"""Behaviour of the sign-in guard.

These assert against real HTTP responses rather than the shape of the source, because the
question that matters is whether an unauthenticated caller can reach the data — not whether
a particular function appears in a particular file.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.auth import ClaimsError, map_entra_error, validate_claims
from api.main import app

TENANT = "11111111-2222-3333-4444-555555555555"


@pytest.fixture()
def anon() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def signed_in() -> TestClient:
    client = TestClient(app)
    client.get("/api/auth/login", follow_redirects=False)
    return client


# ----------------------------------------------------------------- the guard

def test_api_requires_a_session(anon):
    res = anon.get("/api/runs")
    assert res.status_code == 401
    assert res.json()["code"] == "unauthenticated"


def test_health_stays_open_and_says_nothing_useful(anon):
    """The Docker healthcheck and the load balancer both hit this unauthenticated.

    It used to report the S3 bucket, the LLM provider and model, and which keys were
    configured — reconnaissance for anyone who found the hostname.
    """
    res = anon.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_status_carries_the_diagnostics_but_needs_a_session(anon, signed_in):
    assert anon.get("/api/status").status_code == 401
    body = signed_in.get("/api/status").json()
    assert "llm_provider" in body
    # A bucket name is a target, and no reviewer can act on it.
    assert "s3_bucket" not in body


def test_me_answers_200_when_signed_out(anon):
    """First paint depends on this. A 401 here would make the SPA's opening request an
    error and collide with the global 401 handler."""
    res = anon.get("/api/auth/me")
    assert res.status_code == 200
    assert res.json()["authenticated"] is False


def test_sign_in_then_read(signed_in):
    assert signed_in.get("/api/runs").status_code == 200
    body = signed_in.get("/api/auth/me").json()
    assert body["authenticated"] is True
    assert body["user"]["initials"] == "ER"


def test_logout_ends_the_session(signed_in):
    csrf = signed_in.cookies.get("sea_csrf")
    assert signed_in.post("/api/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 200
    assert signed_in.get("/api/runs").status_code == 401


def test_docs_are_gated(anon):
    """Swagger's "Try it out" runs same-origin fetches that would carry the session
    cookie, so it cannot be left open next to a cookie-authenticated API."""
    assert anon.get("/openapi.json").status_code == 401


# ----------------------------------------------------------------- CSRF

def test_write_without_csrf_token_is_refused(signed_in):
    res = signed_in.post("/api/runs/1/override",
                         json={"new_pillar": "Connect", "reason": "no csrf token here"})
    assert res.status_code == 403
    assert res.json()["code"] == "csrf"


def test_write_with_wrong_csrf_token_is_refused(signed_in):
    res = signed_in.post("/api/runs/1/override",
                         json={"new_pillar": "Connect", "reason": "wrong csrf token"},
                         headers={"X-CSRF-Token": "not-the-real-token"})
    assert res.status_code == 403


def test_reads_do_not_need_a_csrf_token(signed_in):
    assert signed_in.get("/api/runs").status_code == 200


# ----------------------------------------------------------------- claims

def test_claims_from_another_tenant_are_rejected():
    with pytest.raises(ClaimsError) as exc:
        validate_claims({"tid": "00000000-0000-0000-0000-000000000999",
                         "oid": "abc", "name": "Mallory"}, TENANT)
    assert exc.value.code == "tenant_mismatch"


def test_claims_without_an_oid_are_rejected():
    """oid is the only stable identifier; names and addresses change. Without it there is
    nothing durable to attribute an override to."""
    with pytest.raises(ClaimsError) as exc:
        validate_claims({"tid": TENANT, "name": "No Object Id"}, TENANT)
    assert exc.value.code == "missing_oid"


def test_valid_claims_become_a_principal():
    principal = validate_claims(
        {"tid": TENANT, "oid": "9f", "name": "Ada Lovelace",
         "preferred_username": "ada@siemens.com"}, TENANT)
    assert principal.oid == "9f"
    assert principal.initials == "AL"
    assert principal.source == "entra"


# ----------------------------------------------------------------- error mapping

@pytest.mark.parametrize("description,expected", [
    ("AADSTS53000: Device is not compliant.", "device_not_compliant"),
    ("AADSTS53001: Device is not domain joined.", "device_not_trusted"),
    ("AADSTS53003: Access has been blocked by Conditional Access policies.", "access_blocked"),
    ("AADSTS50105: The signed in user is not assigned to a role.", "not_assigned"),
    ("AADSTS50011: The redirect URI does not match.", "config_error"),
    ("AADSTS7000215: Invalid client secret provided.", "config_error"),
    ("AADSTS99999: Something new Microsoft added.", "unknown"),
])
def test_entra_errors_map_to_actionable_codes(description, expected):
    assert map_entra_error("invalid_request", description) == expected


def test_user_cancellation_is_not_reported_as_a_failure():
    assert map_entra_error("access_denied", "the user cancelled") == "cancelled"
