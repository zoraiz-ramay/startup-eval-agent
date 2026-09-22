"""Per-user Tracxn OAuth with PKCE. Tokens use the existing Redis session store,
never SQLite (which is synced to S3) or browser storage.
"""
from __future__ import annotations

import base64
import hashlib
import os
import secrets
import time
from urllib.parse import urlencode, urlsplit

import requests
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from api.auth import Principal, current_user, sessions
from core.tracxn import MCP_URL, TracxnClient

router = APIRouter(prefix="/api/integrations/tracxn", tags=["integrations"])
AUTH_BASE = "https://platform.tracxn.com/auth/2.0/mcp"
TTL = 30 * 86400


def _key(user):
    return f"tracxn:account:{user.oid}"


def _redirect_uri():
    uri = os.getenv("TRACXN_REDIRECT_URI", "").strip()
    parsed = urlsplit(uri)
    if not (parsed.scheme == "https" or (parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1"))):
        raise HTTPException(503, "Set TRACXN_REDIRECT_URI to this app's Tracxn callback URL.")
    if parsed.path != "/api/integrations/tracxn/callback" or parsed.query or parsed.fragment:
        raise HTTPException(503, "TRACXN_REDIRECT_URI must end with /api/integrations/tracxn/callback.")
    return uri


def _post(path, **kwargs):
    response = requests.post(AUTH_BASE + path, timeout=12, **kwargs)
    response.raise_for_status()
    return response.json()


@router.get("")
def status(user: Principal = Depends(current_user)):
    record = sessions().get(_key(user)) or {}
    return {"connected": bool(record.get("access_token") and record.get("expires_at", 0) > time.time()),
            "configured": bool(os.getenv("TRACXN_REDIRECT_URI", "").strip())}


@router.post("/connect")
def connect(user: Principal = Depends(current_user), return_to: str = "workspace"):
    redirect = _redirect_uri()
    try:
        client = _post("/register", json={"client_name": "Siemens Startup Evaluation Agent",
            "redirect_uris": [redirect], "grant_types": ["authorization_code"],
            "response_types": ["code"], "token_endpoint_auth_method": "none"})
        client_id = client["client_id"]
    except (requests.RequestException, ValueError, KeyError):
        raise HTTPException(502, "Tracxn sign-in is unavailable. Please try again later.") from None
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    sessions().put(f"tracxn:flow:{state}", {"oid": user.oid, "verifier": verifier,
                   "client_id": client_id, "redirect": redirect, "return_to": "/" if return_to == "home" else "/workspace"}, 300)
    return {"url": AUTH_BASE + "/authorize?" + urlencode({"response_type": "code",
        "client_id": client_id, "redirect_uri": redirect, "scope": "read", "state": state,
        "code_challenge": challenge, "code_challenge_method": "S256", "resource": MCP_URL})}


@router.get("/callback")
def callback(state: str = "", code: str = "", error: str = "", iss: str = "",
             user: Principal = Depends(current_user)):
    flow_key = f"tracxn:flow:{state}"
    flow = sessions().get(flow_key) if state else None
    if not flow or flow.get("oid") != user.oid:
        raise HTTPException(400, "Tracxn sign-in expired or belongs to another user. Connect again.")
    sessions().delete(flow_key)
    if error or not code or iss != MCP_URL:
        return RedirectResponse(flow.get("return_to", "/workspace") + "?tracxn=failed", status_code=303)
    try:
        token = _post("/token", data={"grant_type": "authorization_code", "code": code,
            "client_id": flow["client_id"], "redirect_uri": flow["redirect"],
            "code_verifier": flow["verifier"], "resource": MCP_URL})
        if not token.get("access_token") or token.get("token_type", "").lower() != "bearer":
            raise ValueError("Invalid token")
        # Tracxn currently advertises authorization_code only, so expiry requires reconnect.
        lifetime = min(TTL, max(1, int(token.get("expires_in", 3600))))
        sessions().put(_key(user), {"access_token": token["access_token"],
                       "expires_at": time.time() + lifetime}, lifetime)
    except (requests.RequestException, ValueError, TypeError):
        return RedirectResponse(flow.get("return_to", "/workspace") + "?tracxn=failed", status_code=303)
    return RedirectResponse(flow.get("return_to", "/workspace") + "?tracxn=connected", status_code=303)


@router.delete("")
def disconnect(user: Principal = Depends(current_user)):
    sessions().delete(_key(user))
    return {"connected": False}


def client_for(user, llm=None):
    record = sessions().get(_key(user)) or {}
    if record.get("access_token") and record.get("expires_at", 0) > time.time():
        return TracxnClient(record["access_token"], llm=llm)
    return None
