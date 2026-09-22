"""Siemens programme criteria and the SFS financeability gate — core/programs.py.

These pin the decisions that a numeric threshold could not express. Two failures in the stored
corpus motivated the module and are asserted directly here:

* every one of the 18 stored runs was flagged SFS-relevant, because the old check asked whether
  the startup sat in a capital-intensive SPACE and the model answered about its CUSTOMERS. A pure
  software company whose users own machines is not a financing candidate, and
  `test_customer_capex_is_not_the_startups_capex` is the regression for exactly that;
* `Empower` was appended with no gate, so the answer was only ever Empower or Pass and `secondary`
  was empty in all 18 runs.

Requires the app dependencies (pandas), like the other engine tests.
"""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.programs import (assess_pillar, assess_all_pillars, assess_sfs,  # noqa: E402
                           classify_collaborate_domains, match_empower_bundles,
                           COLLABORATE_DOMAINS, PILLARS)


def _commercial(**overrides):
    """A commercial block that has been assessed — the default is 'nothing found', which is a
    different state from 'never looked' and must not be spelled as an empty dict."""
    base = {"method": "llm", "deployment": "", "deployment_source": "", "has_public_api": False,
            "api_source": "", "certifications": [], "pricing_public": False, "pricing_source": "",
            "sells_hardware": False, "hardware_source": "", "revenue_signal": "",
            "revenue_source": "", "funding_stage": "", "investors": []}
    base.update(overrides)
    return base


def _row(**kw):
    base = {"company_name": "Acme", "Your pitch": "industrial software"}
    base.update(kw)
    return pd.Series(base)


def _score(**kw):
    dims = {"traction": 50.0, "siemens_fit": 70.0, "product": 75.0,
            "market": 60.0, "founder": 70.0, "ecosystem": 40.0}
    dims.update(kw.pop("dimensions", {}))
    return {"dimensions": dims, "final_score": 55.0, "verified_customers": 0, **kw}


def _fit(relation="complement", division="DI SW"):
    return {"aligned": True, "matches": [{"tool": "Industrial Edge", "division": division,
                                          "relation": relation, "confidence": 80}]}


# ====================================================================== the three outcomes

def test_status_distinguishes_blocked_from_unproven():
    """The distinction the module exists for: 'wrong programme' vs 'not yet shown'.

    Reporting both as a plain "no" is what a threshold does, and it is the less useful half —
    a reviewer can act on 'needs ISO 27001' and cannot act on 'ineligible'.
    """
    blocked = assess_pillar("Collaborate", _row(**{"Your pitch": "bookkeeping for dentists"}),
                            {}, _fit(), _score())
    assert blocked["status"] == "blocked"
    assert blocked["blockers"]

    unproven = assess_pillar("Connect", _row(**{"Your pitch": "industrial IoT analytics"}),
                             {"commercial": _commercial()}, _fit(), _score())
    assert unproven["status"] == "unproven"
    assert not unproven["blockers"]
    assert unproven["next_steps"], "an unproven pillar must say what would prove it"


@pytest.mark.parametrize("pillar", PILLARS)
def test_every_pillar_returns_a_usable_shape_on_an_empty_evaluation(pillar):
    out = assess_pillar(pillar, pd.Series(dtype=object), {}, {}, {})
    assert out["status"] in ("eligible", "unproven", "blocked")
    assert isinstance(out["criteria"], list) and out["criteria"]
    assert all({"id", "label", "status"} <= set(c) for c in out["criteria"])


def test_unknown_pillar_is_blocked_not_crashed():
    assert assess_pillar("Acquire", _row(), {}, _fit(), _score())["status"] == "blocked"


# ====================================================================== Connect

def test_connect_blocks_a_substitute():
    """A product that competes with a Siemens tool cannot be listed beside it as a partner
    offering. This is not acquirable, so it blocks rather than becoming a next step."""
    out = assess_pillar("Connect", _row(), {"commercial": _commercial()},
                        _fit(relation="substitute"), _score())
    assert out["status"] == "blocked"
    assert any("substitute" in b.lower() for b in out["blockers"])


def test_connect_is_eligible_once_marketplace_governance_is_evidenced():
    commercial = _commercial(
        deployment="cloud", deployment_source="https://acme.io/docs",
        has_public_api=True, api_source="https://acme.io/api",
        certifications=[{"name": "ISO/IEC 27001", "source_url": "https://acme.io/security"}],
        pricing_public=True, pricing_source="https://acme.io/pricing")
    out = assess_pillar("Connect", _row(employees_count="40"), {"commercial": commercial},
                        _fit(), _score())
    assert out["status"] == "eligible", out["next_steps"]


def test_connect_names_the_missing_marketplace_requirement():
    out = assess_pillar("Connect", _row(employees_count="40"),
                        {"commercial": _commercial(deployment="cloud",
                                                   deployment_source="https://a/b")},
                        _fit(), _score())
    joined = " ".join(out["next_steps"]).lower()
    assert "27001" in joined or "62443" in joined


