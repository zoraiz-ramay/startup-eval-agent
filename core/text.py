"""Shared text-processing helpers and the stopword set used across the engine."""
from __future__ import annotations

import re

_STOP = set("""a an the and or of for to in on with from your you our we it is are be as by at this that solution
platform software company startup using use uses based help helps enable enables provide provides product products
service services data ai ml technology tech into across their them they his her are can will more most than then
app apps mobile web online cloud saas b2b b2c consumer user users customer customers market markets team world
first leading global new tool tools system systems digitally smart real time end manage management""".split())


# A funding string is only useful when it names a stage or an amount. Anything else — "raised
# funding", or Crunchbase's "Unfunded" status label — is not a fact a reviewer can act on, and
# letting such a value through blocks the research pipeline from filling the field with a real,
# sourced round (makkook.ai showed "Unfunded" while its Crunchbase Pre-Seed went unreported).
FUNDING_SIGNAL = re.compile(
    r"[$€£]|\b\d|\bpre[-\s]?seed\b|\bseed\b|\bseries\s+[a-z]\b|\bangel\b|\bgrant\b|"
    r"\bbridge\b|\bipo\b|\bventure\b", re.I)


def has_funding_signal(value) -> bool:
    """True when a funding string names a stage or an amount."""
    return bool(FUNDING_SIGNAL.search(str(value or "")))


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def _keywords(text: str) -> set[str]:
    return {w for w in _norm(text).split() if len(w) > 2 and w not in _STOP}


def _split_list(s: str) -> list[str]:
    return [x.strip() for x in re.split(r"[;,/]", str(s)) if x.strip()]
