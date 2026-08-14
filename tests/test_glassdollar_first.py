"""GlassDollar as the first source, with the web filling only what it leaves empty.

The real API only answers inside the Siemens network, so every test here drives the client
contract with a fake rather than the network. That is a real limitation and worth stating:
these prove the *routing* of data through the pipeline — which source wins, which search is
skipped, what provenance the resulting Fact carries — not that the live endpoint returns what
core/glassdollar_api.py says it does.
"""
from __future__ import annotations

import pandas as pd
import pytest

from core import glassdollar_api, pipeline, profile as profile_mod
from core.provenance import Fact


# --------------------------------------------------------- what the API maps onto our shape

def test_the_api_record_maps_onto_the_headline_fields_the_pipeline_needs():
    """The comparison that decides whether GlassDollar can replace any scraping: the fields
    it returns against the fields the engine would otherwise reconstruct from the web."""
    row = glassdollar_api.company_to_row({
        "id": 4242, "name": "Aeroview", "website": "https://aeroview.io", "domain": "aeroview.io",
        "hq": "Munich, Germany", "founded_year": 2019, "employee_count": "11-50",
        "funding": 3_750_000, "linkedin_url": "https://linkedin.com/company/aeroview",
        "crunchbase_url": "https://crunchbase.com/organization/aeroview",
        "referenced_customers": [{"name": "Bosch"}, "Trumpf"],
        "short_description": "Edge vision QC.", "long_description": "Long form.",
        "logo_url": "https://cdn/x.png", "tags": ["computer vision", "manufacturing"],
    })
    assert row["company_name"] == "Aeroview"
    assert row["founded_year"] == "2019"
    assert row["employees_count"] == "11-50"
    assert row["funding"] == "€3.8M"
    assert row["customers"] == "Bosch, Trumpf"
    assert row["domain"] == "aeroview.io"
    assert row["glassdollar_id"] == "4242"


def test_the_api_leaves_pitch_form_fields_blank_rather_than_guessing():
    """Business model and development stage come from the Siemens application form, which the
    public API does not expose. They must stay empty so the web pipeline is still asked for
    them — inventing them here is exactly the failure mode core/data.py exists to prevent."""
    row = glassdollar_api.company_to_row({"id": 1, "name": "Aeroview"})
    assert row["Business model"] == ""
    assert row["Development stage of your solution"] == ""


# --------------------------------------------------------- seeding and the skipped search

def _blank_profile(**over):
    p = dict(profile_mod.EMPTY_PROFILE)
    p.update(over)
    return p


def test_database_values_replace_a_web_guess_rather_than_only_filling_blanks():
    prof = _blank_profile(founded_year="2015", founded_year_source="https://example.com/wrong")
    row = pd.Series({"founded_year": "2019", "funding": "€3.8M", "employees_count": "11-50"})

    seeded = profile_mod._seed_from_database(prof, row)

    assert prof["founded_year"] == "2019"
    assert seeded == {"founded_year", "funding", "employees"}
    # The URL evidenced 2015, which just lost. Keeping it would make 2019 look sourced by a
    # page that contradicts it.
    assert prof.get("founded_year_source", "") == ""


def test_a_corroborating_source_url_survives_when_the_two_agree():
    prof = _blank_profile(founded_year="2019", founded_year_source="https://example.com/right")
    profile_mod._seed_from_database(prof, pd.Series({"founded_year": "2019"}))
    assert prof["founded_year_source"] == "https://example.com/right"


def test_an_empty_database_field_leaves_the_researched_value_alone():
    prof = _blank_profile(funding="Seed, $2M (2024)")
    seeded = profile_mod._seed_from_database(prof, pd.Series({"funding": "", "founded_year": "nan"}))
    assert prof["funding"] == "Seed, $2M (2024)"
    assert seeded == set()


def test_the_headcount_never_enters_the_time_series():
    """_clean_employee_series requires an http source per datapoint and GlassDollar supplies
    one current number with no URL and no history. It belongs in the scalar field only."""
    prof = _blank_profile()
    profile_mod._seed_from_database(prof, pd.Series({"employees_count": "11-50"}))
    assert prof["employees"] == "11-50"
    assert prof["employees_over_time"] == []


def test_seeded_fields_stop_the_recall_net_searching_for_them(monkeypatch):
    """The saving. _recover_headline_facts fires its own search wave plus an extraction call;
    with the database's answers already in place it must not run at all."""
    searched = []
    monkeypatch.setattr(profile_mod, "_ddg_many",
                        lambda queries, **kw: searched.append(queries) or {})

    class _LLM:
        available = True

        def complete(self, *a, **kw):        # pragma: no cover - must never be reached
            raise AssertionError("the recall net called the model for a field the DB answered")

    prof = _blank_profile()
    profile_mod._seed_from_database(prof, pd.Series(
        {"founded_year": "2019", "funding": "€3.8M", "employees_count": "11-50"}))
    profile_mod._recover_headline_facts(prof, "Aeroview", pd.Series({}), _LLM())
    assert searched == []