def test_soc2_alone_does_not_satisfy_the_marketplace_certification():
    """Real assurance, but not what the governance names — reported as progress, not compliance."""
    out = assess_pillar("Connect", _row(),
                        {"commercial": _commercial(
                            certifications=[{"name": "SOC 2", "source_url": "https://a/b"}])},
                        _fit(), _score())
    cert = next(c for c in out["criteria"] if c["id"] == "security_certified")
    assert cert["status"] == "unmet" and "SOC 2" in cert["note"]


def test_on_prem_only_fails_the_as_a_service_requirement():
    out = assess_pillar("Connect", _row(), {"commercial": _commercial(deployment="on_prem")},
                        _fit(), _score())
    assert next(c for c in out["criteria"] if c["id"] == "cloud_or_edge")["status"] == "unmet"


# ====================================================================== Collaborate

def test_collaborate_requires_one_of_the_five_published_domains():
    outside = assess_pillar("Collaborate", _row(**{"Your pitch": "payroll for hair salons"}),
                            {}, _fit(), _score())
    assert outside["status"] == "blocked"

    inside = assess_pillar("Collaborate",
                           _row(**{"Your pitch": "grid optimization and battery storage analytics"},
                                employees_count="20"),
                           {}, _fit(), _score())
    assert inside["status"] == "eligible", inside["next_steps"]


@pytest.mark.parametrize("pitch,domain", [
    ("augmented reality assembly support for technicians", "ar_vr"),
    ("computer vision and machine learning for defect detection", "ai_data"),
    ("collaborative robot cells for flexible manufacturing", "automation"),
    ("grid optimization and decarbonization of heat networks", "energy_infra"),
    ("industrial IoT edge gateways with OPC UA connectivity", "connectivity_iot"),
])
def test_each_published_domain_is_reachable(pitch, domain):
    ids = [d["id"] for d in classify_collaborate_domains(_row(**{"Your pitch": pitch}), {}, {})]
    assert domain in ids


def test_every_domain_in_the_catalogue_is_classifiable():
    """Guards a domain being added to the catalogue with terms that never fire."""
    assert set(COLLABORATE_DOMAINS) == {"ar_vr", "ai_data", "automation", "energy_infra",
                                        "connectivity_iot"}


def test_collaborate_blocks_a_substitute():
    """Siemens co-develops what it lacks; it does not venture-client its own product back."""
    out = assess_pillar("Collaborate",
                        _row(**{"Your pitch": "digital twin analytics"}),
                        {}, _fit(relation="substitute"), _score())
    assert out["status"] == "blocked"


def test_collaborate_names_the_sponsoring_business_unit():
    out = assess_pillar("Collaborate", _row(**{"Your pitch": "robotics for assembly lines"}),
                        {}, _fit(division="DI FA"), _score())
    assert "DI FA" in next(c for c in out["criteria"] if c["id"] == "bu_sponsor")["note"]


# ====================================================================== Empower

def test_empower_blocks_a_scaled_company():
    """Empower is explicitly for early-stage innovators; a scaled venture is past it, which is a
    different answer from 'not good enough'."""
    out = assess_pillar("Empower", _row(employees_count="800", **{"Your pitch": "CAD tooling"}),
                        {"commercial": _commercial(funding_stage="series_b_plus")},
                        _fit(), _score())
    assert out["status"] == "blocked"


def test_empower_blocks_a_consultancy():
    out = assess_pillar("Empower",
                        _row(**{"Your pitch": "engineering consultancy and staffing agency"}),
                        {}, _fit(), _score())
    assert out["status"] == "blocked"


def test_empower_names_the_software_bundle():
    """'You qualify for Empower' is not the deliverable; 'Solid Edge is free for a year' is."""
    out = assess_pillar("Empower",
                        _row(employees_count="8",
                             **{"Your pitch": "mechanical design of robotic grippers, CAD and CFD"}),
                        {}, _fit(), _score())
    assert out["status"] == "eligible", out["next_steps"]
    labels = " ".join(b["label"] for b in out["detail"]["bundles"])
    assert "Solid Edge" in labels or "Simcenter" in labels


@pytest.mark.parametrize("pitch,bundle", [
    ("PCB schematic and layout for embedded hardware", "electronics"),
    ("low-code internal workflow applications", "lowcode"),
    ("additive manufacturing and 3D printing of metal parts", "frontier"),
    ("product lifecycle and bill of materials management", "plm"),
])
def test_each_bundle_is_reachable(pitch, bundle):
    assert bundle in [b["id"] for b in match_empower_bundles(_row(**{"Your pitch": pitch}), {}, {})]


