"""The inputs Siemens Fit and the total rest on: catalogs, Team & Ecosystem, the weighted total.

A catalog that cannot be read must make its pillar unassessed, not empty — an empty catalog
would score every startup a no-match. And every missing component must leave the total pending,
never counted as 0.
"""
import openpyxl
import pytest

from core import catalogs, assessment
from core import team_ecosystem as T

HEADER = ("Seller", "Region", "Industry", "Topic", "Motion", "Description", "URL", "Logo")


def workbook(tmp_path, sellers, filters=True, header=HEADER, name="x.xlsx"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sellers"
    ws.append(header)
    for row in sellers:
        ws.append(row)
    if filters:
        fv = wb.create_sheet("Filter_Values")
        fv.append(("Filter", "Value", "Sellers"))
        fv.append(("Industry", "Automotive", 1))
        fv.append(("Topic", "Quality", 1))
    path = tmp_path / name
    wb.save(path)
    return str(path)


ROW = ("Acme", "Germany", "Automotive; Electronics", "Quality", "Build", "Vision QA",
       "https://www.siemens.com/en-us/ecosystem/acme/", "")


def test_duplicate_sellers_merge_and_keep_the_canonical_url(tmp_path):
    dup = ("Acme", "Austria", "Automotive; Metals", "Efficiency", "Build", "Vision QA",
           "https://www.siemens.com/en-us/ecosystem/change-me-abc123/", "")
    x = catalogs.xcelerator_catalog(workbook(tmp_path, [dup, ROW]))
    assert x["available"] and len(x["entries"]) == 1
    acme = x["entries"][0]
    assert acme["url"] == "https://www.siemens.com/en-us/ecosystem/acme/"
    assert set(acme["industries"]) == {"Automotive", "Metals", "Electronics"}
    assert set(acme["regions"]) == {"Austria", "Germany"}            # context, kept, not scored
    assert any("duplicate" in i for i in x["issues"])


def test_blank_filters_and_invalid_urls_are_tolerated_and_reported(tmp_path):
    blank = ("Beta", None, None, None, "Service", "Something", "not-a-url", "")
    x = catalogs.xcelerator_catalog(workbook(tmp_path, [ROW, blank]))
    beta = next(s for s in x["entries"] if s["name"] == "Beta")
    assert beta["industries"] == [] and beta["topics"] == [] and beta["url"] == ""
    assert any("Beta: no valid seller URL" in i for i in x["issues"])


@pytest.mark.parametrize("build, reason", [
    (lambda p: workbook(p, [ROW], header=("Seller", "Industry")), "missing columns"),
    (lambda p: workbook(p, [], filters=True), "no sellers"),
])
def test_a_malformed_workbook_is_unavailable_with_the_reason(tmp_path, build, reason):
    x = catalogs.xcelerator_catalog(build(tmp_path))
    assert x["available"] is False and reason in x["reason"]


def test_a_missing_or_corrupt_workbook_is_unavailable(tmp_path):
    assert catalogs.xcelerator_catalog(str(tmp_path / "nope.xlsx"))["available"] is False
    bad = tmp_path / "bad.xlsx"
    bad.write_bytes(b"not a workbook")
    assert catalogs.xcelerator_catalog(str(bad))["available"] is False


def test_filter_vocabulary_falls_back_to_the_sellers(tmp_path):
    x = catalogs.xcelerator_catalog(workbook(tmp_path, [ROW], filters=False))
    assert {i["name"] for i in x["industries"]} == {"Automotive", "Electronics"}
    assert any("Filter_Values" in i for i in x["issues"])


def test_the_checksum_is_of_the_bytes_so_a_changed_catalog_is_a_different_version(tmp_path):
    a = catalogs.xcelerator_catalog(workbook(tmp_path, [ROW], name="a.xlsx"))
    b = catalogs.xcelerator_catalog(workbook(tmp_path, [ROW[:2] + ("Metals",) + ROW[3:]], name="b.xlsx"))
    assert a["checksum"] and a["checksum"] != b["checksum"]


def test_the_shipped_workbook_loads():
    x = catalogs.xcelerator_catalog()
    assert x["available"] and len(x["topics"]) == 31 and len(x["entries"]) >= 490
    assert not any("change-me" in s["url"] for s in x["entries"])


def test_changed_department_needs_change_the_checksum_and_empty_needs_are_unavailable():
    a = catalogs.department_catalog({"id": "di", "label": "DI", "interests": ["automation"], "demo": True})
    b = catalogs.department_catalog({"id": "di", "label": "DI", "interests": ["automation", "grid"], "demo": True})
    assert a["checksum"] != b["checksum"] and a["provisional"] is True
    assert catalogs.department_catalog({"id": "di", "interests": []})["available"] is False
    assert catalogs.department_catalog(None)["available"] is False


NEED = {"id": "SI-01.1", "capability": "Process Automation", "category": "Automate Internal Processes",
        "description": "Automating repetitive tasks such as data entry.", "keywords": ["RPA", "workflow automation"]}


def test_stated_needs_are_one_entry_per_capability_with_what_it_means():
    dep = {"id": "si", "label": "Smart Infrastructure", "interests": ["RPA"], "demo": False, "needs": [NEED]}
    c = catalogs.department_catalog(dep)
    assert c["provisional"] is False
    assert c["entries"] == [{"id": "need:si-01-1", "name": "Process Automation", "kind": "need",
                             "category": "Automate Internal Processes",
                             "description": "Automating repetitive tasks such as data entry.",
                             "keywords": ["RPA", "workflow automation"]}]
    changed = catalogs.department_catalog({**dep, "needs": [{**NEED, "description": "Something else."}]})
    assert changed["checksum"] != c["checksum"]          # a reworded need is a different catalog


def test_a_long_needs_list_is_shortlisted_most_relevant_first_and_every_need_stays_eligible():
    from core import pillar_match as pm
    needs = [{**NEED, "id": f"M-{i}", "capability": f"Need {i}", "description": "rail signalling",
              "keywords": ["signalling"]} for i in range(30)]
    needs[25] = {**needs[25], "description": "predictive maintenance of rolling stock", "keywords": ["predictive maintenance"]}
    cat = catalogs.department_catalog({"id": "mobility", "label": "Mobility", "interests": ["x"], "demo": False, "needs": needs})
    concepts = {"capabilities": [{"term": "predictive maintenance", "key": "predictive maintenance", "citations": ["E1"]}]}
    picked = pm.shortlist("Collaborate", concepts, cat, {})
    assert len(picked) == pm._NEEDS_SHORTLIST and picked[0]["name"] == "Need 25"
    assert "category: Automate Internal Processes" in pm._catalog_line(picked[0])


# ----------------------------------------------------------------------------- team & ecosystem

EV = {"E1": {"id": "E1", "source": "deep_profile.founders[0]", "quote": "ex-Siemens VP", "url": ""}}


def team_raw(levels, cites=("E1",)):
    return {k: {"score": s, "rationale": "r", "citations": list(cites) if s else []}
            for (k, _, _), s in zip(T.CRITERIA, levels)}


@pytest.mark.parametrize("points, band", [(0, "Very weak"), (4, "Very weak"), (5, "Weak"), (8, "Weak"),
                                          (9, "Moderate"), (12, "Moderate"), (13, "Strong"), (16, "Strong"),
                                          (17, "Exceptional"), (20, "Exceptional")])
def test_team_band_boundaries(points, band):
    assert T.band(points) == band


def test_team_points_and_their_0_to_100_scale():
    out = T.validate(team_raw([5, 4, 3, 0]), EV)
    assert out["points"] == 12 and out["score_0_100"] == 60 and out["band"] == "Moderate"
    assert out["criteria"][3]["anchor"] == "No identifiable partnerships or ecosystem relationships"


@pytest.mark.parametrize("bad", [
    lambda r: r["founder_experience"].update(score=6),
    lambda r: r["founder_experience"].update(score=True),
    lambda r: r["founder_experience"].update(citations=[]),     # positive level, no citation
    lambda r: r["founder_experience"].update(citations=["E9"]),
    lambda r: r.pop("strategic_network"),
])
def test_team_rejects_malformed_or_uncited_levels(bad):
    r = team_raw([3, 2, 2, 1])
    bad(r)
    with pytest.raises(ValueError):
        T.validate(r, EV)


def test_team_is_unassessed_without_a_model():
    assert T.assess_team({"company": "x"}, None)["status"] == "unassessed"


# ----------------------------------------------------------------------------- total

@pytest.mark.parametrize("parts, expected", [
    ({"traction": 80, "siemens_fit": 78, "team_ecosystem": 60, "market": 70}, 73.8),
    ({"traction": 0, "siemens_fit": 0, "team_ecosystem": 0, "market": 0}, 0.0),
    ({"traction": 100, "siemens_fit": 100, "team_ecosystem": 100, "market": 100}, 100.0),
    ({"traction": 50, "siemens_fit": 33, "team_ecosystem": 45, "market": 61}, 44.7),
])
def test_total_is_the_exact_weighted_sum(parts, expected):
    assert assessment.total(parts) == expected


@pytest.mark.parametrize("missing", ["traction", "siemens_fit", "team_ecosystem", "market"])
def test_any_missing_component_leaves_the_total_pending_not_zeroed(missing):
    parts = {"traction": 80, "siemens_fit": 78, "team_ecosystem": 60, "market": 70, missing: None}
    assert assessment.total(parts) is None


def _department_run(fit=78, team_points=12, market=70, traction_dims=None):
    return {"found": True, "company": "Acme",
            "department": {"id": "di", "label": "DI", "interests": ["automation"], "demo": True},
            "traction": {"version": "traction-rubric-v2", "status": "scored", "score_0_100": 80.0, "earned": 56,
                         "available_max": 70, "divisions_known": 3, "divisions": []},
            "score": {"version": "llm-judgment-v1", "status": "assessed", "final_score": 64,
                      "dimensions": {"traction": traction_dims or 80.0, "siemens_fit": 55, "market": market}},
            "assessment": {"siemens_fit": {"score": fit, "status": "assessed" if fit is not None else "unassessed"},
                           "team_ecosystem": {"status": "assessed", "score_0_100": team_points * 5}
                           if team_points is not None else {"status": "unassessed"}}}


def test_hydrate_puts_the_total_on_the_headline_and_keeps_the_model_numbers_aside():
    out = assessment.hydrate(_department_run())
    assert out["assessment"]["total"] == 73.8 and out["score"]["final_score"] == 73.8
    assert out["score"]["dimensions"]["siemens_fit"] == 78
    assert out["score"]["llm_final_score"] == 64 and out["score"]["llm_siemens_fit"] == 55
    again = assessment.hydrate(out)                          # idempotent on re-read
    assert again["score"]["llm_final_score"] == 64 and again["assessment"]["total"] == 73.8


def test_hydrate_attaches_every_level_of_each_rubric_so_a_score_can_be_read_against_its_scale():
    scales = assessment.hydrate(_department_run())["assessment"]["scales"]
    assert scales["pillars"]["Empower"]["tool_fit"][3] == "Tool directly supports a core startup activity/capability"
    assert all(len(levels) == 4 for p in scales["pillars"].values() for levels in p.values())
    assert set(scales["team_ecosystem"]) == {k for k, _, _ in T.CRITERIA}
    assert all(len(levels) == 6 for levels in scales["team_ecosystem"].values())


def test_an_unassessed_siemens_fit_is_absent_not_the_models_guess_and_the_total_waits():
    out = assessment.hydrate(_department_run(fit=None))
    assert "siemens_fit" not in out["score"]["dimensions"]
    assert out["score"]["final_score"] is None and out["assessment"]["total_status"] == "pending"


def test_a_legacy_run_gets_no_total():
    legacy = {"found": True, "company": "Old", "score": {"final_score": 55, "dimensions": {"market": 50}}}
    out = assessment.hydrate(legacy)
    assert out["score"]["final_score"] == 55 and "assessment" not in out
