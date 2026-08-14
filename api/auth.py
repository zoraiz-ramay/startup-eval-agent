"""Microsoft Entra ID sign-in, as a backend-for-frontend.

FastAPI is the confidential client: it performs the authorization-code exchange with a
client secret, keeps every token server-side, and hands the browser nothing but an opaque
session id in an httpOnly cookie. The SPA never sees a token, which is what lets
`ui/src/api.js` keep its "no tokens in the browser bundle" stance.

Three things here look heavier than a small internal tool needs, and all three are deliberate:

1. **Sessions live in Redis, not in a signed cookie and not in SQLite.** A signed cookie
   puts the payload *in the browser* — tamper-proof but readable — which defeats the whole
   point, and an Entra id_token blows the 4 KB cookie budget anyway. SQLite is worse:
   `api/store.py` ships the entire database file to S3 on a background thread after every
   write, so session tokens would be uploaded to a bucket, and `--workers 2` would have two
   processes racing whole-file uploads. Redis was already running in the container with no
   consumer at all.

2. **The stub mode is sealed twice.** Conditional Access at ACP 3 requires a compliant
   device on a trusted location, which no CI runner can ever be, so the test suite needs a
   way in. `AUTH_MODE=stub` replaces *only* the Entra round-trip — cookies, CSRF, the
   session store and the middleware guard all run production code. Both seals below must
   fail simultaneously for that flag to take effect in production.

3. **Config is read at a defined moment, not at import.** The rest of the codebase reads
   `os.getenv` at module scope, which works only because `api/main.py` imports `core`
   (and therefore `load_dotenv`) first. For auth, *when* env is read decides whether the
   app fails open, and that is not a property worth resting on import order.
"""
from __future__ import annotations

import logging
import os
import re
import secrets
import sys
import time
from dataclasses import dataclass, field
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

log = logging.getLogger("api.auth")

SESSION_COOKIE = "sea_session"
CSRF_COOKIE = "sea_csrf"
TXN_COOKIE = "sea_txn"

# The sign-in transaction (state/nonce/PKCE verifier) is short-lived by design: it exists
# only for the round trip to Entra and back.
TXN_TTL_SECONDS = 300

# Fixed, not configurable. A varying e2e identity means a varying avatar glyph, which means
# flickering visual baselines, which trains people to ignore screenshot diffs.
STUB_PRINCIPAL = {
    "oid": "00000000-0000-0000-0000-000000000001",
    "name": "E2E Reviewer",
    "upn": "e2e.reviewer@siemens.com",
    "email": "e2e.reviewer@siemens.com",
    "tid": "00000000-0000-0000-0000-0000000000ff",
    "source": "stub",
}


# ------------------------------------------------------------------ settings

@dataclass(frozen=True)
class AuthSettings:
    mode: str
    tenant_id: str = ""
    client_id: str = ""
    client_secret: str = field(default="", repr=False)
    redirect_uri: str = ""
    session_ttl: int = 28800
    session_backend: str = "redis"
    redis_url: str = "redis://127.0.0.1:6379/1"
    secure_cookies: bool = False

    @property
    def authority(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}"

    @property
    def is_stub(self) -> bool:
        return self.mode == "stub"


def _secret_from_env(name: str) -> str:
    """Read a secret, tolerating either injection shape the CI hub might use.

    Production values come from AWS Secrets Manager (`docker-apps/startup-evaluation-agent-hydra`),
    and whether the platform explodes that into individual env vars or hands over one JSON
    blob is not discoverable from this repo. Handle both rather than guess.
    """
    direct = os.getenv(name, "").strip()
    if direct:
        return direct
    blob = os.getenv("APP_SECRETS", "").strip() or os.getenv("AWS_SECRET_JSON", "").strip()
    if blob:
        try:
            import json
            return str(json.loads(blob).get(name, "")).strip()
        except Exception:
            log.warning("APP_SECRETS is set but is not valid JSON; ignoring it")
    return ""


