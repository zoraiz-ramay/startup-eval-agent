"""Tests for the recall fixes on profile research queries and the profile backfill.

A bare company name is often ambiguous — "Phena" collides with Tryphena, Phena International
Ltd and Phena's Studio — so the identity-sensitive searches came back as noise, which is
indistinguishable downstream from "the web knows nothing about this company". Pinning those
queries to the company's own domain is what surfaces its LinkedIn ("Company size 2-10
employees") and CB Insights ("founded in 2026") entries.

Requires pandas; run in the app environment.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.profile import _queries, _site_hint, _corpus, _clean_source_url  # noqa: E402
from core.pipeline import backfill_profile  # noqa: E402
from core.score import score_startup  # noqa: E402


class _NoLLM:
    """Keeps _queries on its deterministic base wave (no LLM-suggested extras)."""
    available = False


def test_site_hint_normalises_domain_and_website():
    assert _site_hint(pd.Series({"domain": "phena.tech"})) == "phena.tech"
    assert _site_hint(pd.Series({"website": "https://www.phena.tech/"})) == "phena.tech"
    assert _site_hint(pd.Series({"domain": "", "website": "http://acme.io/about"})) == "acme.io"
    assert _site_hint(pd.Series({"company_name": "Acme"})) == ""


def test_identity_sensitive_queries_carry_the_domain():
    q = _queries("Phena", pd.Series({"company_name": "Phena", "domain": "phena.tech"}), _NoLLM())
    assert "phena.tech" in q["team"]
    assert "phena.tech" in q["corp_programs"]
    assert "phena.tech" in q["founded"]
    # Name-only searches already resolve well and the wave is budget-sensitive, so they
    # deliberately stay unqualified.
    assert "phena.tech" not in q["founders"]
    assert "phena.tech" not in q["customers"]


def test_founded_year_query_exists():
    """Nothing searched for the founding year before, so it was only ever picked up by
    accident from whatever the other queries happened to return."""
    q = _queries("Acme", pd.Series({"company_name": "Acme", "domain": "acme.io"}), _NoLLM())
    assert "founded" in q
    assert "founded" in q["founded"].lower()


def test_funding_query_exists():
    """Nothing searched for the funding round, so Crunchbase rounds were only ever found by
    accident — makkook.ai's Pre-Seed never surfaced at all."""
    q = _queries("Acme", pd.Series({"company_name": "Acme", "domain": "acme.io"}), _NoLLM())
    assert "funding" in q
    assert "acme.io" in q["funding"]
    assert "funding" in q["funding"].lower()


def test_clean_source_url_rejects_non_links():
    """Asked for a source_url the model sometimes answers with the corpus label it read the
    fact from ('f1, f2'), which the UI would render as a broken 'web-sourced' link."""
    assert _clean_source_url("https://www.crunchbase.com/organization/makkook-ai") == \
        "https://www.crunchbase.com/organization/makkook-ai"
    assert _clean_source_url("http://x.io/a") == "http://x.io/a"
    for junk in ("f1, f2", "crunchbase", "", None, "  ", "www.crunchbase.com"):
        assert _clean_source_url(junk) == ""


def _score_with(row_funding, profile_funding):
    row = pd.Series({"company_name": "Acme", "funding": row_funding})
    profile = {"founders": [], "advisors": [], "programs": [], "parent_group": "",
               "funding": profile_funding}
    return score_startup(row, {"facts": []}, {}, {}, profile)


def test_researched_funding_reaches_the_score():
    """score_startup read only the DB row, so a web-found round changed nothing — even though
    the profile header already displayed it."""
    blank = _score_with("", "")
    researched = _score_with("", "Pre-Seed, amount undisclosed")
    assert researched["dimensions"]["market"] > blank["dimensions"]["market"]
    assert researched["dimensions"]["traction"] > blank["dimensions"]["traction"]


def test_stage_only_funding_counts():
    """A paywalled amount still evidences a raise; the stage alone must register."""
    assert _score_with("", "Pre-Seed, amount undisclosed")["dimensions"]["market"] > \
        _score_with("", "")["dimensions"]["market"]


def test_a_bigger_round_is_a_bigger_signal_than_a_smaller_one():
    """Funding used to be a yes/no, so a pre-seed and a $200M round scored identically."""
    small = _score_with("", "Pre-Seed, amount undisclosed")["dimensions"]
    large = _score_with("", "Series C, $200M")["dimensions"]
    assert large["market"] > small["market"]
    assert large["traction"] > small["traction"]


def test_database_funding_stays_authoritative():
    """Where the application data has a value it wins over research."""
    row = pd.Series({"company_name": "Acme", "funding": "Series B, $30M"})
    profile = {"founders": [], "advisors": [], "programs": [], "parent_group": "",
               "funding": "Pre-Seed, amount undisclosed"}
    scored = score_startup(row, {"facts": []}, {}, {}, profile)["dimensions"]
    assert scored == _score_with("Series B, $30M", "")["dimensions"]
    assert scored["market"] != _score_with("", "Pre-Seed, amount undisclosed")["dimensions"]["market"]


