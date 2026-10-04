"""The model half of Siemens Fit, driven end to end by a scripted fake model.

The fake answers the concept prompt and each pillar's match prompt the way a well-behaved model
would, picking catalog ids out of the shortlist it was actually shown — so these tests exercise
the real shortlisting, validation, catalog checksums and route, with nothing but the model faked.
"""
import json
import re

import pytest

from core import catalogs, pillar_match
from core.pillars import ORDER

RUN = {"company": "Acme Vision",
       "summary": "AI visual inspection software for automotive factories using computer vision."}
DEPT = {"id": "di", "label": "Digital Industries", "interests": ["inspection", "automation"], "demo": True}


class FakeLLM:
    available = True

    def __init__(self, concepts=None, strong=True):
        self.concepts = concepts
        self.strong = strong
        self.prompts = []

    def complete(self, prompt, **_):
        self.prompts.append(prompt)
        if "list its concepts in these groups" in prompt:
            ids = re.findall(r'"id":"([ES]\d+)"', prompt)
            cite = [ids[1] if len(ids) > 1 else ids[0]] if ids else []
            data = self.concepts if self.concepts is not None else {
                "technologies": [{"term": "computer vision", "citations": cite}],
                "capabilities": [{"term": "visual inspection", "citations": cite}],
                "needs_gaps": [{"term": "simulation", "citations": cite}],
                "use_cases": [{"term": "quality inspection", "citations": cite}],
                "industries": [{"term": "automotive", "citations": cite}],
                "topics": [{"term": "quality", "citations": cite}]}
            return json.dumps(data)
        pillar = re.search(r"Assess the startup's (\w+) fit", prompt).group(1)
        entry = re.search(r"^((?:tool|need|industry|seller|topic):[a-z0-9-]+) \| ([^|\n]+)", prompt, re.M)
        cat_id, name = entry.group(1), entry.group(2).strip()
        cite = re.findall(r'"id":"(E\d+)"', prompt)[:1]
        keys = {"Empower": ("tool_fit", "benefit_fit", "actionability"),
                "Collaborate": ("capability_fit", "need_fit", "actionability"),
                "Connect": ("ecosystem_gap", "industry_topic_fit", "ecosystem_value")}[pillar]
        statement = {"Empower": f"{name} could help the startup train models faster by simulating defects.",
                     "Collaborate": f"Digital Industries could pilot the startup for {name} on one line.",
                     "Connect": f"The startup could be relevant to the Xcelerator ecosystem because its inspection addresses quality for {name} buyers."}[pillar]
        scores = (3, 2, 2) if self.strong else (1, 1, 1)
        if pillar == "Connect":
            # Ecosystem gap is derived from per-seller labels; the model scores the other two.
            ids = [re.search(rf"^({k}:[a-z0-9-]+) \|", prompt, re.M).group(1) for k in ("industry", "topic")]
            sellers = re.findall(r"^(seller:[a-z0-9-]+) \|", prompt, re.M)
            audience = re.search(r"POSSIBLE AUDIENCE.*?\n(seller:[a-z0-9-]+) \|", prompt, re.S)
            return json.dumps({"criteria": {
                "industry_topic_fit": {"score": scores[1], "rationale": "because", "citations": cite, "catalog_ids": ids}},
                "neighbours": [{"catalog_id": i, "overlap": "distinct", "differentiator": "", "citations": cite}
                               for i in sellers],
                "audience": [{"catalog_id": audience.group(1), "role": "integrate", "reason": "Integrates it.",
                              "citations": cite}] if audience and self.strong else [],
                "statement": statement, "next_step": "Book a scoping call with the owner."})
        return json.dumps({"criteria": {k: {"score": s, "rationale": "because", "citations": cite,
                                              "catalog_ids": [cat_id]} for k, s in zip(keys, scores)},
                           "statement": statement, "next_step": "Book a scoping call with the owner."})

    @staticmethod
    def parse_json(text):
        return json.loads(text)


