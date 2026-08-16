"""Spreadsheet cells reaching the profile as strings a reviewer can read.

Both defects here came from the same place: `str()` applied to a pandas cell. openpyxl types a
column by its contents, so any column containing a blank is float64 and every value in it
stringifies with a trailing ".0" — headcount shown as "8.0", founded year as "2024.0". Funding
had that plus a second problem: the amount is a bare number of currency units, so a real run
displayed "2831100.0" and left the reader counting digits.
"""
import numpy as np
import pytest

from core.pipeline import _cell
from core.text import format_funding


@pytest.mark.parametrize("value, expected", [
    (np.float64(8.0), "8"),                 # headcount
    (np.float64(2024.0), "2024"),           # founded year
    (np.float64(2831100.0), "2831100"),
    (np.int64(2024), "2024"),               # int64 columns were never affected
    ("11-50", "11-50"),                     # a band is a string and must survive
    (2.5, "2.5"),                           # only WHOLE floats are narrowed
    (np.float64("nan"), ""),                # blank cell, not the string "nan"
    (None, ""),
    ("", ""),
])
def test_cell_drops_the_float_artefact_without_touching_real_values(value, expected):
    assert _cell(value) == expected


def test_nan_does_not_become_the_string_nan():
    """The failure this guards: "nan" is truthy, so it would pass every emptiness check in the
    pipeline and reach the UI as a value rather than an em dash."""
    assert _cell(np.float64("nan")) == ""
    assert not _cell(np.float64("nan"))


@pytest.mark.parametrize("value, expected", [
    (2831100.0, "€2.8M"),
    ("2831100.0", "€2.8M"),                 # already stringified upstream
    (3_410_000, "€3.4M"),
    (1_250_000_000, "€1.2B"),
    (12_000, "€12K"),
    (950, "€950"),
])
def test_funding_amounts_are_rendered_at_their_magnitude(value, expected):
    assert format_funding(value) == expected


@pytest.mark.parametrize("value", [
    "Pre-Seed, amount undisclosed",
    "Raised funding over 1 Pre-Seed round; total amount obfuscated.",
    "$2.5M Series A",
])
def test_free_text_funding_is_left_exactly_as_it_is(value):
    """These strings are the most precise statement the source made. Reformatting them, or
    dropping them for not parsing as a number, would lose information rather than clean it."""
    assert format_funding(value) == value


@pytest.mark.parametrize("value", [None, "", 0])
def test_no_amount_stays_empty_so_the_ui_shows_an_em_dash(value):
    assert format_funding(value) == ""
