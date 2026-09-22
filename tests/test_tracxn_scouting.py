"""Provider routing and per-user OAuth tests. No live paid services required."""
import time
import json
from urllib.parse import parse_qs, urlsplit
from unittest.mock import Mock

import pytest

from core import solve
from core.tracxn import companies_from_payload
from api import tracxn
from api.auth import Principal, sessions


def candidate(name="Alpha", **kwargs):
    return {"name": name, "description": "industrial inspection", "website": "https://alpha.example", "source": "tracxn", **kwargs}


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr(solve, "save_challenge", lambda *a: None)
    monkeypatch.setattr(solve, "_derive_keywords", lambda *a: ["industrial inspection"])
    monkeypatch.setattr(solve, "_rank", lambda p, cs, llm: [{**c, "relevance": 80} for c in cs])
    gd, web = Mock(return_value=[]), Mock(return_value=[])
    monkeypatch.setattr(solve, "_glassdollar_candidates", gd)
    monkeypatch.setattr(solve, "_web_candidates", web)
    return gd, web


def test_complete_tracxn_skips_glassdollar_and_web(setup):
    gd, web = setup
    client = Mock(); client.search.return_value = [candidate(str(i)) for i in range(5)]
    result = solve.solve_problem("industrial inspection", tracxn=client)
    assert len(result["candidates"]) == 5
    gd.assert_not_called(); web.assert_not_called()


@pytest.mark.parametrize("response", [[], RuntimeError("provider down")])
def test_tracxn_miss_or_failure_falls_back_to_glassdollar(setup, response):
    gd, web = setup
    gd.return_value = [candidate(str(i), source="glassdollar") for i in range(5)]
    client = Mock()
    if isinstance(response, Exception):
        client.search.side_effect = response
    else:
        client.search.return_value = response
    result = solve.solve_problem("industrial inspection", tracxn=client)
    gd.assert_called_once(); web.assert_not_called()
    assert all(c["source"] == "glassdollar" for c in result["candidates"])


def test_web_only_when_needed_and_enabled(setup):
    gd, web = setup
    solve.solve_problem("industrial inspection", do_web=False)
    gd.assert_called_once(); web.assert_not_called()
    solve.solve_problem("industrial inspection")
    web.assert_called_once()


def test_bad_llm_rank_indices_and_scores_do_not_crash_or_duplicate():
    llm = Mock(available=True)
    llm.complete.return_value = json.dumps({"ranked": [{"index": -1, "relevance": 90},
        {"index": 0, "relevance": "bad"}, {"index": 0, "relevance": 75},
        {"index": 0, "relevance": 99}, {"index": 55, "relevance": 99}]})
    assert [c["relevance"] for c in solve._rank("inspection", [candidate()], llm)] == [75]


def test_valid_empty_llm_ranking_does_not_resurrect_irrelevant_candidates():
    llm = Mock(available=True)
    llm.complete.return_value = json.dumps({"ranked": []})
    assert solve._rank("industrial inspection", [candidate()], llm) == []


def test_structured_and_json_text_mcp_records():
    data = {"companies": [{"companyName": "Alpha", "shortDescription": "Inspection", "domain": "alpha.example"}]}
    import json
    for payload in (data, [{"type": "text", "text": json.dumps(data)}]):
        result = companies_from_payload(payload)
        assert result[0]["source"] == "tracxn"
        assert result[0]["name"] == "Alpha"
    assert companies_from_payload([{"type": "text", "text": "Alpha may have raised $10M"}]) == []


def user(oid):
    return Principal(oid=oid, name=oid, upn=f"{oid}@example.com", email=f"{oid}@example.com", tid="test")


def test_tokens_are_per_user_and_expiry_is_respected():
    a, b = user("tracxn-a"), user("tracxn-b")
    sessions().put(tracxn._key(a), {"access_token": "private", "expires_at": time.time() + 30}, 60)
    assert tracxn.status(a)["connected"]
    assert not tracxn.status(b)["connected"]
    assert tracxn.client_for(b) is None
    tracxn.disconnect(a)
    assert tracxn.client_for(a) is None


def test_oauth_state_is_bound_to_user_and_pkce_is_exchanged(monkeypatch):
    monkeypatch.setenv("TRACXN_REDIRECT_URI", "http://localhost:5173/api/integrations/tracxn/callback")
    post = Mock(side_effect=[{"client_id": "registered"}, {"access_token": "secret", "token_type": "Bearer", "expires_in": 300}])
    monkeypatch.setattr(tracxn, "_post", post)
    a, b = user("oauth-a"), user("oauth-b")
    params = parse_qs(urlsplit(tracxn.connect(a)["url"]).query)
    assert params["code_challenge_method"] == ["S256"]
    state = params["state"][0]
    with pytest.raises(Exception) as exc:
        tracxn.callback(state, "code", "", tracxn.MCP_URL, b)
    assert exc.value.status_code == 400
    response = tracxn.callback(state, "code", "", tracxn.MCP_URL, a)
    assert "connected" in response.headers["location"]
    assert len(post.call_args.kwargs["data"]["code_verifier"]) >= 43
    assert "access_token" not in tracxn.status(a)
    with pytest.raises(Exception):
        tracxn.callback(state, "code", "", tracxn.MCP_URL, a)
    tracxn.disconnect(a)


def test_wrong_issuer_rejected_without_token_exchange(monkeypatch):
    a = user("issuer-test")
    sessions().put("tracxn:flow:issuer", {"oid": a.oid}, 60)
    post = Mock(); monkeypatch.setattr(tracxn, "_post", post)
    result = tracxn.callback("issuer", "code", "", "https://other.example", a)
    assert "failed" in result.headers["location"]
    post.assert_not_called()


def test_private_research_bypasses_shared_cache_reads_and_writes(monkeypatch):
    from core import web
    read, write = Mock(return_value="other user's result"), Mock()
    monkeypatch.setattr(web, "_cache_get", read)
    monkeypatch.setattr(web, "_cache_put", write)
    monkeypatch.setattr(web, "_cache_entry", None)
    token = web.set_cache_private(True)
    try:
        assert web._cached("llm", "key") is None
        web._store("llm", "key", "licensed result")
    finally:
        web.reset_cache_private(token)
    read.assert_not_called(); write.assert_not_called()
    assert web._cached("llm", "key") == "other user's result"


def test_mcp_negotiates_session_and_uses_discovered_schema(monkeypatch):
    from core.tracxn import TracxnClient
    client = TracxnClient("never-log-this")
    rpc = Mock(side_effect=[{"protocolVersion": "2025-03-26"}, {},
        {"tools": [{"name": "search_companies", "inputSchema": {
            "type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}]},
        {"structuredContent": {"companies": [{"name": "Alpha", "description": "Inspection"}]}}])
    monkeypatch.setattr(client, "_rpc", rpc)
    assert client.search("inspection")[0]["name"] == "Alpha"
    assert rpc.call_args.args == ("tools/call", {"name": "search_companies", "arguments": {"query": "inspection"}})
    assert client.http.headers["MCP-Protocol-Version"] == "2025-03-26"


def test_mcp_rejects_mutating_tools(monkeypatch):
    from core.tracxn import TracxnClient, TracxnError
    client = TracxnClient("never-log-this")
    rpc = Mock(side_effect=[{}, {}, {"tools": [{"name": "search_companies",
        "annotations": {"destructiveHint": True}, "inputSchema": {}}]}])
    monkeypatch.setattr(client, "_rpc", rpc)
    with pytest.raises(TracxnError):
        client.search("inspection")
    assert all(call.args[0] != "tools/call" for call in rpc.call_args_list)
