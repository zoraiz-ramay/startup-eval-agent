"""Siemens Directory API client: employees by department, for the "Relevant Siemens Contact" list.

`GET {SIEMENS_DIRECTORY_API_BASE}/people` with the API key in a header and the department as a
filter. Only three fields leave this module — `commonName`, `department` and `email` (LDAP `cn`,
`department`, `mail`) — because a contact list needs nothing more, and anything else in a person
record is not ours to copy. Any of the three may be null in LDAP; a person with neither a name
nor an email is not a contact and is dropped.

Pagination is cursor-based and the docs recommend low limits, so a search reads at most
SIEMENS_DIRECTORY_MAX_PAGES pages of SIEMENS_DIRECTORY_LIMIT. If a cursor is rejected as invalid,
the search restarts from the beginning once, as the docs require — continuing from a guess would
miss or repeat people.

The key resolves only inside the Siemens network: tests/test_siemens_contacts.py drives this
contract with a fake, and nothing here has been verified against the live service.
"""
from __future__ import annotations

import os

import requests

from . import config


class DirectoryError(RuntimeError):
    """The directory could not be reached or answered with an error."""


class InvalidCursor(DirectoryError):
    """The directory rejected a pagination cursor."""


def _api_key() -> str:
    return os.getenv("SIEMENS_DIRECTORY_API_KEY", "").strip()


def configured() -> bool:
    return bool(_api_key())


def _person(raw) -> dict | None:
    if not isinstance(raw, dict):
        return None
    out = {"name": _text(raw.get("commonName")), "department": _text(raw.get("department")),
           "email": _text(raw.get("email"))}
    return out if out["name"] or out["email"] else None


def _text(value) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _page(body) -> tuple[list, str]:
    """(people, next cursor) from one response, whichever common envelope it uses."""
    if isinstance(body, list):
        return body, ""
    if not isinstance(body, dict):
        return [], ""
    people = next((body[k] for k in ("people", "data", "items", "results") if isinstance(body.get(k), list)), [])
    cursor = next((str(body[k]) for k in ("nextCursor", "next_cursor", "cursor", "next")
                   if body.get(k) and isinstance(body.get(k), (str, int))), "")
    return people, cursor


class DirectoryClient:
    def __init__(self, api_key: str = "", session=None):
        self.api_key = api_key or _api_key()
        self.base = config.SIEMENS_DIRECTORY_API_BASE
        self._session = session or requests.Session()

    def _get(self, params: dict):
        try:
            r = self._session.get(f"{self.base}/people", params=params,
                                  headers={config.SIEMENS_DIRECTORY_KEY_HEADER: self.api_key},
                                  timeout=config.SIEMENS_DIRECTORY_TIMEOUT)
        except requests.RequestException as e:
            raise DirectoryError(f"Could not reach the Siemens Directory: {e}") from e
        if r.status_code in (400, 422) and config.SIEMENS_DIRECTORY_CURSOR_PARAM in params \
                and "cursor" in (r.text or "").lower():
            raise InvalidCursor(r.text[:200])
        if r.status_code != 200:
            raise DirectoryError(f"Siemens Directory request failed ({r.status_code})")
        try:
            return r.json()
        except ValueError as e:
            raise DirectoryError("Siemens Directory returned something other than JSON") from e

    def people_in(self, department: str) -> list[dict]:
        """Everyone the directory lists under ``department``, at most a few pages of them."""
        if not self.api_key:
            raise DirectoryError("No Siemens Directory API key is set (SIEMENS_DIRECTORY_API_KEY).")
        for attempt in range(2):
            try:
                return self._read(department)
            except InvalidCursor:
                if attempt:
                    raise
                # Restart from the beginning rather than continue from a cursor the API rejected.
        return []

    def _read(self, department: str) -> list[dict]:
        out, cursor = [], ""
        base = {config.SIEMENS_DIRECTORY_DEPARTMENT_PARAM: department, "limit": config.SIEMENS_DIRECTORY_LIMIT}
        for _ in range(max(1, config.SIEMENS_DIRECTORY_MAX_PAGES)):
            params = {**base, **({config.SIEMENS_DIRECTORY_CURSOR_PARAM: cursor} if cursor else {})}
            people, cursor = _page(self._get(params))
            out += [p for p in (_person(x) for x in people) if p]
            if not cursor:
                break
        return out
