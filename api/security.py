"""API hardening: security headers, session enforcement, CSRF, per-IP rate limiting.

Defense-in-depth for a small internal tool:
- Security headers on every response (no sniffing, no framing, no referrer leakage).
- Session auth: every /api/* request outside the public allowlist must carry a valid
  session cookie, resolved here and handed to routes via `Depends(current_user)`.
- Double-submit CSRF check on every state-changing request.
- Sliding-window per-IP rate limit (in-memory; suitable for single-process deploys).
  Evaluate/solve are expensive (LLM + web calls), so they get a tighter budget.

The guard lives in middleware rather than as a dependency on each route because there are
nineteen routes and the failure mode of the alternative is silent: forget the decorator on
a new endpoint and it ships open. Here, a new route is protected by default and has to be
named in PUBLIC_PATHS to opt out — the mistake is visible in review instead of invisible.

The shared `API_AUTH_TOKEN` this replaces was a single static secret for the whole
deployment, unset by default, which answered "does the caller know the password" rather
than "who is the caller". Nothing in the repo referenced it.
"""
from __future__ import annotations

import hmac
import os
import time
import threading
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.auth import SESSION_COOKIE, Principal, load_session

# requests allowed per window (seconds) per client IP
RATE_DEFAULT = (int(os.getenv("RATE_LIMIT_DEFAULT", "120")), 60.0)
RATE_EXPENSIVE = (int(os.getenv("RATE_LIMIT_EXPENSIVE", "10")), 60.0)
# Auth plumbing gets its own generous budget, separate from the data API.
#
# None of these endpoints holds a credential to guess: /login mints a transaction and
# redirects to Entra, which is where authentication actually happens, and /me is a session
# lookup. What makes a tight limit here actively harmful is that /me runs on every page
# load while `request.client.host` is the load balancer's address in production — so every
# user shares one bucket, and the app would throttle itself for everyone during any busy
# period. Capping the Redis writes is worth doing; capping page loads is not.
#
# (Honouring X-Forwarded-For would give each user their own bucket, but that header is
# caller-supplied and trusting it needs the proxy hop count pinned down first.)
RATE_AUTH = (int(os.getenv("RATE_LIMIT_AUTH", "300")), 60.0)
_EXPENSIVE_PATHS = ("/api/evaluate", "/api/solve", "/api/ask")
_AUTH_PATHS = ("/api/auth/login", "/api/auth/callback", "/api/auth/me", "/api/auth/logout")

# Reachable without a session. Everything else under /api requires one.
#   - login/callback are how you *get* a session.
#   - logout must succeed when the session has already expired, or a signed-out user is
#     stuck with a stale cookie they cannot clear.
#   - /me is the SPA's first request and reports "not signed in" as a normal 200.
PUBLIC_PATHS = frozenset({
    "/api/auth/login",
    "/api/auth/callback",
    "/api/auth/logout",
    "/api/auth/me",
})

# Swagger issues same-origin fetches from the browser, which would carry the session
# cookie — an authenticated console for anyone who loads the page. Gated with the API.
_DOCS_PATHS = frozenset({"/docs", "/openapi.json", "/redoc"})

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


class SecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[tuple[str, str], deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def _rate_limited(self, identity: str, path: str) -> bool:
        if path in _AUTH_PATHS:
            limit, window, bucket = *RATE_AUTH, "auth"
        elif path in _EXPENSIVE_PATHS:
            limit, window, bucket = *RATE_EXPENSIVE, "expensive"
        else:
            limit, window, bucket = *RATE_DEFAULT, "default"
        now = time.monotonic()
        key = (identity, bucket)
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                return True
            if not q:
                # Keys are per session now, so leaving spent buckets behind would grow this
                # dict by one entry per sign-in for the life of the process.
                self._hits.pop(key, None)
                q = self._hits[key]
            q.append(now)
        return False

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"
        guarded = path.startswith("/api") or path in _DOCS_PATHS

        if guarded:
            sid = request.cookies.get(SESSION_COOKIE, "")
            record = load_session(sid)

            # Budget per session, falling back to IP only for callers who have none.
            #
            # Keying purely on IP was already weak — `request.client.host` is the load
            # balancer's address in production, so the whole company shares one bucket and
            # a busy afternoon looks exactly like an attack. Now that a request cannot
            # reach any data route without a Siemens identity on a compliant device, the
            # session is both the more accurate unit and the harder one to forge: an
            # attacker can trivially vary source IPs, but not mint sessions.
            identity = f"sid:{sid}" if record else f"ip:{client_ip}"
            if self._rate_limited(identity, path):
                return self._finish(JSONResponse(
                    {"detail": "Rate limit exceeded — slow down.", "code": "rate_limited"},
                    status_code=429, headers={"Retry-After": "60"}))

            if record:
                # Written into scope rather than via `request.state` because the Request
                # object here is not the one the endpoint receives; scope is what actually
                # crosses the middleware/endpoint boundary. tests/test_auth.py pins this.
                user = record.get("user") or {}
                request.scope.setdefault("state", {})["user"] = Principal(**user)

            if path not in PUBLIC_PATHS:
                if not record:
                    return self._finish(JSONResponse(
                        {"detail": "Not signed in.", "code": "unauthenticated"},
                        status_code=401))
                if request.method not in _SAFE_METHODS:
                    if not self._csrf_ok(request, record):
                        return self._finish(JSONResponse(
                            {"detail": "Invalid or missing CSRF token.", "code": "csrf"},
                            status_code=403))
            elif path == "/api/auth/logout" and record:
                if not self._csrf_ok(request, record):
                    return self._finish(JSONResponse(
                        {"detail": "Invalid or missing CSRF token.", "code": "csrf"},
                        status_code=403))

        response = await call_next(request)
        return self._finish(response)

    @staticmethod
    def _csrf_ok(request: Request, record: dict) -> bool:
        """Double-submit check against the session record, not just the cookie.

        Comparing the header to the cookie alone proves only that the caller can echo a
        value the browser attached for them. Comparing it to what the server stored at
        sign-in is what makes this a real check: a cross-origin attacker can neither read
        the readable CSRF cookie (wrong origin) nor set a custom header without a preflight
        the browser will refuse.
        """
        supplied = request.headers.get("x-csrf-token", "")
        expected = str(record.get("csrf") or "")
        if not supplied or not expected:
            return False
        return hmac.compare_digest(supplied.encode(), expected.encode())

    @staticmethod
    def _finish(response):
        for k, v in _SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        return response