def _enforce_seals(mode: str) -> None:
    """Refuse to run with auth stubbed anywhere that looks like production.

    Two independent checks, because one of them failing silently is exactly the scenario
    this is here to prevent. APP_ENV is baked into the image (see Dockerfile), so flipping
    it requires a rebuild and a reviewable diff rather than a console edit.
    """
    if mode == "entra":
        return
    if os.getenv("APP_ENV", "").strip().lower() == "production":
        sys.exit(
            f"FATAL: AUTH_MODE={mode!r} with APP_ENV=production. Authentication cannot be "
            "stubbed in production. Unset AUTH_MODE to use Entra ID."
        )
    if "gunicorn" in os.path.basename(sys.argv[0] or "").lower():
        sys.exit(
            f"FATAL: AUTH_MODE={mode!r} under gunicorn. The stub is for tests and local "
            "development only. Unset AUTH_MODE to use Entra ID."
        )


@lru_cache(maxsize=1)
def settings() -> AuthSettings:
    """Build (and validate) auth config once, at app construction.

    Fail-closed: a missing client secret with AUTH_MODE=entra stops the process. There is
    deliberately no "not configured, so allow everything" branch anywhere in this module —
    that default is precisely what the shared-token auth this replaces got wrong.
    """
    mode = os.getenv("AUTH_MODE", "entra").strip().lower() or "entra"
    if mode not in ("entra", "stub"):
        sys.exit(f"FATAL: AUTH_MODE must be 'entra' or 'stub', got {mode!r}.")
    _enforce_seals(mode)

    is_prod = os.getenv("APP_ENV", "").strip().lower() == "production"
    cfg = AuthSettings(
        mode=mode,
        tenant_id=_secret_from_env("ENTRA_TENANT_ID"),
        client_id=_secret_from_env("ENTRA_CLIENT_ID"),
        client_secret=_secret_from_env("ENTRA_CLIENT_SECRET"),
        redirect_uri=_secret_from_env("ENTRA_REDIRECT_URI"),
        session_ttl=int(os.getenv("SESSION_TTL_SECONDS", "28800")),
        session_backend=os.getenv("SESSION_BACKEND", "redis").strip().lower(),
        redis_url=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/1").strip(),
        secure_cookies=is_prod,
    )

    if mode == "entra":
        missing = [n for n, v in (
            ("ENTRA_TENANT_ID", cfg.tenant_id),
            ("ENTRA_CLIENT_ID", cfg.client_id),
            ("ENTRA_CLIENT_SECRET", cfg.client_secret),
            ("ENTRA_REDIRECT_URI", cfg.redirect_uri),
        ) if not v]
        if missing:
            sys.exit(
                "FATAL: Entra ID sign-in is not configured. Missing: "
                + ", ".join(missing)
                + ".\nSet them, or use AUTH_MODE=stub for local development."
            )
    else:
        log.warning(
            "AUTH_MODE=stub — sign-in is FAKED. Every session is the same fixed test "
            "identity. This must never run outside tests and local development."
        )
    return cfg


# ------------------------------------------------------------------ principal

@dataclass(frozen=True)
class Principal:
    oid: str
    name: str
    upn: str
    email: str
    tid: str
    source: str = "entra"

    @property
    def initials(self) -> str:
        parts = [p for p in re.split(r"[\s,]+", self.name or "") if p]
        if not parts:
            return (self.email or "?")[:1].upper()
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][:1] + parts[-1][:1]).upper()

    def as_dict(self) -> dict:
        return {"oid": self.oid, "name": self.name, "upn": self.upn,
                "email": self.email, "tid": self.tid, "source": self.source}

    def as_reviewer(self) -> dict:
        """The shape api/store.py records against an override."""
        return {"name": self.name or self.upn or self.email,
                "oid": self.oid, "upn": self.upn, "tid": self.tid, "source": self.source}


