"""Pins the browser's what-if routing to the engine it replicates.

`ui/src/scoring/routing.js` re-derives the pillar under a reviewer's own weighting, which means it
mirrors `core/route.py`'s eligibility gates. Those gates are **bare inline literals** (70, 60, 55,
35 at `core/route.py:26,28`) — nothing named, nothing importable — so unlike the score constants
they cannot be pinned by value. They are pinned here behaviourally instead: each probe drives the
real `route()` to a threshold and asserts it flips exactly where the UI's mirror claims.

Every threshold is read from `ui/src/scoring/route-constants.json`, never written as a literal in
this file. That is deliberate: if the test hard-coded 70, changing the engine would fail the test
with a message about the test, and the tempting fix would be to edit the test and leave the mirror
silently wrong. Reading the mirror makes the mirror the thing under test.

Requires the app dependencies (pandas), like the other scoring tests.
"""
import json
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.config import FIT_ALIGN_THRESHOLD, WEIGHTS  # noqa: E402
from core.route import route  # noqa: E402
from core.score import ROUTE_WEIGHTS  # noqa: E402

_UI = os.path.join(os.path.dirname(__file__), "..", "ui", "src", "scoring")

# Half the 1dp rounding the engine applies to scorecards: small enough to sit inside any real gap,
# large enough not to be float noise. Probing at t and t-EPS pins the value AND the >= inclusivity.
EPS = 0.05


def _load(name):
    with open(os.path.join(_UI, name), encoding="utf-8") as fh:
        return json.load(fh)


CONSTANTS = _load("route-constants.json")


class _OfflineLLM:
    """`_route_reasons` takes the template branch when the client is unavailable, so no network."""
    available = False


def _eligible(route_score=None, traction=None, target="Connect",
              aligned=True, siemens_fit=None):
    """Runs the real router with one clause under test and everything else comfortably satisfied,
    so a failure is unambiguous about which gate moved."""
    gates = CONSTANTS["gates"]
    cards = {r: 100.0 for r in ROUTE_WEIGHTS}
    if route_score is not None:
        cards[target] = route_score
    dims = {k: 100.0 for k in WEIGHTS}
    dims["traction"] = 100.0 if traction is None else traction
    dims["siemens_fit"] = (CONSTANTS["fit_align_threshold"] + 10
                           if siemens_fit is None else siemens_fit)
    score = {
        "final_score": 50.0, "dimensions": dims, "route_scorecards": cards,
        "data_confidence": 0.9, "data_completeness": 0.8, "unverified_customers": 0,
    }
    fit = {"aligned": aligned, "matches": [{"tool": "Simcenter"}]}
    out = route(score, fit, pd.Series(dtype=object), _OfflineLLM(), {})
    assert gates  # guards against an empty mirror silently passing every probe
    return [out["pillar"], *out["secondary"]] if out["pillar"] != "Pass" else []


def test_route_weights_mirror_matches_the_engine():
    assert CONSTANTS["route_weights"] == ROUTE_WEIGHTS
    assert CONSTANTS["fit_align_threshold"] == FIT_ALIGN_THRESHOLD


def test_each_route_profile_covers_exactly_the_scored_dimensions():
    """Catches a new dimension or a renamed one: the UI iterates these keys to build its blend."""
    for name, profile in ROUTE_WEIGHTS.items():
        assert set(profile) == set(WEIGHTS), name
        assert abs(sum(profile.values()) - 1.0) < 1e-9, name


def test_every_pillar_the_engine_can_return_is_in_the_mirror():
    """A fourth pillar would silently vanish from the UI's gate table."""
    assert set(ROUTE_WEIGHTS) | {"Pass"} == set(CONSTANTS["pillars"])


@pytest.mark.parametrize("target,clause", [
    ("Connect", "route_score"), ("Connect", "traction"),
    ("Collaborate", "route_score"), ("Collaborate", "traction"),
])
def test_eligibility_gate_sits_exactly_where_the_mirror_says(target, clause):
    threshold = CONSTANTS["gates"][target][clause]
    kwargs = {"target": target}
    below, at, above = threshold - EPS, threshold, threshold + EPS

    assert target not in _eligible(**{clause: below}, **kwargs), (
        f"{target}'s {clause} gate admits at {below}; the UI mirror says the threshold is {threshold}"
    )
    # `at` is the one that matters: it pins >= rather than >, which a value-only probe would miss.
    assert target in _eligible(**{clause: at}, **kwargs), (
        f"{target}'s {clause} gate excludes at exactly {threshold}; the mirror assumes >="
    )
    assert target in _eligible(**{clause: above}, **kwargs)


def test_empower_has_no_score_gate():
    """The property that makes 'a what-if can never become Pass' true. If Empower ever gains a gate,
    the UI's invariant reasoning becomes wrong and this must fail."""
    assert CONSTANTS["gates"]["Empower"] == {}
    cards = {r: 0.0 for r in ROUTE_WEIGHTS}
    dims = {k: 0.0 for k in WEIGHTS}
    dims["siemens_fit"] = FIT_ALIGN_THRESHOLD
    score = {"final_score": 0.0, "dimensions": dims, "route_scorecards": cards,
             "data_confidence": 0.9, "data_completeness": 0.8, "unverified_customers": 0}
    out = route(score, {"aligned": True, "matches": []}, pd.Series(dtype=object), _OfflineLLM(), {})
    assert out["pillar"] == "Empower"


@pytest.mark.parametrize("aligned,siemens_fit", [
    (False, None),                              # portfolio match absent
    (True, FIT_ALIGN_THRESHOLD - EPS),          # aligned, but fit below the threshold
])
def test_alignment_gate_bars_every_pillar(aligned, siemens_fit):
    assert _eligible(aligned=aligned, siemens_fit=siemens_fit) == []


def test_primary_is_the_highest_scoring_eligible_route_not_a_fixed_order():
    """The UI sorts its own eligible list the same way; a fixed-order engine would disagree."""
    dims = {k: 100.0 for k in WEIGHTS}
    base = {"final_score": 50.0, "dimensions": dims, "data_confidence": 0.9,
            "data_completeness": 0.8, "unverified_customers": 0}
    fit = {"aligned": True, "matches": []}
    row, llm = pd.Series(dtype=object), _OfflineLLM()

    collab_high = dict(base, route_scorecards={"Connect": 71.0, "Collaborate": 99.0, "Empower": 60.0})
    assert route(collab_high, fit, row, llm, {})["pillar"] == "Collaborate"
    connect_high = dict(base, route_scorecards={"Connect": 99.0, "Collaborate": 71.0, "Empower": 60.0})
    assert route(connect_high, fit, row, llm, {})["pillar"] == "Connect"


def test_golden_runs_replay_through_the_real_router():
    """Every recorded run, pushed back through route(), still produces what it recorded. Catches a
    change to the gates that happens to leave the synthetic probes above intact."""
    golden = _load("golden-runs.json")["runs"]
    assert golden, "golden-runs.json is empty; run scripts/golden_runs.py"
    for run in golden:
        score = {
            "final_score": run["final_score"], "dimensions": run["dimensions"],
            "route_scorecards": run["route_scorecards"], "data_confidence": run["data_confidence"],
            "data_completeness": run["data_completeness"], "unverified_customers": 0,
        }
        out = route(score, {"aligned": run["fit_aligned"], "matches": []},
                    pd.Series(dtype=object), _OfflineLLM(), {})
        assert out["pillar"] == run["pillar"], f"run {run['run_id']} ({run['company']})"
        assert out["secondary"] == run["secondary"], f"run {run['run_id']}"