def test_the_recall_net_still_runs_for_whatever_the_database_left_empty(monkeypatch):
    """GlassDollar narrows the web's job; it does not end it. A company with no recorded
    funding must still get the focused wave."""
    searched = []
    monkeypatch.setattr(profile_mod, "_ddg_many",
                        lambda queries, **kw: searched.append(queries) or {})

    class _LLM:
        available = True

        def complete(self, *a, **kw):
            return "{}"

    prof = _blank_profile()
    profile_mod._seed_from_database(prof, pd.Series(
        {"founded_year": "2019", "employees_count": "11-50"}))     # no funding
    profile_mod._recover_headline_facts(prof, "Aeroview", pd.Series({}), _LLM())
    assert len(searched) == 1


# --------------------------------------------------------- provenance

@pytest.mark.parametrize("method,url,expected", [
    ("glassdollar_api", "", "private"),
    ("glassdollar_db", "", "self_reported"),
    ("profile_research", "https://example.com/about", "public"),
    # An existing rule worth pinning next to the new one: a web finding with no URL is an
    # inference, which is why glassdollar_api needed its own category rather than "public".
    ("profile_research", "", "inferred"),
])
def test_source_type_distinguishes_the_curated_database_from_a_web_find(method, url, expected):
    assert Fact(key="founded_year", value="2019", method=method,
                source_url=url).source_type == expected


def test_a_database_fact_is_not_demoted_to_an_inference_for_lacking_a_url():
    """A "public" claim without a URL is correctly demoted to "inferred" — but a GlassDollar
    record is neither. It has no URL because it is licensed data, not because nobody found
    a source, and calling it an inference would understate it as badly as calling it public
    would overstate it."""
    f = Fact(key="founded_year_research", value="2019", method="glassdollar_api")
    assert f.source_url == ""
    assert f.source_type == "private"


def test_facts_report_the_database_when_that_is_where_the_value_came_from():
    prof = _blank_profile(founded_year="2019", funding="€3.8M", employees="11-50")
    facts = {f.key: f for f in profile_mod._profile_facts(
        prof, {"founded_year", "employees"}, "glassdollar_api")}

    assert facts["founded_year_research"].method == "glassdollar_api"
    assert facts["employees_research"].method == "glassdollar_api"
    # funding was not seeded, so it is still a web finding and must not borrow the credit.
    assert facts["funding_research"].method == "profile_research"


def test_facts_default_to_web_research_when_nothing_was_seeded():
    prof = _blank_profile(founded_year="2019")
    facts = {f.key: f for f in profile_mod._profile_facts(prof)}
    assert facts["founded_year_research"].method == "profile_research"


# --------------------------------------------------------- domain resolution

@pytest.mark.parametrize("value,expected", [
    ("phena.tech", True),
    ("https://www.phena.tech/about", True),
    ("Phena", False),
    ("Phena Technologies", False),
    ("", False),
    ("trailing.", False),
])
def test_only_domain_shaped_input_triggers_the_by_domain_lookup(value, expected):
    assert pipeline._looks_like_domain(value) is expected


def test_a_pasted_url_resolves_to_the_database_record(monkeypatch):
    """get_company_by_domain existed in the client and was never called. A domain identifies
    exactly one company where a fuzzy name match at 0.82 competes with near-namesakes."""
    seen = {}

    class _Client:
        def get_company_by_domain(self, domain):
            seen["domain"] = domain
            return {"id": 7, "name": "Phena", "domain": "phena.tech", "founded_year": 2026}

    monkeypatch.setattr(glassdollar_api, "get_client", lambda *a, **kw: _Client())
    row = pipeline._by_domain("https://www.phena.tech/about")

    assert seen["domain"] == "phena.tech"          # scheme, www and path all stripped
    assert row["company_name"] == "Phena"
    assert row["founded_year"] == "2026"


def test_by_domain_failures_fall_through_instead_of_breaking_the_evaluation(monkeypatch):
    class _Client:
        def get_company_by_domain(self, domain):
            raise glassdollar_api.GlassDollarError("no key")

    monkeypatch.setattr(glassdollar_api, "get_client", lambda *a, **kw: _Client())
    assert pipeline._by_domain("phena.tech") is None
    assert pipeline._by_domain("Phena") is None