class ClaimsError(Exception):
    """Raised with a short, already-mapped error code — never raw Entra prose."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def validate_claims(claims: dict, expected_tid: str) -> Principal:
    """Turn validated id_token claims into a Principal, or raise ClaimsError.

    MSAL has already checked the token's signature, issuer, audience and nonce by the time
    we get here. What it does *not* check is that the token came from our tenant: the app
    registration is single-tenant, but a misconfiguration there would otherwise let any
    Microsoft account in, so the check is repeated in code where it is visible and tested.
    """
    tid = str(claims.get("tid") or "").strip()
    if not tid or (expected_tid and tid != expected_tid):
        raise ClaimsError("tenant_mismatch")

    # oid is the only stable identifier: names and email addresses change, oid does not.
    # Without it there is nothing durable to attribute an override to.
    oid = str(claims.get("oid") or "").strip()
    if not oid:
        raise ClaimsError("missing_oid")

    upn = str(claims.get("preferred_username") or claims.get("upn") or "").strip()
    email = str(claims.get("email") or upn).strip()
    name = str(claims.get("name") or upn or email).strip()
    return Principal(oid=oid, name=name, upn=upn, email=email, tid=tid, source="entra")


# ------------------------------------------------------------------ error mapping

# Entra reports failures as AADSTS<number> inside a prose description meant for developers.
# The number is the actionable part; the prose is Microsoft-internal, changes without
# notice, and is partly attacker-influencable, so it never reaches the browser.
_AADSTS_CODES = {
    "53000": "device_not_compliant",
    "53001": "device_not_trusted",
    "53002": "device_not_trusted",
    # 53003 is the umbrella "blocked by Conditional Access" code. A trusted-location
    # failure has NO distinct code of its own — it arrives as 53003 exactly like a device
    # failure — so the copy for this one has to name both causes. Guessing which condition
    # failed would send half the affected users chasing the wrong fix.
    "53003": "access_blocked",
    "50158": "access_blocked",
    "50005": "mfa_required",
    "53004": "mfa_required",
    "50076": "mfa_required",
    "50105": "not_assigned",
    "90072": "tenant_mismatch",
    "50020": "tenant_mismatch",
    "50011": "config_error",
    "700016": "config_error",
    "7000215": "config_error",
}

# An expired client secret is the classic middle-of-the-night outage: everything worked
# yesterday, the symptom is a generic sign-in failure, and nothing in the UI can say why.
_LOG_AS_ERROR = {"config_error"}


def map_entra_error(error: str, description: str) -> str:
    """Map an Entra error response to one of our short codes.

    Unknown codes deliberately fall through to "unknown" rather than being guessed at:
    a wrong-but-specific instruction wastes more of the user's time than an honest generic
    one plus a correlation ID.
    """
    for code in re.findall(r"AADSTS(\d+)", description or ""):
        mapped = _AADSTS_CODES.get(code)
        if mapped:
            return mapped
    if (error or "").strip() == "access_denied" and "AADSTS" not in (description or ""):
        return "cancelled"
    return "unknown"


def extract_correlation_id(description: str) -> str:
    """Pull Entra's correlation ID out of the description — the one string Siemens IT asks for."""
    m = re.search(r"Correlation ID:\s*([0-9a-fA-F-]{8,})", description or "")
    return m.group(1) if m else ""


# ------------------------------------------------------------------ session store

class MemorySessions:
    """Process-local sessions. Development and tests only.

    Deliberately not usable in production: it splits under `--workers 2`, so a request
    landing on the other worker looks signed out. `settings()` warns loudly whenever the
    stub mode that goes with it is active.
    """

    def __init__(self) -> None:
        self._data: dict[str, tuple[float, dict]] = {}

    def get(self, key: str) -> dict | None:
        row = self._data.get(key)
        if not row:
            return None
        expires, payload = row
        if expires < time.time():
            self._data.pop(key, None)
            return None
        return payload

    def put(self, key: str, payload: dict, ttl: int) -> None:
        self._data[key] = (time.time() + ttl, payload)

    def delete(self, key: str) -> None:
        self._data.pop(key, None)