def test_knowledge_gapfill_never_invents_verifiable_facts():
    """Model-recall gap-fill must not touch facts a reader would cite.

    It used to cover funding/founded_year/employees/hq/customers, and asked to recall a small
    startup the model invents rather than declining: makkook.ai came back with a funding round
    of 'SAR 3.75 million' that appears nowhere on the web. The marker meant to flag such values
    never reached the row, so a guess rendered exactly like a cited fact.
    """
    import inspect

    from core import data as data_mod

    src = inspect.getsource(data_mod.web_profile_row)
    gap = src.split("_GAP_KEYS = ")[1].split(")")[0]
    for verifiable in ("funding", "founded_year", "employees", "hq", "customers", "website"):
        assert verifiable not in gap, f"{verifiable} must not be filled from model memory"


def test_queries_degrade_cleanly_without_a_domain():
    """No domain must mean today's behaviour, not a query with a dangling space."""
    q = _queries("Acme", pd.Series({"company_name": "Acme"}), _NoLLM())
    assert q["team"].startswith("Acme ")
    assert "  " not in q["team"]
    for text in q.values():
        assert text == text.strip()


def test_thinking_models_get_completion_headroom(monkeypatch):
    """Reasoning tokens are billed against max_completion_tokens before any answer is emitted.

    Sizing the budget for the answer alone let thinking consume it, so the reply came back
    truncated mid-token; parse_json then rejected it and every profile silently fell back to
    method='offline_keyword' — no founders, no headcount, no founding year. The request itself
    succeeds in that scenario, so last_error stays empty and nothing surfaces the failure.
    """
    from core import llm as llm_mod

    seen = {}

    class _FakeCompletions:
        def create(self, **kwargs):
            seen.update(kwargs)
            raise RuntimeError("stop here — we only care about the budget")

    client = llm_mod.LLMClient.__new__(llm_mod.LLMClient)
    client.available, client.model, client.last_error = True, "gemini-2.5-flash", ""
    client._client = type("C", (), {"chat": type("Ch", (), {"completions": _FakeCompletions()})()})()

    client.provider = "gemini"
    monkeypatch.setattr(llm_mod, "MAX_RETRIES", 1)
    client.complete("hi", max_tokens=1200)
    assert seen["max_completion_tokens"] == 1200 + llm_mod.LLM_THINKING_HEADROOM

    client.provider = "openai"          # non-reasoning gateway keeps the plain budget
    client.complete("hi", max_tokens=1200)
    assert seen["max_completion_tokens"] == 1200


def _hits(key, n, size=400):
    return [{"title": f"{key}-{i}", "body": "x" * size, "href": f"https://e/{key}/{i}"}
            for i in range(n)]


def test_corpus_gives_every_query_a_share_of_the_budget(monkeypatch):
    """Truncation must cost each query equally, not erase the tail wholesale.

    Concatenating key by key spent the whole budget on whichever queries came first in the
    dict — for a real 11-query wave only the first four keys reached the model, so headcount
    and founding year were dropped before extraction even though the searches had found them.
    """
    monkeypatch.setattr("core.profile._CORPUS_CHARS", 4000)
    results = {k: _hits(k, 4) for k in
               ("founders", "advisors", "programs", "parent", "team", "founded", "customers")}
    text = _corpus(results)
    represented = {line.split("]")[0][1:] for line in text.splitlines() if line.startswith("[")}
    assert represented == set(results)          # every query survives, including the last
    assert len(text) <= 4000


def test_corpus_puts_the_companys_own_pages_first():
    """Own-site evidence is the highest-signal input, so it must not be the first thing cut."""
    results = {"founders": _hits("founders", 2), "__site__0": _hits("__site__0", 1)}
    assert _corpus(results).splitlines()[0].startswith("[__site__0]")


def test_corpus_handles_empty_and_missing_hits():
    assert _corpus({}) == ""
    assert _corpus({"a": [], "b": None}) == ""


def test_employees_backfills_into_the_profile():
    """deep_profile.employees must reach profile['employees_count'] for API consumers.

    The UI falls back to deep_profile, but /api/evaluate consumers read the profile block,
    where a researched headcount used to vanish because only founded_year and funding were
    backfilled.
    """
    profile = {"employees_count": "", "founded_year": ""}
    sources = backfill_profile(
        profile,
        {"employees": "2-10", "founded_year": "2026", "founded_year_source": "https://x/y"})
    assert profile["employees_count"] == "2-10"
    assert profile["founded_year"] == "2026"
    # Headcount has no *_source key, so the origin is still recorded with an empty URL.
    assert sources["employees_count"] == {"origin": "web", "url": ""}
    assert sources["founded_year"]["url"] == "https://x/y"


def test_backfill_never_overwrites_database_values():
    """Wherever the application data has a value it stays authoritative."""
    profile = {"employees_count": "500", "founded_year": "2011"}
    sources = backfill_profile(profile, {"employees": "2-10", "founded_year": "2026"})
    assert profile == {"employees_count": "500", "founded_year": "2011"}
    assert sources == {}
