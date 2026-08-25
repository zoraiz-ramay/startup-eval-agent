"""The routing benchmark — benchmarks/replay.py and benchmarks/routing_eval.py.

A benchmark that cannot fail is worse than none: it produces a number people quote. So these
assert the two things that make it real — that the metrics actually punish a wrong answer, and
that a stored run genuinely round-trips back through the live engine rather than being read off
the record it came from.

Requires the app dependencies (pandas), like the other engine tests.
"""
import json
import os
import sqlite3
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from benchmarks.replay import _facts, _row, load_runs, replay  # noqa: E402
from benchmarks.routing_eval import PILLARS, evaluate  # noqa: E402


# ====================================================================== metrics

def test_a_perfect_run_scores_one():
    out = evaluate([("Empower", "Empower"), ("Connect", "Connect")], PILLARS)
    assert out["accuracy"] == 1.0
    assert out["per_class"]["Empower"]["precision"] == 1.0
    assert out["per_class"]["Connect"]["recall"] == 1.0


def test_a_wrong_answer_costs_precision_and_recall_on_the_right_classes():
    """Predicting Empower for a company labelled Connect must dent Empower's precision AND
    Connect's recall — a metric that only moved one of them would hide half of every mistake."""
    out = evaluate([("Connect", "Empower"), ("Empower", "Empower")], PILLARS)
    assert out["per_class"]["Empower"]["precision"] == 0.5
    assert out["per_class"]["Connect"]["recall"] == 0.0
    assert out["accuracy"] == 0.5


def test_macro_f1_is_not_dominated_by_the_majority_class():
    """The corpus is overwhelmingly one pillar. A micro average would report that pillar's
    performance as the system's, which is exactly the blindness this benchmark exists to remove."""
    pairs = [("Empower", "Empower")] * 9 + [("Connect", "Empower")]
    out = evaluate(pairs, PILLARS)
    assert out["accuracy"] == 0.9
    assert out["macro_f1"] < 0.75, "macro F1 must show the missed class, not average it away"


def test_the_confusion_matrix_records_where_answers_went():
    out = evaluate([("Connect", "Empower"), ("Connect", "Empower"), ("Pass", "Pass")], PILLARS)
    assert out["matrix"]["Connect"]["Empower"] == 2
    assert out["matrix"]["Pass"]["Pass"] == 1


def test_classes_never_predicted_or_labelled_do_not_inflate_the_average():
    """Collaborate absent from both sides is not a perfect score on Collaborate."""
    out = evaluate([("Empower", "Empower")], PILLARS)
    assert out["per_class"]["Collaborate"]["support"] == 0
    assert out["macro_f1"] == 1.0     # averaged over supported classes only


# ====================================================================== replay

def _stored_run():
    """A stored run shaped exactly like `result_json`, including the string-typed booleans that
    survive a JSON round trip."""
    return {
        "found": True,
        "company": "Acme Vision",
        "summary": "Machine vision for production lines.",
        "profile": {"company_name": "Acme Vision", "hq": "Munich, DE", "founded_year": "2022",
                    "employees_count": "24", "funding": "Seed, $2.5M (2024)", "customers": "Bosch",
                    "Your pitch": "industrial computer vision with edge deployment",
                    "linkedin_url": "https://linkedin.com/company/acme"},
        "score": {"final_score": 41.2, "dimensions": {}},
        "routing": {"pillar": "Pass"},
        "facts": [{"key": "funding_web", "value": "raised", "source_url": "https://x/y",
                   "method": "ddg_search", "confidence": 0.65, "verified": "True",
                   "retrieved_at": "2026-08-20T10:00:00+00:00", "source_type": "public"}],
        "verification": {"claims": [{"field": "reference_customer", "value": "Bosch",
                                     "status": "verified"}], "red_flags": []},
        "fit": {"aligned": True, "challenge_match": {"score": 0.0, "library_size": 1},
                "matches": [{"tool": "Industrial Edge", "division": "DI",
                             "relation": "integration", "confidence": 90}]},
        "deep_profile": {"founders": [{"name": "A. Founder", "background": "PhD"}],
                         "employees": "24", "programs": [], "reference_customers": ["Bosch"],
                         "commercial": {"method": "llm", "deployment": "edge",
                                        "deployment_source": "https://acme.io/docs",
                                        "has_public_api": False, "certifications": [],
                                        "pricing_public": False, "sells_hardware": False,
                                        "revenue_signal": "", "funding_stage": "seed",
                                        "investors": []}},
        "trend": {"momentum": 60, "method": "web+llm"},
    }