class RedisSessions:
    def __init__(self, url: str) -> None:
        import json

        import redis

        self._json = json
        self._client = redis.Redis.from_url(url, decode_responses=True)

    def get(self, key: str) -> dict | None:
        raw = self._client.get(key)
        if not raw:
            return None
        try:
            return self._json.loads(raw)
        except Exception:
            self._client.delete(key)
            return None

    def put(self, key: str, payload: dict, ttl: int) -> None:
        self._client.setex(key, ttl, self._json.dumps(payload))

    def delete(self, key: str) -> None:
        self._client.delete(key)


@lru_cache(maxsize=1)
def sessions():
    cfg = settings()
    if cfg.session_backend == "memory":
        log.warning("SESSION_BACKEND=memory — sessions are process-local and will split "
                    "across workers. Development only.")
        return MemorySessions()
    return RedisSessions(cfg.redis_url)


def load_session(sid: str) -> dict | None:
    if not sid:
        return None
    return sessions().get(f"sess:{sid}")


def create_session(principal: Principal) -> tuple[str, str]:
    """Returns (session_id, csrf_token).

    The session id is minted only *after* the token exchange succeeded, and the transaction
    record is deleted at the same moment, so there is no pre-auth session to fixate.
    """
    sid = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    sessions().put(f"sess:{sid}",
                   {"user": principal.as_dict(), "csrf": csrf, "created_at": time.time()},
                   settings().session_ttl)
    # Durable sign-in record for the admin dashboard. Redis holds only *live* sessions (they
    # expire after SESSION_TTL), so it can say who is online but never how many sessions
    # there have been. Imported here rather than at module scope to keep the auth module
    # importable without the persistence layer, and best-effort: a full disk must not be
    # able to stop people signing in.
    try:
        from api import store
        store.record_session(principal.as_reviewer())
    except Exception as exc:
        log.warning("Could not record sign-in for the admin log: %s", exc)
    return sid, csrf


def destroy_session(sid: str) -> None:
    if sid:
        sessions().delete(f"sess:{sid}")


# ------------------------------------------------------------------ dependency

def current_user(request: Request) -> Principal:
    """The authenticated principal, resolved by SecurityMiddleware earlier in the stack.

    Performs no I/O: it reads what the guard already established, so it cannot disagree
    with the guard about who is signed in. Role gating, when it arrives, belongs here as a
    sibling dependency rather than as a second lookup.
    """
    user = request.scope.get("state", {}).get("user")
    if not isinstance(user, Principal):
        raise HTTPException(status_code=401, detail="Not signed in.")
    return user


def admin_upns() -> frozenset[str]:
    """The seed admins, from ADMIN_UPNS (comma-separated).

    Read per call rather than captured at import so a deployment can change the list by
    restarting the process without a code change, and so tests can set it with monkeypatch.

    Goes through _secret_from_env, not os.getenv, because production config arrives from AWS
    Secrets Manager and it is not knowable from this repo whether the CI hub explodes that
    secret into individual env vars or hands over one JSON blob. Reading only the plain env
    var would, under the blob shape, leave this empty in production — and the symptom is an
    ordinary 403, indistinguishable from "you are not on the list".
    """
    raw = _secret_from_env("ADMIN_UPNS")
    return frozenset(u.strip().lower() for u in raw.split(",") if u.strip())


def db_admin_upns() -> frozenset[str]:
    """Admins granted in-app. Never the only source — see is_admin.

    A failure here must not lock everyone out of a working deployment, so a broken or
    unreachable database degrades to "no in-app grants" rather than raising into the auth
    path. That is still fail-closed: it can only ever remove access, never add it.
    """
    try:
        from api import store
        return frozenset(store.admin_upns_from_db())
    except Exception:
        log.warning("[auth] could not read the admins table; falling back to ADMIN_UPNS only",
                    exc_info=True)
        return frozenset()