def test_empower_without_a_bundle_is_unproven_not_blocked():
    out = assess_pillar("Empower", _row(employees_count="6", **{"Your pitch": "a marketplace"}),
                        {}, _fit(), _score())
    assert out["status"] == "unproven"


# ====================================================================== SFS

def test_customer_capex_is_not_the_startups_capex():
    """THE regression for 18/18. A pure SaaS whose users own machinery has nothing to underwrite."""
    out = assess_sfs(_row(**{"Your pitch": "AI platform for OT teams in manufacturing with "
                                           "capital-intensive machinery and equipment"}),
                     {"commercial": _commercial(deployment="cloud", funding_stage="seed")}, {})
    assert out["status"] == "not_relevant"
    assert out["relevant"] is False
    assert any("customers" in b.lower() for b in out["blockers"]), out["blockers"]


def test_hardware_seller_gets_vendor_finance():
    """The line that helps a hardware startup CLOSE DEALS, which the old boolean could not say."""
    out = assess_sfs(_row(**{"Your pitch": "industrial vision systems for production lines"}),
                     {"commercial": _commercial(sells_hardware=True, deployment="hardware",
                                                revenue_signal="customers",
                                                revenue_source="https://a/b"),
                      "reference_customers": ["Bosch"]}, {})
    assert out["status"] == "relevant"
    assert out["line"] == "Vendor / sales finance"


def test_plant_scale_process_gets_project_finance():
    out = assess_sfs(_row(**{"Your pitch": "chemical recycling of mixed plastic waste, scaling a "
                                           "continuously operated pilot plant"}),
                     {"commercial": _commercial(funding_stage="series_a",
                                                revenue_signal="contracted")}, {})
    assert out["line"] == "Project and structured finance"


def test_scaled_software_with_revenue_reaches_corporate_lending():
    """SFS does lend to software companies — against cash flow, not against an asset."""
    out = assess_sfs(_row(**{"Your pitch": "cloud analytics"}),
                     {"commercial": _commercial(deployment="cloud", funding_stage="series_b_plus",
                                                revenue_signal="recurring",
                                                revenue_source="https://a/b")}, {})
    assert out["line"] == "Corporate lending / growth capital"


def test_hardware_without_customers_is_conditional_not_relevant():
    """A lead, not a recommendation — and it names what is missing."""
    out = assess_sfs(_row(**{"Your pitch": "robotic grippers"}),
                     {"commercial": _commercial(sells_hardware=True)}, {})
    assert out["status"] == "conditional"
    assert out["relevant"] is False
    assert out["lines"][0]["missing"]


def test_an_unassessed_run_says_so_rather_than_saying_no():
    """A run from before the commercial extraction knows nothing either way. Reporting that as
    'not relevant' is the same mistake as reporting an unsearched headcount history as absent."""
    out = assess_sfs(_row(**{"Your pitch": "hardware robots"}), {}, {})
    assert out["status"] == "unassessed"
    assert out["relevant"] is False
    assert not out["blockers"]


def test_sfs_lines_are_ordered_strongest_first():
    out = assess_sfs(_row(**{"Your pitch": "chemical recycling pilot plant and reactor"}),
                     {"commercial": _commercial(sells_hardware=True, funding_stage="series_a",
                                                revenue_signal="contracted")}, {})
    fits = [line["fit"] for line in out["lines"]]
    assert fits == sorted(fits, key=lambda f: {"strong": 0, "conditional": 1}.get(f, 2))


# ====================================================================== integration

def test_assess_all_pillars_covers_every_pillar():
    out = assess_all_pillars(_row(), {}, _fit(), _score())
    assert set(out) == set(PILLARS)


def test_a_deterministic_funding_stage_is_not_proof_the_posture_was_assessed():
    """funding_stage is parsed from a string the pipeline already had, so it is present even on a
    run where the commercial extraction never fired. Reading it as evidence of assessment made an
    offline run report a confident 'not relevant' about a company nothing had been checked on."""
    out = assess_sfs(_row(**{"Your pitch": "industrial computer vision systems"}),
                     {"commercial": {"method": "none", "funding_stage": "seed",
                                     "deployment": "", "revenue_signal": "",
                                     "certifications": [], "investors": [],
                                     "sells_hardware": False, "has_public_api": False,
                                     "pricing_public": False}}, {})
    assert out["status"] == "unassessed"


def test_an_extraction_that_found_nothing_still_counts_as_assessed():
    """We looked and the evidence was silent — that IS a finding, unlike never having looked."""
    out = assess_sfs(_row(**{"Your pitch": "a scheduling app"}),
                     {"commercial": {"method": "llm", "funding_stage": "", "deployment": "",
                                     "revenue_signal": "", "certifications": [], "investors": [],
                                     "sells_hardware": False, "has_public_api": False,
                                     "pricing_public": False}}, {})
    assert out["status"] == "not_relevant"
