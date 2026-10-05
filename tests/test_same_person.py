"""One person, one entry: core/text.py::same_person, the rule every people list is deduplicated by.

Matching on the name key alone listed Phena's co-founder twice ("KD Kutadgu Gokalp Demirci" and
"Kutadgu Gokalp Demirci"). Matching too loosely would be worse — it would delete a real person —
so the cases that must stay apart are pinned as firmly as the ones that must merge.
"""
import pytest

from core.text import dedupe_people, founders_first, same_person


def p(name, **kw):
    return {"name": name, **kw}


@pytest.mark.parametrize("a, b", [
    (p("Andreas Wagner"), p("Dr. Andreas Wagner")),                          # honorific
    (p("Alexandre Kremer"), p("Alexandre Krémer (CTO)")),                    # accent, role
    (p("KD Kutadgu Gokalp Demirci"), p("Kutadgu Gokalp Demirci")),           # leading initials
    (p("Jane A. Doe"), p("Jane Doe")),                                       # middle initial
    (p("Andy Wagner", linkedin="https://www.linkedin.com/in/wagner-andreas/"),
     p("Andreas Wagner", source_url="https://linkedin.com/in/wagner-andreas")),  # same profile, shared surname
])
def test_the_same_person_spelled_differently_is_one_person(a, b):
    assert same_person(a, b) and same_person(b, a)


@pytest.mark.parametrize("a, b", [
    (p("Christian Piechnick"), p("Maria Piechnick")),                        # siblings share a surname
    # Research attached Anna Winiwarter's LinkedIn to "Florian Zahn": a shared link alone is not enough.
    (p("Florian Zahn", source_url="https://www.linkedin.com/in/anna-winiwarter"),
     p("Anna Winiwarter", linkedin="https://www.linkedin.com/in/anna-winiwarter")),
    (p("Jack Ma"), p("Jack")),                                               # one name left is not a full name
    (p("Li Wei"), p("Wei Li")),
    # A team page names everyone on it, so a shared non-LinkedIn source says nothing.
    (p("Anna Roe", source_url="https://acme.example/team"), p("Anna Smith", source_url="https://acme.example/team")),
])
def test_different_people_stay_apart(a, b):
    assert not same_person(a, b)


def test_dedupe_keeps_the_first_entry_and_fills_its_blanks_from_the_duplicate():
    out = dedupe_people([p("KD Kutadgu Gokalp Demirci", role=""), p("Kutadgu Gokalp Demirci", role="Co-Founder")])
    assert out == [{"name": "KD Kutadgu Gokalp Demirci", "role": "Co-Founder"}]


def test_a_founder_wins_over_the_same_person_in_key_team_or_advisors():
    prof = {"founders": [p("Trevor Amanya")], "key_team": [p("Dr. Trevor Amanya"), p("Ann Lee")],
            "advisors": [p("Trevor Amanya"), p("Ann Lee"), p("Bo Chen")]}
    founders_first(prof)
    assert [x["name"] for x in prof["key_team"]] == ["Ann Lee"]
    assert [x["name"] for x in prof["advisors"]] == ["Bo Chen"]