def test_all_three_pillars_are_assessed_with_their_catalog_versions_recorded():
    out = pillar_match.assess_pillars(RUN, DEPT, FakeLLM(), do_web=False)
    assert {p: out["pillars"][p]["status"] for p in ORDER} == dict.fromkeys(ORDER, "assessed")
    assert all(out["pillars"][p]["band"] == "strong" for p in ORDER)
    assert out["siemens_fit"] == {"score": 78, "winner": "Empower", "raw": 7, "partial": False, "status": "assessed"}
    assert out["recommendation"]["pillar"] == "Empower"
    assert out["catalogs"]["xcelerator"]["checksum"] == catalogs.xcelerator_catalog()["checksum"]
    assert out["catalogs"]["siemens_tools"]["checksum"] and out["catalogs"]["department_needs"]["checksum"]
    collab = out["pillars"]["Collaborate"]
    assert collab["provisional"] is True and collab["needs"] == ["inspection", "automation"]
    assert collab["criteria"][1]["catalog"][0]["id"].startswith("need:")


def test_every_pillar_is_unassessed_without_a_model_and_the_route_defers():
    class Off:
        available = False
    out = pillar_match.assess_pillars(RUN, DEPT, Off(), do_web=False)
    assert all(out["pillars"][p]["status"] == "unassessed" for p in ORDER)
    assert out["siemens_fit"]["score"] is None and out["recommendation"]["pillar"] == "Defer"


def test_a_missing_catalog_leaves_its_pillar_unassessed_and_blocks_pass(monkeypatch):
    monkeypatch.setattr(catalogs, "xcelerator_catalog",
                        lambda *a: {"name": "xcelerator", "available": False, "reason": "workbook missing",
                                    "checksum": "", "entries": []})
    out = pillar_match.assess_pillars(RUN, DEPT, FakeLLM(strong=False), do_web=False)
    assert out["pillars"]["Connect"]["status"] == "unassessed"
    assert out["pillars"]["Connect"]["reason"] == "catalog_unavailable"
    assert out["siemens_fit"]["partial"] is True
    assert out["recommendation"]["pillar"] == "Defer"        # all no-match, but not all assessed


def test_uncited_or_fabricated_concepts_are_dropped_and_a_bounded_search_fills_the_gap():
    calls = []

    def search(queries, **kw):
        calls.append(queries)
        return {k: [{"title": "Acme Vision", "body": "inspection for automotive plants",
                     "href": "https://acme.example/about"}] for k in queries}
    fabricated = {g: [{"term": "quantum", "citations": ["E999"]}] for g in pillar_match.CONCEPT_GROUPS}
    llm = FakeLLM(concepts=fabricated)
    out = pillar_match.assess_pillars(RUN, DEPT, llm, do_web=True, search=search)
    assert len(calls) == 1 and set(calls[0]) == set(ORDER)   # one wave, one query per pillar
    assert {s["pillar"] for s in out["searched"]} == set(ORDER)
    # The fake keeps citing E999, so even the searched records yield nothing citable.
    assert all(out["pillars"][p]["reason"] == "no_grounded_evidence" for p in ORDER)


def test_search_hits_become_citable_records_with_their_urls():
    def search(queries, **kw):
        return {k: [{"title": "Acme", "body": "vision inspection", "href": "https://acme.example/p"}] for k in queries}
    records = pillar_match._search_records("Acme", list(ORDER), search({p: "" for p in ORDER}))
    assert [r["id"] for r in records] == ["S0", "S1", "S2"]
    assert all(r["url"] == "https://acme.example/p" for r in records)


@pytest.mark.parametrize("term, key", [("AI", "artificial intelligence"), ("Digital Twins", "digital twin"),
                                       ("Machine Vision", "computer vision"), ("factories", "factory"),
                                       ("LLMs", "large language model")])
def test_synonyms_are_normalised_before_matching(term, key):
    assert pillar_match.normalize(term) == key
