"""Money and headcount parsing, as the traction rubric reads it.

The rubric's bands are in euros and its sources disagree on notation: GlassDollar hands back a bare
bigint, Tracxn "USD 2500000", the web "2,5 Mio €" or "₹15 crore". Every row below is a string a
source can plausibly produce; the expectation is the amount a human reader would take from it.
Where the parser reads a *larger* number than the text states, that is an invented fact — the
worst failure here, because it moves a startup up a band on money nobody raised.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.text import (find_money, parse_funding_amount, parse_headcount,  # noqa: E402
                       parse_money)


def _one(text):
    money = parse_money(text)
    assert money is not None, f"no amount read from {text!r}"
    return money


# --------------------------------------------------------------------- symbols and ISO codes

@pytest.mark.parametrize("text, low, currency", [
    ("$5M", 5e6, "USD"),
    ("€2.8M", 2.8e6, "EUR"),
    ("£1.2m", 1.2e6, "GBP"),
    ("¥300M", 3e8, "JPY"),
    ("₹15 crore", 1.5e8, "INR"),
    ("US$4M", 4e6, "USD"),
    ("CA$5M", 5e6, "CAD"),
    ("C$5M", 5e6, "CAD"),
    ("A$3M", 3e6, "AUD"),
    ("AU$3M", 3e6, "AUD"),
    ("S$2M", 2e6, "SGD"),
    ("HK$10M", 1e7, "HKD"),
    ("~$3M", 3e6, "USD"),
    ("over $2 million", 2e6, "USD"),
    ("€2M+", 2e6, "EUR"),
])
def test_currency_symbols(text, low, currency):
    m = _one(text)
    assert (m["low"], m["currency"], m["currency_assumed"]) == (low, currency, False)


@pytest.mark.parametrize("text, low, currency", [
    ("USD 2500000", 2.5e6, "USD"),          # Tracxn's shape
    ("2500000 USD", 2.5e6, "USD"),
    ("EUR 1.5M", 1.5e6, "EUR"),
    ("1.5M EUR", 1.5e6, "EUR"),
    ("CHF 2M", 2e6, "CHF"),
    ("SAR 3.75 million", 3.75e6, "SAR"),
    ("USD 2,500,000", 2.5e6, "USD"),
    ("USD 1,5 Mio", 1.5e6, "USD"),
    ("2.5 million EUR", 2.5e6, "EUR"),
    ("RMB 10M", 1e7, "CNY"),                # RMB is the same currency as CNY
    ("CNY 5M", 5e6, "CNY"),
])
def test_iso_codes_before_and_after(text, low, currency):
    m = _one(text)
    assert (m["low"], m["currency"]) == (low, currency)


@pytest.mark.parametrize("text, low, currency", [
    ("5 million euros", 5e6, "EUR"),
    ("3 million dollars", 3e6, "USD"),
])
def test_currency_words(text, low, currency):
    m = _one(text)
    assert (m["low"], m["currency"]) == (low, currency)


@pytest.mark.parametrize("text", ["USD2M", "EUR2M"])
def test_iso_code_glued_to_the_number(text):
    assert _one(text)["currency"] == text[:3]


# ------------------------------------------------------------------------------ magnitudes

@pytest.mark.parametrize("text, low", [
    ("$500k", 5e5),
    ("500K", 5e5),
    ("2 thousand", 2e3),
    ("0.5M", 5e5),
    ("3 m", 3e6),
    ("$1.5 million", 1.5e6),
    ("2,5 Mio €", 2.5e6),
    ("2,5 Mio. €", 2.5e6),
    ("1,2 Mrd €", 1.2e9),
    ("1.2bn", 1.2e9),
    ("$1.2 bn", 1.2e9),
    ("₹50 lakh", 5e6),
    ("50 lakhs", 5e6),
    ("15 crore", 1.5e8),
])
def test_magnitude_suffixes(text, low):
    assert _one(text)["low"] == low


@pytest.mark.parametrize("text", ["15 crore", "50 lakhs", "3 lac", "2 cr"])
def test_lakh_and_crore_imply_rupees(text):
    m = _one(text)
    assert (m["currency"], m["currency_assumed"]) == ("INR", False)


def test_bare_magnitude_has_no_currency_and_says_so():
    m = _one("1.2bn")
    assert (m["currency"], m["currency_assumed"]) == ("", True)


# ------------------------------------------------------------------------------ separators

@pytest.mark.parametrize("text, low", [
    ("2.500.000 €", 2.5e6),                 # European thousands
    ("€1.500.000", 1.5e6),
    ("€2.500.000,50", 2_500_000.5),         # European thousands + decimal comma
    ("€2,500,000", 2.5e6),                  # English thousands
    ("$2,500,000.50", 2_500_000.5),
    ("$12,345", 12_345),
    ("€1.500", 1_500),                      # one dot group, no magnitude → thousands
    ("€1,500", 1_500),
    ("$1,5M", 1.5e6),                       # decimal comma before a magnitude
    ("2,500 Mio", 2.5e6),                   # documented: a lone 3-digit comma group + magnitude is decimal
])
def test_european_and_english_separators(text, low):
    assert _one(text)["low"] == low


@pytest.mark.parametrize("text", ["€ 750 000", "750 000 €"])
def test_space_grouped_thousands(text):
    assert _one(text)["low"] == 750_000


def test_indian_digit_grouping():
    assert _one("₹2,50,000")["low"] == 250_000


def test_leading_decimal_point_is_not_dropped():
    assert _one("$.5M")["low"] == 500_000


# ---------------------------------------------------------------------------------- ranges

@pytest.mark.parametrize("text, low, high, currency", [
    ("$1-2M", 1e6, 2e6, "USD"),             # the suffix after the second number applies to both
    ("€1–2 Mio", 1e6, 2e6, "EUR"),
    ("$1M to $3M", 1e6, 3e6, "USD"),
    ("€5-€10M", 5e6, 1e7, "EUR"),
    ("$10M-$5M", 5e6, 1e7, "USD"),          # reversed range is normalised
    ("10-20M€", 1e7, 2e7, "EUR"),
])
def test_ranges_keep_both_ends_and_score_the_lower(text, low, high, currency):
    m = _one(text)
    assert (m["low"], m["high"], m["currency"]) == (low, high, currency)
    assert parse_funding_amount(text) == low


# ------------------------------------------------------------------------ years, not amounts

@pytest.mark.parametrize("text, low", [
    ("$5M - 2023", 5e6),                    # an amount and a year, not a range to 2023M
    ("$5M in 2023", 5e6),
    ("$5M, 2023", 5e6),
    ("in 2021 raised $3M", 3e6),
    ("Seed round in 2023 of 1.5M", 1.5e6),
    ("$3.5M.", 3.5e6),
])
def test_a_year_beside_an_amount_is_not_the_amount(text, low):
    found = find_money(text)
    assert [m["low"] for m in found] == [low]
    assert found[0]["high"] == low


@pytest.mark.parametrize("text", ["Seed round, 2023", "Founded 2019", "Pre-Seed, amount undisclosed",
                                  "abc", "", "   ", "nan", None, "0", "$0"])
def test_no_amount(text):
    assert find_money(text) == []
    assert parse_money(text) is None
    assert parse_funding_amount(text) == 0.0


@pytest.mark.parametrize("text", ["Series A 2023 $5M", "Founded 2019 $400k"])
def test_a_year_before_an_amount_does_not_steal_its_currency(text):
    found = find_money(text)
    assert len(found) == 1 and found[0]["currency"] == "USD"


# ------------------------------------------------------------------- whole-string bare numbers

@pytest.mark.parametrize("text, low", [("2831100.0", 2_831_100), ("2500000", 2_500_000),
                                       ("1.5", 1.5)])
def test_a_whole_string_bare_number_is_an_amount_of_unstated_currency(text, low):
    m = _one(text)
    assert (m["low"], m["currency"], m["currency_assumed"]) == (low, "", True)


def test_a_whole_string_bare_number_with_separators():
    assert _one("2,500,000")["low"] == 2_500_000


def test_parse_money_picks_the_largest_lower_bound():
    assert _one("Seed $2.5M, $4M raised to date")["low"] == 4e6


def test_non_breaking_space_is_ordinary_whitespace():
    assert _one("€ 2,5 Mio")["low"] == 2.5e6


# ------------------------------------------------------ parse_funding_amount's old contract

@pytest.mark.parametrize("value, expected", [
    ("$5M seed", 5_000_000),
    ("Series C, $200 million", 200_000_000),
    ("€2.8M", 2_800_000),
    ("1.4B", 1_400_000_000),
    ("2831100.0", 2_831_100),
    ("€250K pre-seed", 250_000),
    ("Pre-Seed, amount undisclosed", 0.0),
    ("Seed round, 2023", 0.0),
    ("", 0.0),
    (None, 0.0),
    # newly read through parse_money
    ("USD 2500000", 2_500_000),
    ("2,5 Mio €", 2_500_000),
])
def test_parse_funding_amount_contract(value, expected):
    assert parse_funding_amount(value) == expected


# ---------------------------------------------------------------------------------- headcount

@pytest.mark.parametrize("text, low, high", [
    ("11-50", 11, 50),
    ("2-10", 2, 10),
    ("10 to 50", 10, 50),
    ("200-500 employees", 200, 500),
    ("10+", 10, 10),
    ("50 employees", 50, 50),
    ("1,200", 1200, 1200),
    ("~10", 10, 10),
    ("about 25", 25, 25),
    ("1", 1, 1),
])
def test_headcount(text, low, high):
    assert parse_headcount(text) == {"low": low, "high": high}


@pytest.mark.parametrize("text", ["<10", " <10", "under 10", "fewer than 5", "less than 10",
                                  "", "abc", None])
def test_headcount_without_a_lower_bound_is_unknown(text):
    assert parse_headcount(text) is None


def test_headcount_with_a_k_suffix():
    assert parse_headcount("10k employees")["low"] == 10_000
