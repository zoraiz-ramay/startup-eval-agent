"""A reference customer must read as the name of one organisation.

An application form's "Reference customers" box is often prose, and splitting it on commas kept
every piece as a named account: Radical Dot "had" customers called "In parallel" and "For
scale-up", scored as SMEs. These pin that fragments are dropped at extraction, on every stored
run as it is read, and from the traction rubric — and that real names survive.
"""
import pytest

from core.assessment import hydrate
from core.pillar_match import _concept_evidence
from core.text import is_named_org
from core.traction import score_traction, gather_traction_inputs

FRAGMENTS = ["Chemical producers (platform chemicals and intermediates)", "Materials and polymer value chains (resins",
             "In parallel", "For scale-up", "Over 2", "Industrial manufacturing and suppliers. Currently",
             "as well as a a few local manufacturing outfits in the US"]
NAMES = ["Spendesk", "Deliciously Ella", "AstraZeneca", "Dell Technologies", "Booking.com", "Swiss Life",
         "BarmeniaGothaer", "Würth", "NVIDIA", "The Home Depot", "Whole Foods Market", "SAP"]


@pytest.mark.parametrize("text", FRAGMENTS)
def test_fragments_of_prose_are_not_customers(text):
    assert not is_named_org(text)


@pytest.mark.parametrize("name", NAMES)
def test_real_organisation_names_are_kept(name):
    assert is_named_org(name)


def test_a_stored_run_loses_its_fragments_on_read_and_the_rubric_stops_counting_them():
    run = {"found": True, "company": "Radical Dot",
           "deep_profile": {"reference_customers": FRAGMENTS[:4] + ["BASF"]}}
    out = hydrate(run)
    assert out["deep_profile"]["reference_customers"] == ["BASF"]
    assert run["deep_profile"]["reference_customers"][0] == FRAGMENTS[0]          # the stored run is not mutated
    customers = next(d for d in score_traction(gather_traction_inputs(run))["divisions"] if d["id"] == "customers")
    assert [i["name"] for i in customers["items"]] == ["BASF"]


def test_the_assessment_keeps_the_records_its_concepts_cite():
    records = [{"id": "E0", "source": "summary", "text": "Oxolysis turns plastic into acids.", "url": ""},
               {"id": "E1", "source": "profile.hq", "text": "Munich", "url": ""}]
    concepts = {"technologies": [{"term": "Oxolysis", "key": "oxolysi", "citations": ["E0"]}]}
    assert _concept_evidence(concepts, records) == {
        "E0": {"id": "E0", "source": "summary", "quote": "Oxolysis turns plastic into acids.", "url": ""}}
