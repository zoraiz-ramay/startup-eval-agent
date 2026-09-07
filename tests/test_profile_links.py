"""Public identifiers recovered from evidence already in hand (core/profile.py::_extract_links).

The defect these pin: a company outside GlassDollar rendered a BLANK LinkedIn row on its profile,
every time. `core/data.py::web_profile_row` walks the search results skipping every social hit
while it guesses the website, then hard-codes `linkedin_url` to "" — so the URL was in the result
set the run had already paid for, and nothing wrote it down. The website had the mirror-image
problem: it was stored ("bliro.io") but without a scheme, and so was not a link.

The grounding bar is the one the rest of this module works to: a near-namesake's profile page is
worse than an empty field, because a reviewer will follow the link and read the wrong company.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.data import _as_url                                          # noqa: E402
from core.profile import _extract_links, _identity_forms               # noqa: E402


def _row(**kw):
    base = {"company_name": "Bliro", "website": "https://bliro.io", "domain": "bliro.io"}
    base.update(kw)
    return pd.Series(base)


def _hits(*hrefs):
    return {"q": [{"title": "", "body": "", "href": h} for h in hrefs]}


# --------------------------------------------------------------------------- website is a URL

def test_a_bare_host_becomes_a_link():
    # The exact value stored for Bliro in runs.db, which rendered as an empty Website row.
    assert _as_url("bliro.io") == "https://bliro.io"


def test_an_existing_scheme_is_left_alone():
    assert _as_url("http://bliro.io/en") == "http://bliro.io/en"


def test_nothing_is_still_nothing():
    assert _as_url("") == ""
    assert _as_url(None) == ""


# --------------------------------------------------------------------------- identity matching

def test_a_slug_carrying_a_legal_suffix_is_the_same_company():
    assert _identity_forms("bliro gmbh") & _identity_forms("Bliro")


def test_a_run_together_vanity_suffix_is_the_same_company():
    # makkook.ai's LinkedIn slug is "makkook-ai"; its company name is "Makkook AI".
    assert _identity_forms("makkook ai") & _identity_forms("Makkook AI")


def test_a_short_name_does_not_lose_its_tail():
    # "sonio" must never be reduced to "son" -- that is how a three-letter stem starts matching
    # unrelated companies.
    assert "son" not in _identity_forms("Sonio")


# --------------------------------------------------------------------------- link extraction

def test_it_records_the_linkedin_page_the_search_already_returned():
    links = _extract_links("Bliro", _row(), _hits("https://www.linkedin.com/company/bliro/"))
    assert links["linkedin_url"] == "https://www.linkedin.com/company/bliro/"


def test_it_records_crunchbase_the_same_way():
    links = _extract_links("Bliro", _row(),
                           _hits("https://www.crunchbase.com/organization/bliro"))
    assert links["crunchbase_url"] == "https://www.crunchbase.com/organization/bliro"


def test_it_refuses_a_near_namesake():
    # A name-based search for a small startup returns neighbours -- Phena/Fena/Phenna is a real
    # case from this corpus. Linking a reviewer to the wrong company's LinkedIn is worse than
    # showing them nothing.
    links = _extract_links("Phena", _row(company_name="Phena", website="", domain="phena.tech"),
                           _hits("https://www.linkedin.com/company/phenna-group/"))
    assert "linkedin_url" not in links


def test_a_deep_link_still_yields_the_company_page():
    links = _extract_links("Bliro", _row(),
                           _hits("https://de.linkedin.com/company/bliro/people?trk=x"))
    assert links["linkedin_url"] == "https://www.linkedin.com/company/bliro/"


def test_it_reads_the_results_of_every_wave_it_is_given():
    # The profile stage and enrichment search different things; either may be the one that
    # surfaced the profile page.
    links = _extract_links("Bliro", _row(), {}, _hits("https://linkedin.com/company/bliro"))
    assert links["linkedin_url"] == "https://www.linkedin.com/company/bliro/"


# --------------------------------------------------------------------------- website recovery

def test_it_recovers_a_missing_website_from_a_matching_host():
    links = _extract_links("Bliro", _row(website="", domain=""),
                           _hits("https://bliro.io/en/pricing"))
    assert links["website"] == "https://bliro.io"


def test_it_does_not_mistake_a_directory_entry_for_the_company_site():
    links = _extract_links("Bliro", _row(website="", domain=""),
                           _hits("https://growjo.com/company/Bliro",
                                 "https://www.crunchbase.com/organization/bliro"))
    assert "website" not in links


def test_it_leaves_a_known_website_alone():
    links = _extract_links("Bliro", _row(website="https://bliro.io"),
                           _hits("https://bliro.io/en"))
    assert "website" not in links


# --------------------------------------------------------------------------- LinkedIn size band

def test_it_captures_the_size_band_linkedin_publishes():
    results = {"q": [{"title": "Bliro | LinkedIn",
                      "body": "2,341 followers on LinkedIn. Company size 11-50 employees",
                      "href": "https://www.linkedin.com/company/bliro/"}]}
    links = _extract_links("Bliro", _row(), results)
    assert links["linkedin_size_band"] == "11-50"


def test_a_follower_count_is_not_a_headcount():
    results = {"q": [{"title": "Bliro | LinkedIn", "body": "2,341 followers on LinkedIn.",
                      "href": "https://www.linkedin.com/company/bliro/"}]}
    assert "linkedin_size_band" not in _extract_links("Bliro", _row(), results)


def test_the_band_never_overwrites_the_cited_count():
    # It is returned under its own key. Nothing here may touch `employees`, which is the figure
    # the run can cite per datapoint.
    results = {"q": [{"title": "Bliro | LinkedIn", "body": "Company size 11-50 employees",
                      "href": "https://www.linkedin.com/company/bliro/"}]}
    assert "employees" not in _extract_links("Bliro", _row(), results)