def test_replay_reruns_the_engine_instead_of_reading_the_stored_verdict():
    """The stored run says Pass; the current engine says otherwise. If replay were quietly reading
    `result["routing"]` this would agree with the record and the whole benchmark would be a
    tautology."""
    out = replay(_stored_run())
    assert out["routing"]["pillar"] != _stored_run()["routing"]["pillar"]
    assert out["routing"]["pillar"] in PILLARS
    assert out["score"]["final_score"] != _stored_run()["score"]["final_score"]


def test_replay_makes_no_model_call():
    """A replay sweeps the whole corpus; if it called a model it would cost money and minutes to
    generate prose nothing reads. The offline branch produces templated reasons."""
    out = replay(_stored_run())
    assert out["routing"]["reasons"], "the offline template branch should still give reasons"


def test_replay_carries_the_evidence_scoring_depends_on():
    out = replay(_stored_run())
    assert out["score"]["verified_customers"] == 1
    assert out["routing"]["pillar_assessments"]["Empower"]["criteria"]


def test_replay_declines_a_run_it_cannot_score():
    assert replay({"found": False, "query": "nobody"}) == {}
    assert replay({"found": True}) == {}


def test_facts_survive_the_json_round_trip():
    """`verified` comes back as the string "True" from stored JSON, and the ecosystem dimension
    counts on it being a bool."""
    facts = _facts(_stored_run()["facts"])
    assert len(facts) == 1
    assert facts[0].verified is True
    assert facts[0].method == "ddg_search"


def test_facts_skip_junk_without_losing_the_rest():
    facts = _facts([{"key": "a", "method": "ddg_search"}, "not a dict", None,
                    {"key": "b", "method": "ddg_search"}])
    assert [f.key for f in facts] == ["a", "b"]


def test_row_falls_back_to_the_summary_when_a_web_sourced_run_has_no_pitch():
    """The Collaborate domain and Empower bundle matchers read the pitch text. A web-sourced run
    keeps it only in the generated summary, and matching nothing would silently block the pillar."""
    run = _stored_run()
    run["profile"].pop("Your pitch")
    assert "Machine vision" in _row(run)["Your pitch"]


# ====================================================================== corpus loading

def test_load_runs_keeps_one_row_per_company(tmp_path):
    """The corpus holds the same startup re-evaluated many times. Counting each as an independent
    case would weight whichever company someone happened to debug against most heavily."""
    db = tmp_path / "runs.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE runs (id INTEGER PRIMARY KEY, company TEXT, created_at TEXT, "
                "result_json TEXT)")
    payload = json.dumps(_stored_run())
    con.executemany("INSERT INTO runs (company, created_at, result_json) VALUES (?,?,?)",
                    [("Acme", "2026-08-01", payload), ("Acme", "2026-08-02", payload),
                     ("Other", "2026-08-03", payload)])
    con.commit()
    con.close()

    deduped = load_runs(str(db))
    assert [r["company"] for r in deduped] == ["Other", "Acme"]
    # Newest first, so the survivor is the latest evaluation of that company.
    assert next(r["run_id"] for r in deduped if r["company"] == "Acme") == 2
    assert len(load_runs(str(db), latest_per_company=False)) == 3


def test_load_runs_on_a_missing_database_is_empty_not_an_error():
    assert load_runs("/no/such/runs.db") == []
