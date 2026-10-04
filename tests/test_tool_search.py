"""Semantic + word tool search (core/tool_search.py), and Empower's ranked tool list.

Word overlap alone showed Wandelbots — a robot-programming and simulation startup — a shortlist
without Tecnomatix, Process Simulate or SIMIT, but with a cybersecurity certification that shared
the word "industrial". These tests pin what fixed that and every way it falls back.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core import pillars, tool_search  # noqa: E402
from core.pillar_match import shortlist  # noqa: E402

CATALOG = {"available": True, "checksum": "abc", "entries": [
    {"id": "tool:process-simulate", "name": "Process Simulate", "category": "Tecnomatix", "division": "DI SW",
     "description": "Virtual commissioning and simulation of robotic and assembly manufacturing processes."},
    {"id": "tool:iec-62443", "name": "IEC 62443 Certification", "category": "Products", "division": "DI",
     "description": "Industrial cybersecurity certification for industrial automation systems."},
    {"id": "tool:scalance", "name": "SCALANCE X-400", "category": "Scalance", "division": "DI PA",
     "description": "Layer 3 switch for industrial networks."},
]}
# Two-dimensional "embeddings": robotics/simulation along x, networking/security along y.
VEC = {"Process Simulate": [1.0, 0.0], "IEC 62443 Certification": [0.1, 1.0], "SCALANCE X-400": [0.0, 1.0]}


class FakeEmbedder:
    available = True
    last_error = ""

    def __init__(self, query=(1.0, 0.1), fail=False):
        self.query, self.fail, self.calls = list(query), fail, 0

    def embedding_model(self):
        return "fake-embed"

    def embed(self, texts, dims=2, cache=True):
        self.calls += 1
        if self.fail:
            return None
        return [VEC.get(t.split(" | ")[0], self.query) for t in texts]


@pytest.fixture
def index_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(tool_search, "INDEX_DIR", tmp_path / "tool_index")
    monkeypatch.setattr(tool_search, "_dims", lambda: 2)
    tool_search._loaded.clear()
    yield tmp_path
    tool_search._loaded.clear()


def test_a_synonym_match_ranks_above_a_shared_generic_word(index_dir):
    tool_search.build_index(CATALOG, FakeEmbedder())
    ranked, why = tool_search.semantic_ranking("robot programming and simulation software", CATALOG, FakeEmbedder())
    assert why == "" and ranked[0] == "Process Simulate"


def test_fusion_keeps_an_exact_word_hit_and_admits_a_strong_semantic_match():
    words = ["IEC 62443 Certification", "SCALANCE X-400"]            # word overlap's own order
    fused = tool_search.fuse(words, ["Process Simulate", "SCALANCE X-400"], limit=3)
    assert set(fused) == {"IEC 62443 Certification", "SCALANCE X-400", "Process Simulate"}
    assert fused[0] == "SCALANCE X-400"                              # in both rankings: strongest


def test_only_the_top_of_each_ranking_is_fused(monkeypatch):
    monkeypatch.setattr(tool_search, "FUSE_DEPTH", 1)
    # "Generic" is first by words and last semantically: past the depth, it gains nothing extra.
    fused = tool_search.fuse(["Generic", "B"], ["Specific", "B", "Generic"], limit=2)
    assert fused == ["Generic", "Specific"] or fused == ["Specific", "Generic"]


def test_no_semantic_ranking_means_words_alone():
    assert tool_search.fuse(["A", "B", "C"], None, limit=2) == ["A", "B"]


@pytest.mark.parametrize("setup, reason", [
    ("missing", "no tool index"),
    ("stale", "no tool index"),
    ("embed_fails", "the embedding call failed"),
])
def test_every_fallback_says_why(index_dir, setup, reason):
    llm = FakeEmbedder(fail=(setup == "embed_fails"))
    if setup != "missing":
        tool_search.build_index(CATALOG, FakeEmbedder())
    catalog = {**CATALOG, "checksum": "changed"} if setup == "stale" else CATALOG
    ranked, why = tool_search.semantic_ranking("robot simulation", catalog, llm)
    assert ranked is None and reason in why


def test_a_provider_without_an_embedding_model_falls_back():
    class NoEmbed:
        available = True
    ranked, why = tool_search.semantic_ranking("robot simulation", CATALOG, NoEmbed())
    assert ranked is None and "no embedding model" in why


def test_the_empower_shortlist_takes_a_semantic_match_word_overlap_missed():
    concepts = {"technologies": [{"term": "industrial automation", "key": "industrial automation", "citations": ["E1"]}]}
    words_only = [t["name"] for t in shortlist("Empower", concepts, CATALOG, {})]
    assert "Process Simulate" not in words_only                        # shares no word with the concept
    hybrid = [t["name"] for t in shortlist("Empower", concepts, CATALOG, {}, semantic=["Process Simulate"])]
    assert "Process Simulate" in hybrid


# ------------------------------------------------------------------- Xcelerator neighbours (Connect)

XCEL = {"name": "xcelerator", "available": True, "checksum": "x1",
        "industries": [{"id": "industry:automotive", "name": "Automotive", "kind": "industry"}],
        "topics": [{"id": "topic:quality", "name": "Quality", "kind": "topic"}],
        "entries": [
            {"id": "seller:vision-qc", "name": "Vision QC", "industries": ["Automotive"], "topics": ["Quality"],
             "description": "Deep-learning visual inspection for car body shops."},
            {"id": "seller:door-access", "name": "Door Access", "industries": ["Commercial buildings"],
             "topics": ["Cybersecurity"], "description": "IP door access control."}]}
XVEC = {"Vision QC": [1.0, 0.0], "Door Access": [0.0, 1.0]}


class SellerEmbedder(FakeEmbedder):
    def embed(self, texts, dims=2, cache=True):
        return [XVEC.get(t.split(" | ")[0], self.query) for t in texts]


def test_the_xcelerator_index_is_its_own_index_and_finds_the_nearest_seller(index_dir, monkeypatch):
    monkeypatch.setattr(tool_search, "XCELERATOR_INDEX_DIR", index_dir / "xcelerator_index")
    tool_search.build_index(XCEL, SellerEmbedder())
    assert (index_dir / "xcelerator_index" / "meta.json").exists()
    assert not (index_dir / "tool_index").exists()                       # the tools index is untouched
    ranked, why = tool_search.semantic_ranking("car paint defect detection", XCEL, SellerEmbedder())
    assert why == "" and ranked[0] == "Vision QC"
    assert "Automotive" in tool_search.seller_text(XCEL["entries"][0])


def test_a_missing_xcelerator_index_says_how_to_build_it(index_dir, monkeypatch):
    monkeypatch.setattr(tool_search, "XCELERATOR_INDEX_DIR", index_dir / "nothing")
    ranked, why = tool_search.semantic_ranking("anything", XCEL, SellerEmbedder())
    assert ranked is None and "--catalog xcelerator" in why


def test_the_connect_shortlist_adds_a_semantic_neighbour_word_overlap_missed():
    concepts = {"capabilities": [{"term": "paint defect detection", "key": "paint defect detection", "citations": ["E1"]}]}
    words = [e["id"] for e in shortlist("Connect", concepts, XCEL, {})]
    assert "seller:vision-qc" not in words and words[:2] == ["industry:automotive", "topic:quality"]
    hybrid = [e["id"] for e in shortlist("Connect", concepts, XCEL, {}, semantic=["Vision QC"])]
    assert "seller:vision-qc" in hybrid


def test_only_good_cited_market_signals_become_citable_records():
    from core.pillar_match import market_records
    def run(size=None, cagr=None, peers=0):
        return {"trend": {"landscape": {
            "market_size": {"value": size, "cagr": cagr, "as_of": "2026", "source_url": "https://m.test"},
            "funded_peers": [{"company": f"P{i}", "round": "Seed", "source_url": "https://p.test"} for i in range(peers)]}}}
    assert [r["source"] for r in market_records(run("$20 billion", "12%"))] == ["market:size", "market:growth"]
    assert market_records(run("$300 million", "3%")) == []                   # small and slow: not good
    assert [r["source"] for r in market_records(run(peers=2))] == ["market:funded_peers"]
    blank = {"trend": {"landscape": {"funded_peers": [{"company": "UpcycleX", "round": None, "amount": "None",
                                                       "source_url": "https://p.test"}] * 2}}}
    assert "None" not in market_records(blank)[0]["text"]                     # a missing round says nothing
    assert market_records({"trend": {"landscape": {"market_size": {"value": "$20 billion", "cagr": "12%"}}}}) == []  # uncited


# ------------------------------------------------------------------- department needs (Collaborate)

def _needs(n):
    return {"name": "department_needs", "available": True, "entries": [
        {"id": f"need:m-{i}", "name": f"Need {i}", "category": "c", "description": "generic data platform",
         "keywords": ["data"]} for i in range(n)]}


def test_a_need_close_in_meaning_reaches_the_shortlist_word_overlap_left_out():
    # 20 needs, more than the 15 the model is shown; the one the startup answers shares no word.
    concepts = {"capabilities": [{"term": "data", "key": "data", "citations": ["E1"]}]}
    catalog = _needs(20)
    catalog["entries"][19].update(name="Track wear detection", description="detect rail wear", keywords=[])
    words = [e["id"] for e in shortlist("Collaborate", concepts, catalog, {})]
    assert "need:m-19" not in words and len(words) == 15
    hybrid = [e["id"] for e in shortlist("Collaborate", concepts, catalog, {}, semantic=["need:other-dept", "need:m-19"])]
    assert hybrid[0] == "need:m-19" and len(hybrid) == 15


def test_within_the_limit_every_need_is_kept_and_the_closest_comes_first():
    catalog = _needs(6)
    out = [e["id"] for e in shortlist("Collaborate", {}, catalog, {}, semantic=["need:m-4"])]
    assert out[0] == "need:m-4" and sorted(out) == sorted(e["id"] for e in catalog["entries"])


def test_the_needs_index_covers_every_departments_stated_needs():
    from core import catalogs
    cat = catalogs.needs_index_catalog()
    if not cat["available"]:
        pytest.skip("requirements workbook not present")
    assert len(cat["entries"]) >= 40 and len({e["name"] for e in cat["entries"]}) == len(cat["entries"])
    assert {"Smart Infrastructure", "Siemens Mobility", "Digital Industries"} <= {e["department"] for e in cat["entries"]}
    assert "Mobility" in tool_search.need_text(next(e for e in cat["entries"] if e["department"] == "Siemens Mobility"))


# ------------------------------------------------------------------------- ranked tool list

EVIDENCE = {"E1": {"id": "E1", "quote": "robot programming"}}
IDS = {e["id"]: e for e in CATALOG["entries"]}


def test_ranked_tools_are_held_to_the_criteria_bar_and_capped_at_five():
    raw = {"recommended_tools": [
        {"catalog_id": "tool:process-simulate", "relation": "complement", "reason": "Simulates the robots it programs.", "citations": ["E1"]},
        {"catalog_id": "tool:not-shortlisted", "relation": "complement", "reason": "x", "citations": ["E1"]},
        {"catalog_id": "tool:scalance", "relation": "friend", "reason": "x", "citations": ["E1"]},
        {"catalog_id": "tool:iec-62443", "relation": "adjacent", "reason": "", "citations": ["E1"]},
        {"catalog_id": "tool:iec-62443", "relation": "adjacent", "reason": "Secures the cell.", "citations": ["E9"]},
        {"catalog_id": "tool:process-simulate", "relation": "complement", "reason": "duplicate", "citations": ["E1"]},
    ]}
    tools = pillars._recommended_tools(raw, EVIDENCE, IDS)
    assert [(t["name"], t["rank"]) for t in tools] == [("Process Simulate", 1)]
    many = {"recommended_tools": [{"catalog_id": f"tool:t{i}", "relation": "adjacent", "reason": "r", "citations": ["E1"]}
                                  for i in range(8)]}
    ids = {f"tool:t{i}": {"id": f"tool:t{i}", "name": f"T{i}"} for i in range(8)}
    assert len(pillars._recommended_tools(many, EVIDENCE, ids)) == 5


def test_a_ranked_tool_that_cannot_be_found_is_dropped_without_another_model_call(monkeypatch):
    from core import pillar_match, tool_check
    result = {"status": "assessed", "criteria": [{"catalog": [IDS["tool:process-simulate"]]}],
              "recommended_tools": [{**IDS["tool:process-simulate"], "rank": 1}, {**IDS["tool:scalance"], "rank": 2}]}
    monkeypatch.setattr(tool_check, "verify_tools", lambda entries, llm: {
        e["id"]: {"id": e["id"], "name": e["name"], "status": "not_found" if e["id"] == "tool:scalance" else "verified"}
        for e in entries})
    rematches = []
    monkeypatch.setattr(pillar_match, "deep_match", lambda *a, **k: rematches.append(1))
    out = pillar_match._with_real_tools(result, CATALOG["entries"], {}, [], None, None, {})
    assert rematches == []
    assert [(t["name"], t["rank"], t["check"]) for t in out["recommended_tools"]] == [("Process Simulate", 1, "verified")]


def test_sfs_reads_only_the_first_three_fit_matches():
    """Fit now lists up to five tools; the SFS rules must not see words from the fourth and fifth."""
    import pandas as pd
    from core.programs import _startup_text
    fit = {"matches": [{"rationale": f"reason-{i}"} for i in range(5)]}
    text = _startup_text(pd.Series(dtype=str), {}, fit)
    assert all(f"reason-{i}" in text for i in range(3))
    assert "reason-3" not in text and "reason-4" not in text
