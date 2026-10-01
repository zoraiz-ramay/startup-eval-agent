"""Empower recommends only Siemens tools a web search can find (core/tool_check.py).

A catalog row can be a renamed product or a typo. What is pinned: a tool the search says does not
exist is replaced by another match; a tool that simply could not be checked is kept (that is no
evidence against it); and every check is recorded so the admin page can list the missing ones.
"""
from unittest.mock import Mock

import pytest

from core import pillar_match as pm
from core import tool_check as T


@pytest.fixture(autouse=True)
def no_cache(monkeypatch):
    monkeypatch.setattr(T.web, "_cached", lambda *a, **k: None)
    monkeypatch.setattr(T.web, "_store", lambda *a, **k: None)


def searcher(found: dict):
    llm = Mock(available=True)
    def web_answer(prompt, **k):
        name = next(n for n in found if f'"{n}"' in prompt)
        if found[name] is None:
            return None
        return {"text": ("FOUND\nIt is a Siemens simulation tool." if found[name] else "NOT FOUND\nNo such product."),
                "sources": [{"title": "siemens.com", "url": "https://siemens.com/x"}] if found[name] else []}
    llm.web_answer.side_effect = web_answer
    return llm


@pytest.mark.parametrize("found, status", [(True, "verified"), (False, "not_found"), (None, "unchecked")])
def test_a_tool_is_verified_not_found_or_unchecked(found, status):
    out = T.verify_tool({"id": "tool:x", "name": "Simcenter X"}, searcher({"Simcenter X": found}))
    assert out["status"] == status
    assert (out["url"] == "https://siemens.com/x") is (status == "verified")


def tool(i, name):
    return {"id": f"tool:{i}", "name": name, "category": "c", "description": "d"}


def pillar(tools):
    return {"status": "assessed", "total": 8, "criteria": [{"id": "tool_fit", "catalog": tools}, {"id": "benefit_fit", "catalog": []},
            {"id": "actionability", "catalog": []}], "notes": []}


def test_a_tool_that_does_not_exist_is_replaced_by_another_match(monkeypatch):
    ghost, real = tool("ghost", "Ghost Suite"), tool("real", "Simcenter Amesim")
    seen_shortlists = []
    def rematch(p, concepts, entries, *a):
        seen_shortlists.append([e["id"] for e in entries])
        return pillar([real])
    monkeypatch.setattr(pm, "deep_match", rematch)
    out = pm._with_real_tools(pillar([ghost]), [ghost, real], {}, [], searcher({"Ghost Suite": False, "Simcenter Amesim": True}), None, {})
    assert seen_shortlists == [["tool:real"]]                       # the missing tool is out of the shortlist
    assert [e["id"] for e in pm._cited_tools(out)] == ["tool:real"]
    checks = {c["id"]: c for c in out["tool_checks"]}
    assert checks["tool:ghost"]["status"] == "not_found" and checks["tool:ghost"]["replaced"] is True
    assert checks["tool:real"]["status"] == "verified"
    assert "Ghost Suite" in out["notes"][-1]


def test_a_tool_that_could_not_be_checked_is_kept(monkeypatch):
    t = tool("x", "Opcenter")
    monkeypatch.setattr(pm, "deep_match", lambda *a: pytest.fail("no re-match without evidence the tool is missing"))
    out = pm._with_real_tools(pillar([t]), [t], {}, [], searcher({"Opcenter": None}), None, {})
    assert pm._cited_tools(out) == [t] and out["tool_checks"][0]["status"] == "unchecked"
