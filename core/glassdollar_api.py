"""GlassDollar public REST API client.

Replaces the local Excel export as the source of GlassDollar company data. Auth is a
two-step flow:

    1. POST {BASE}/v1/token with header `X-API-Key: <key>`  -> {access_token, expires_in}
    2. Send `Authorization: Bearer <access_token>` on every data call.

The bearer token is short-lived, so it is cached and transparently refreshed shortly
before it expires (and once more on a 401). Company objects returned by the API are
mapped back onto the SAME column names the rest of the pipeline already expects, so
enrich / verify / summarize / fit / score / route keep working unchanged.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import time
from typing import Optional

import pandas as pd
import requests

from .config import GLASSDOLLAR_API_BASE, GLASSDOLLAR_API_KEY, GLASSDOLLAR_API_TIMEOUT

# Refresh the token this many seconds BEFORE its stated expiry, to avoid racing the boundary.
_TOKEN_SKEW_SECONDS = 60
# Page size for the paginated /v1/companies listing.
_PAGE_SIZE = 100
# The /v1/token endpoint is HEAVILY rate-limited (a handful of requests per window), so the
# bearer token is cached to disk and shared across process restarts / Streamlit reruns.
_TOKEN_CACHE_PATH = os.path.join(tempfile.gettempdir(), "glassdollar_token_cache.json")


class GlassDollarError(RuntimeError):
    """Raised when the GlassDollar API cannot be reached or authenticated."""


class GlassDollarClient:
    """Thin, thread-safe client over the GlassDollar public REST API."""

    def __init__(self, api_key: str = "", base: str = "", timeout: float = 0.0):
        # Read the key dynamically (config -> env) so a key entered at runtime still works
        # even though config captured its value at import time.
        self.api_key = (api_key or GLASSDOLLAR_API_KEY or os.getenv("GLASSDOLLAR_API_KEY", "")).strip()
        self.base = (base or GLASSDOLLAR_API_BASE).rstrip("/")
        self.timeout = timeout or GLASSDOLLAR_API_TIMEOUT
        self._session = requests.Session()
        self._token = ""
        self._token_expiry = 0.0
        self._lock = threading.Lock()
        # try to reuse a token cached by a previous run before ever calling /v1/token
        self._load_cached_token()

    # ---------------------------------------------------------------- token disk cache
    def _token_cache_key(self) -> str:
        return hashlib.sha256(f"{self.base}|{self.api_key}".encode()).hexdigest()

    def _load_cached_token(self) -> None:
        """Load a still-valid token saved by a previous process, avoiding a /v1/token call."""
        try:
            with open(_TOKEN_CACHE_PATH, "r", encoding="utf-8") as f:
                cache = json.load(f)
            entry = cache.get(self._token_cache_key())
            if entry and float(entry.get("expiry", 0)) > time.time():
                self._token = entry.get("token", "")
                self._token_expiry = float(entry.get("expiry", 0))
        except (OSError, ValueError):
            pass

    def _save_cached_token(self) -> None:
        try:
            cache = {}
            if os.path.exists(_TOKEN_CACHE_PATH):
                with open(_TOKEN_CACHE_PATH, "r", encoding="utf-8") as f:
                    cache = json.load(f) or {}
            cache[self._token_cache_key()] = {"token": self._token, "expiry": self._token_expiry}
            with open(_TOKEN_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(cache, f)
        except (OSError, ValueError):
            pass

    # ---------------------------------------------------------------- auth
    def _fetch_token(self) -> None:
        """POST /v1/token with the X-API-Key header and cache the returned bearer token."""
        if not self.api_key:
            raise GlassDollarError(
                "No GlassDollar API key set. Set GLASSDOLLAR_API_KEY (or pass it in Settings).")
        try:
            r = self._session.post(f"{self.base}/v1/token",
                                   headers={"X-API-Key": self.api_key}, timeout=self.timeout)
        except requests.RequestException as e:
            raise GlassDollarError(f"Could not reach GlassDollar token endpoint: {e}") from e
        if r.status_code == 429:
            # Rate-limited on the token endpoint. Surface the reset hint so the user can wait.
            retry_after = ""
            try:
                retry_after = f" Retry in ~{int(float(r.json().get('retryAfter', 0)) / 60)} min."
            except (ValueError, TypeError):
                pass
            raise GlassDollarError(
                "GlassDollar token endpoint rate limit exceeded (it allows only a few token "
                f"requests per window).{retry_after} The last good token is reused when possible.")
        if r.status_code != 200:
            raise GlassDollarError(
                f"GlassDollar token request failed ({r.status_code}): {r.text[:200]}")
        body = r.json()
        token = body.get("access_token", "")
        if not token:
            raise GlassDollarError("GlassDollar token response did not include an access_token.")
        expires_in = float(body.get("expires_in", 3600) or 3600)
        self._token = token
        self._token_expiry = time.time() + max(0.0, expires_in - _TOKEN_SKEW_SECONDS)
        self._save_cached_token()

    def _valid_token(self) -> str:
        with self._lock:
            if not self._token or time.time() >= self._token_expiry:
                # a concurrent process may have refreshed it on disk since we last looked
                self._load_cached_token()
            if not self._token or time.time() >= self._token_expiry:
                self._fetch_token()
            return self._token

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self._valid_token()}"}

    # ---------------------------------------------------------------- request
    def _request(self, method: str, path: str, *, params: dict = None,
                 json_body: dict = None) -> dict:
        """Perform an authenticated request, retrying on timeouts and one 401 refresh."""
        url = f"{self.base}{path}"
        max_attempts = 4
        last_timeout_err: Optional[Exception] = None
        attempt = 0
        while attempt < max_attempts:
            attempt += 1
            headers = self._auth_headers()
            if json_body is not None:
                headers["Content-Type"] = "application/json"
            try:
                r = self._session.request(method, url, headers=headers, params=params,
                                          json=json_body, timeout=self.timeout)
            except (requests.Timeout, requests.ConnectionError) as e:
                # Transient network/slow-endpoint issue -> back off briefly and retry.
                last_timeout_err = e
                if attempt < max_attempts:
                    time.sleep(min(2.0 * attempt, 6.0))
                    continue
                raise GlassDollarError(
                    f"GlassDollar request to {path} timed out after {attempt} attempts: {e}") from e
            except requests.RequestException as e:
                raise GlassDollarError(f"GlassDollar request to {path} failed: {e}") from e
            if r.status_code == 401 and attempt == 1:
                # token likely expired mid-flight -> force a refresh and retry once
                with self._lock:
                    self._token = ""
                    self._token_expiry = 0.0
                continue
            if r.status_code >= 500 and attempt < max_attempts:
                # transient server-side error (the search endpoint 500s intermittently) -> retry
                last_timeout_err = GlassDollarError(
                    f"GlassDollar {path} returned {r.status_code}: {r.text[:120]}")
                time.sleep(min(1.5 * attempt, 5.0))
                continue
            if r.status_code != 200:
                raise GlassDollarError(
                    f"GlassDollar GET {path} failed ({r.status_code}): {r.text[:200]}")
            try:
                return r.json()
            except ValueError as e:
                raise GlassDollarError(f"GlassDollar {path} returned non-JSON: {e}") from e
        if last_timeout_err is not None:
            raise GlassDollarError(
                f"GlassDollar request to {path} timed out: {last_timeout_err}") from last_timeout_err
        raise GlassDollarError(f"GlassDollar {path} failed after token refresh.")

    # ---------------------------------------------------------------- endpoints
    def list_companies(self, limit: int = _PAGE_SIZE, offset: int = 0) -> dict:
        return self._request("GET", "/v1/companies", params={"limit": limit, "offset": offset})

    def list_all_companies(self) -> list[dict]:
        """Fetch every company for the org by paging until the aggregate count is reached."""
        first = self.list_companies(limit=_PAGE_SIZE, offset=0)
        companies = list(first.get("companies", []))
        total = (first.get("companies_aggregate", {}) or {}).get("aggregate", {}).get("count")
        total = int(total) if total is not None else len(companies)
        offset = len(companies)
        while offset < total:
            page = self.list_companies(limit=_PAGE_SIZE, offset=offset)
            batch = page.get("companies", [])
            if not batch:
                break
            companies.extend(batch)
            offset += len(batch)
        return companies

    def search_companies(self, search: str, limit: int = 10) -> list[dict]:
        body = {"search": search}
        if limit:
            body["limit"] = limit
        resp = self._request("POST", "/v1/companies/search", json_body=body)
        return resp.get("results", []) or []

    def get_company(self, company_id: int) -> Optional[dict]:
        resp = self._request("GET", f"/v1/companies/{int(company_id)}")
        return resp.get("company")

    def get_company_by_domain(self, domain: str) -> Optional[dict]:
        resp = self._request("GET", f"/v1/companies/by-domain/{domain}")
        companies = resp.get("companies", []) or []
        return companies[0] if companies else None


# ----------------------------------------------------------------------------- mapping helpers
def _fmt_funding(value) -> str:
    """Format the bigint `funding` (in currency units) as a compact human string."""
    if value in (None, "", 0):
        return ""
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return str(value)
    if amount >= 1_000_000_000:
        return f"€{amount / 1_000_000_000:.1f}B"
    if amount >= 1_000_000:
        return f"€{amount / 1_000_000:.1f}M"
    if amount >= 1_000:
        return f"€{amount / 1_000:.0f}K"
    return f"€{amount:.0f}"


def _parse_customers(value) -> str:
    """`referenced_customers` is a jsonb blob: a list of names or of {name:...} objects."""
    if not value:
        return ""
    data = value
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except ValueError:
            return data.strip()
    names: list[str] = []
    if isinstance(data, dict):
        data = data.get("customers", data.get("items", list(data.values())))
    if isinstance(data, (list, tuple)):
        for item in data:
            if isinstance(item, dict):
                n = item.get("name") or item.get("title") or ""
                if n:
                    names.append(str(n).strip())
            elif item:
                names.append(str(item).strip())
    elif data:
        names.append(str(data).strip())
    return ", ".join(n for n in names if n)


def company_to_row(company: dict) -> pd.Series:
    """Map an API company object onto the GlassDollar row shape the pipeline expects.

    Fields the public API does not expose (pitch-form answers such as Business model and
    Development stage) are intentionally left blank — no inference.
    """
    c = company or {}
    tags = c.get("tags") or []
    tags_str = ", ".join(str(t).strip() for t in tags if str(t).strip()) if isinstance(tags, (list, tuple)) else str(tags)
    founded = c.get("founded_year")
    row = {
        "company_name":      str(c.get("name", "") or ""),
        "website":           str(c.get("website", "") or ""),
        "domain":            str(c.get("domain", "") or ""),
        "hq":                str(c.get("hq", "") or ""),
        "founded_year":      "" if founded in (None, "") else str(founded),
        "employee_band":     str(c.get("employee_count", "") or ""),
        "employees_count":   str(c.get("employee_count", "") or ""),
        "funding":           _fmt_funding(c.get("funding")),
        "linkedin_url":      str(c.get("linkedin_url", "") or ""),
        "crunchbase_url":    str(c.get("crunchbase_url", "") or ""),
        "customers":         _parse_customers(c.get("referenced_customers")),
        "short_description": str(c.get("short_description", "") or ""),
        "about_enriched":    str(c.get("long_description", "") or ""),
        "Your pitch":        str(c.get("long_description", "") or c.get("short_description", "") or ""),
        "logo_url":          str(c.get("logo_url", "") or ""),
        "tags":              tags_str,
        # pitch-form fields the public API does not provide -> left blank on purpose
        "Business model": "",
        "Development stage of your solution": "",
        # PDFs deferred: no local pitch deck in API mode
        "has_pdf": "", "pdf_local_path": "", "pdf_filename": "",
        # keep the numeric id around so callers can hydrate full detail
        "glassdollar_id": "" if c.get("id") in (None, "") else str(c.get("id")),
    }
    return pd.Series(row)


# ----------------------------------------------------------------------------- module API
_default_client: Optional[GlassDollarClient] = None


def get_client(api_key: str = "") -> GlassDollarClient:
    """Return a cached default client, or a fresh one when an explicit key is supplied."""
    global _default_client
    if api_key:
        return GlassDollarClient(api_key=api_key)
    env_key = (GLASSDOLLAR_API_KEY or os.getenv("GLASSDOLLAR_API_KEY", "")).strip()
    # Rebuild the cached client if the active key changed since it was created.
    if _default_client is None or _default_client.api_key != env_key:
        _default_client = GlassDollarClient()
    return _default_client


def load_all_as_df(api_key: str = "") -> pd.DataFrame:
    """Fetch every company and return the GlassDollar-shaped DataFrame.

    WARNING: the GlassDollar database contains millions of companies and each page is slow,
    so this is NOT suitable for populating a picker. Prefer search_as_df() for interactive use.
    """
    companies = get_client(api_key).list_all_companies()
    rows = [company_to_row(c) for c in companies]
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).fillna("")


def _search_result_to_row(result: dict) -> pd.Series:
    """Map a /v1/companies/search hit ({company_id, company:{name,domain,logo_url}}) to a row.

    Search hits are intentionally light; the full profile is hydrated later via get_company().
    """
    comp = (result or {}).get("company", {}) or {}
    cid = result.get("company_id") or comp.get("id") or ""
    row = company_to_row(comp)
    row["glassdollar_id"] = "" if cid == "" else str(cid)   # search omits company.id -> outer id
    return row


def search_as_df(search: str, limit: int = 10, api_key: str = "") -> pd.DataFrame:
    """Search companies by name and return a small GlassDollar-shaped DataFrame of candidates.

    Raises GlassDollarError on auth/rate-limit/network failures so the caller can show why the
    picker is empty; a successful search with no hits simply returns an empty DataFrame.
    """
    if not str(search).strip():
        return pd.DataFrame()
    results = get_client(api_key).search_companies(search, limit=limit)
    rows = [_search_result_to_row(r) for r in results]
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).fillna("")


def search_companies(search: str, limit: int = 10, api_key: str = "") -> list[dict]:
    return get_client(api_key).search_companies(search, limit=limit)


def get_company(company_id: int, api_key: str = "") -> Optional[dict]:
    return get_client(api_key).get_company(company_id)


def get_company_row(company_id: int, api_key: str = "") -> Optional[pd.Series]:
    company = get_company(company_id, api_key=api_key)
    return company_to_row(company) if company else None