def is_admin(user: Principal) -> bool:
    """Membership is by UPN, which is the tenant-unique sign-in name.

    Two sources, union: the ADMIN_UPNS seed and the in-app grants. The seed cannot be dropped
    in favour of the table alone — with an empty table and no "not configured, so allow"
    branch anywhere in this module, nobody would be able to make the first grant, and the
    only way back in would be the AWS console.

    Fail-closed otherwise: an unset ADMIN_UPNS and an empty table means NOBODY is an admin.
    The admin surface exposes every reviewer's activity, so getting that default wrong is
    worse than locking the owner out of their own dashboard until they set the variable.
    """
    upn = (getattr(user, "upn", "") or "").strip().lower()
    if not upn:
        return False
    return upn in admin_upns() or upn in db_admin_upns()


def require_admin(user: Principal = Depends(current_user)) -> Principal:
    """Sibling of current_user for the /api/admin routes. 403, not 404: the caller is
    authenticated and the route exists — hiding that adds nothing an attacker cannot infer
    from the SPA bundle, and it makes a misconfigured ADMIN_UPNS impossible to diagnose."""
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="Administrator access required.")
    return user


# ------------------------------------------------------------------ cookies

def _set_cookie(response: Response, name: str, value: str, *, max_age: int,
                http_only: bool = True, path: str = "/") -> None:
    response.set_cookie(
        name, value, max_age=max_age, path=path, httponly=http_only,
        secure=settings().secure_cookies,
        # Lax is forced, not chosen. The Entra callback is a cross-site top-level GET, and
        # under Strict the transaction cookie is not sent at all — login would fail 100% of
        # the time. Lax still withholds the cookie on cross-site POST/PATCH/DELETE, and the
        # double-submit CSRF token covers what remains.
        samesite="lax",
    )


def _clear_cookie(response: Response, name: str, path: str = "/") -> None:
    response.delete_cookie(name, path=path)


# ------------------------------------------------------------------ routes

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _safe_next(raw: str | None) -> str:
    """Constrain post-login redirects to paths inside this app.

    Without this, /api/auth/login?next=https://evil.example is an open redirect wearing a
    Siemens hostname — a credible phishing primitive precisely because the first hop is
    genuine.
    """
    value = (raw or "/").strip()
    if not value.startswith("/") or value.startswith("//") or "\\" in value or ":" in value.split("/")[0]:
        return "/"
    return value


def _msal_app():
    import msal

    cfg = settings()
    return msal.ConfidentialClientApplication(
        cfg.client_id, authority=cfg.authority, client_credential=cfg.client_secret,
    )


@router.get("/login")
def login(request: Request, next: str = "/"):
    cfg = settings()
    target = _safe_next(next)

    if cfg.is_stub:
        principal = Principal(**{k: v for k, v in STUB_PRINCIPAL.items()})
        sid, csrf = create_session(principal)
        response = RedirectResponse(target, status_code=302)
        _set_cookie(response, SESSION_COOKIE, sid, max_age=cfg.session_ttl)
        _set_cookie(response, CSRF_COOKIE, csrf, max_age=cfg.session_ttl, http_only=False)
        return response

    # MSAL's auth-code flow generates and later verifies state, nonce and the PKCE verifier
    # itself. Keeping the whole flow dict server-side means none of those ever reach the
    # browser, and the record is single-use.
    flow = _msal_app().initiate_auth_code_flow(scopes=[], redirect_uri=cfg.redirect_uri)
    txid = secrets.token_urlsafe(24)
    sessions().put(f"authtx:{txid}", {"flow": flow, "next": target}, TXN_TTL_SECONDS)

    response = RedirectResponse(flow["auth_uri"], status_code=302)
    _set_cookie(response, TXN_COOKIE, txid, max_age=TXN_TTL_SECONDS, path="/api/auth")
    return response


def _signin_redirect(code: str, correlation_id: str = "") -> RedirectResponse:
    url = f"/signin?e={code}"
    if correlation_id:
        url += f"&cid={correlation_id}"
    response = RedirectResponse(url, status_code=302)
    _clear_cookie(response, TXN_COOKIE, path="/api/auth")
    return response


