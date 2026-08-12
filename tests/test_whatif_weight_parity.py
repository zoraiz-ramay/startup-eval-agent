"""Pins the browser what-if scorer to the engine it replicates.

`ui/src/scoring/index.js` re-implements `core/score.py:121-129` in JavaScript, because the what-if
weighting is per-user browser state that the server is never told about. Duplicated arithmetic
drifts unless something fails when it does — these tests are that something, from the Python side.

If you change how `score_startup` turns dimensions into `final_score`, expect this file to fail.
The fix is to update `ui/src/scoring/` and its golden runs to match, not to loosen the assertions.
`ui/src/scoring/scoring.test.js` holds the other half of the pin.

Requires the app dependencies (pandas), like the other scoring tests.
"""
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.config import THIN_PROFILE_CAP, WEIGHTS  # noqa: E402
from core.provenance import Fact  # noqa: E402
from core.score import score_startup  # noqa: E402

_UI = os.path.join(os.path.dirname(__file__), "..", "ui", "src", "scoring")


def _load(name):
    with open(os.path.join(_UI, name), encoding="utf-8") as fh:
        return json.load(fh)


def _row(**overrides):
    row = {
        "company_name": "Acme Robotics", "hq": "Munich, DE", "founded_year": "2021",
        "employees_count": "40", "funding": "$5M seed", "customers": "Bosch",
        "linkedin_url": "https://linkedin.com/company/acme", "Your pitch": "Robots for factories",
    }
    row.update(overrides)
    return pd.Series(row)


def _base_kwargs():
    enrichment = {"facts": [Fact(key="funding_web", value="raised", method="ddg_search",
                                 source_url="https://x/y", confidence=0.6, verified=True)]}
    verification = {"claims": [], "red_flags": []}
    fit = {"matches": [], "challenge_match": {}}
    return enrichment, verification, fit


def test_ui_constants_match_the_engine_exactly():
    """The JSON the browser reads is a copy of core.config; a copy that drifts is a wrong score."""
    constants = _load("engine-constants.json")
    assert constants["weights"] == WEIGHTS
    assert constants["thin_profile_cap"] == THIN_PROFILE_CAP


def test_engine_weights_still_sum_to_one():
    """The UI normalises to 1 on the strength of this. If the engine stops summing to 1, the
    normalisation silently rescales every what-if relative to the stored score."""
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_completeness_lands_on_the_grid_the_ui_snaps_to():
    """The UI recovers exact completeness by snapping to 1/N, because the engine rounds it to 2dp
    on the way out. That is only valid while completeness really is k/N — adding a ninth key field
    would break the assumption, so assert it against live engine output rather than the source."""
    denom = _load("engine-constants.json")["completeness_denominator"]
    enrichment, verification, fit = _base_kwargs()
    for blanks in range(0, 5):
        blanked = {k: "" for k in list(_row().index)[:blanks]}
        out = score_startup(_row(**blanked), enrichment, verification, fit, {})
        scaled = out["data_completeness"] * denom
        # The engine rounds completeness to 2dp, so scaled by `denom` it can sit up to
        # 0.005 * denom off a whole number. Anything beyond that is a real change of grid,
        # which is what would make the UI's snapping pick the wrong k.
        assert abs(scaled - round(scaled)) <= 0.005 * denom + 1e-9, (
            f"completeness {out['data_completeness']} is not a multiple of 1/{denom}"
        )


def test_confidence_is_still_derived_from_completeness():
    """The UI derives confidence rather than reading the stored value, since the stored one is
    rounded. That is only correct while the engine uses this exact relation."""
    enrichment, verification, fit = _base_kwargs()
    out = score_startup(_row(), enrichment, verification, fit, {})
    assert out["data_confidence"] == round(0.5 + 0.5 * out["data_completeness"], 2)


def test_golden_runs_still_reproduce_under_the_current_formula():
    """The golden runs are real stored scores. Recomputing them from today's engine constants
    proves the recorded fixtures still describe how the engine behaves — so a change to the shape
    of the formula fails here, not just a change to the numbers."""
    golden = _load("golden-runs.json")["runs"]
    assert golden, "golden-runs.json is empty; regenerate it from data/runs.db"
    for run in golden:
        dims = run["dimensions"]
        raw = sum(dims[k] * WEIGHTS[k] for k in WEIGHTS)
        completeness = round(run["data_completeness"] * 8) / 8
        final = raw * (0.5 + 0.5 * completeness)
        if completeness < 0.5:
            final = min(final, THIN_PROFILE_CAP)
        assert abs(final - run["final_score"]) <= 0.1, (
            f"run {run['run_id']} ({run['company']}): recomputed {final:.2f} "
            f"but the engine stored {run['final_score']}"
        )
