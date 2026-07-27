"""API hardening: security headers, optional bearer-token auth, per-IP rate limiting.

Defense-in-depth for a small internal tool:
- Security headers on every response (no sniffing, no framing, no referrer leakage).
- Optional shared-token auth: set API_AUTH_TOKEN and every /api/* request must send
  `Authorization: Bearer <token>`. Unset = open (local/dev use). Comparison is
  constant-time to avoid timing side channels.
- Sliding-window per-IP rate limit (in-memory; suitable for single-process deploys).
  Evaluate/solve are expensive (LLM + web calls), so they get a tighter budget.
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

API_AUTH_TOKEN = os.getenv("API_AUTH_TOKEN", "").strip()

# requests allowed per window (seconds) per client IP
RATE_DEFAULT = (int(os.getenv("RATE_LIMIT_DEFAULT", "120")), 60.0)
RATE_EXPENSIVE = (int(os.getenv("RATE_LIMIT_EXPENSIVE", "10")), 60.0)
_EXPENSIVE_PATHS = ("/api/evaluate", "/api/solve", "/api/ask")

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

    def _rate_limited(self, ip: str, path: str) -> bool:
        limit, window = RATE_EXPENSIVE if path in _EXPENSIVE_PATHS else RATE_DEFAULT
        bucket = "expensive" if path in _EXPENSIVE_PATHS else "default"
        now = time.monotonic()
        with self._lock:
            q = self._hits[(ip, bucket)]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                return True
            q.append(now)
        return False

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"

        if path.startswith("/api"):
            # optional shared-token auth (constant-time compare)
            if API_AUTH_TOKEN:
                supplied = request.headers.get("authorization", "")
                expected = f"Bearer {API_AUTH_TOKEN}"
                if not hmac.compare_digest(supplied.encode(), expected.encode()):
                    return self._finish(JSONResponse({"detail": "Unauthorized"}, status_code=401))
            if self._rate_limited(client_ip, path):
                return self._finish(JSONResponse(
                    {"detail": "Rate limit exceeded — slow down."}, status_code=429,
                    headers={"Retry-After": "60"}))

        response = await call_next(request)
        return self._finish(response)

    @staticmethod
    def _finish(response):
        for k, v in _SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        return response