@router.get("/callback")
def callback(request: Request):
    cfg = settings()
    if cfg.is_stub:
        return _signin_redirect("config_error")

    txid = request.cookies.get(TXN_COOKIE, "")
    record = sessions().get(f"authtx:{txid}") if txid else None
    if not record:
        # Expired, replayed, or arrived without the cookie. Treat as a fresh start rather
        # than an error the user can do anything about.
        return _signin_redirect("expired")
    sessions().delete(f"authtx:{txid}")

    params = dict(request.query_params)
    if params.get("error"):
        description = params.get("error_description", "")
        code = map_entra_error(params["error"], description)
        cid = extract_correlation_id(description)
        level = logging.ERROR if code in _LOG_AS_ERROR else logging.WARNING
        log.log(level, "Entra sign-in failed (%s): %s", code, description)
        return _signin_redirect(code, cid)

    try:
        result = _msal_app().acquire_token_by_auth_code_flow(record["flow"], params)
    except Exception as exc:
        log.warning("Auth code exchange failed: %s", exc)
        return _signin_redirect("unknown")

    if "error" in result:
        description = result.get("error_description", "")
        code = map_entra_error(result["error"], description)
        level = logging.ERROR if code in _LOG_AS_ERROR else logging.WARNING
        log.log(level, "Token exchange rejected (%s): %s", code, description)
        return _signin_redirect(code, extract_correlation_id(description))

    try:
        principal = validate_claims(result.get("id_token_claims") or {}, cfg.tenant_id)
    except ClaimsError as exc:
        log.warning("Rejected sign-in: %s", exc.code)
        return _signin_redirect(exc.code)

    # We call no downstream API, so the refresh token MSAL just cached has no purpose and
    # would only be one more credential sitting in an unauthenticated loopback Redis if it
    # were ever persisted. Drop it; the session below is what keeps the user signed in.
    app = _msal_app()
    for account in app.get_accounts():
        app.remove_account(account)

    sid, csrf = create_session(principal)
    response = RedirectResponse(_safe_next(record.get("next")), status_code=302)
    _set_cookie(response, SESSION_COOKIE, sid, max_age=cfg.session_ttl)
    _set_cookie(response, CSRF_COOKIE, csrf, max_age=cfg.session_ttl, http_only=False)
    _clear_cookie(response, TXN_COOKIE, path="/api/auth")
    return response


@router.post("/logout")
def logout(request: Request):
    """Sign out locally. Missing session is success, not an error.

    POST rather than GET so that `<img src="/api/auth/logout">` on any page cannot sign a
    reviewer out. The Entra end-session URL is returned rather than followed: silently
    signing someone out of every Siemens app because they left one internal tool is a
    hostile surprise, so it needs its own button.
    """
    destroy_session(request.cookies.get(SESSION_COOKIE, ""))
    cfg = settings()
    body = {"ok": True}
    if not cfg.is_stub:
        body["logout_url"] = f"{cfg.authority}/oauth2/v2.0/logout"
    response = JSONResponse(body)
    _clear_cookie(response, SESSION_COOKIE)
    _clear_cookie(response, CSRF_COOKIE)
    return response


@router.get("/me")
def me(request: Request):
    """Who is signed in — 200 whether or not anyone is.

    This is the SPA's very first request, and a 401 here would make first paint an error
    case and collide with the global 401 handler. "Nobody is signed in" is a fact, not a
    failure.
    """
    cfg = settings()
    user = request.scope.get("state", {}).get("user")
    if not isinstance(user, Principal):
        return {"authenticated": False, "mode": cfg.mode}
    return {"authenticated": True, "mode": cfg.mode,
            "user": {"name": user.name, "email": user.email or user.upn,
                     "initials": user.initials, "oid": user.oid,
                     # The exact string the admin list matches on. Without it there is no way
                     # to find out what to type when granting someone access: `email` is the
                     # email claim, which is not necessarily the preferred_username this is
                     # keyed on. It is the caller's own identity, so it widens nothing.
                     "upn": user.upn,
                     # Only decides whether the SPA renders the admin nav entry. Every
                     # /api/admin route re-checks with require_admin, so a client that
                     # flips this flag gains nothing.
                     "is_admin": is_admin(user)}}
