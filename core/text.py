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


def format_funding(value) -> str:
    """Render a raw funding amount compactly; pass any non-numeric string through unchanged.

    Both sources that carry an amount give a bare number in currency units — the API as a
    bigint, the applications xlsx as a spreadsheet cell — so "2831100.0" reached the profile
    verbatim and a reviewer had to count digits. Free text ("Pre-Seed, amount undisclosed")
    is already the most precise statement available and must survive untouched.

    The € is inherited from the API mapping this used to live in, and is an assumption: no
    source states a currency. It is applied consistently rather than to one source only.
    """
    if value in (None, "", 0):
        return ""
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return str(value)
    if amount >= 1_000_000_000:
        return f"€{amount / 1_000_000_000:.1f}B"
    if amount >= 1_000_000:
        return f"€{amount / 1_000_000:.1f}M"
    if amount >= 1_000:
        return f"€{amount / 1_000:.0f}K"
    return f"€{amount:.0f}"


_MAGNITUDES = {"k": 1e3, "thousand": 1e3, "mn": 1e6, "m": 1e6, "million": 1e6,
               "bn": 1e9, "b": 1e9, "billion": 1e9}
# Longest alternatives first: "m" must not win against "million".
_AMOUNT = re.compile(r"(?P<sym>[$€£])?\s*(?P<num>\d[\d,]*(?:\.\d+)?)\s*"
                     r"(?P<mag>billion|million|thousand|bn|mn|[kmb])?\b", re.I)


def parse_funding_amount(value) -> float:
    """The currency amount a funding string states, or 0.0 when it states none.

    Scoring used to ask only whether a funding string *existed*, which made "€250K pre-seed"
    and "$1.4B Series F" the same signal. It also missed the amount entirely for GlassDollar
    rows, whose funding cell is a bare number that `FUNDING_SIGNAL` does not match at all.

    A bare number in prose is ignored unless it carries a currency symbol or a magnitude
    suffix — "Seed round, 2023" would otherwise read as a 2023-unit raise. The whole-string
    case is exempt because that is exactly the shape the xlsx cell and the API bigint take.
    Like `format_funding`, this returns a magnitude and not a currency: no source states one.
    """
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        return max(0.0, float(text.replace(",", "")))
    except ValueError:
        pass
    best = 0.0
    for m in _AMOUNT.finditer(text):
        if not (m.group("sym") or m.group("mag")):
            continue
        try:
            num = float(m.group("num").replace(",", ""))
        except ValueError:
            continue
        best = max(best, num * _MAGNITUDES.get((m.group("mag") or "").lower(), 1.0))
    return best


# Funding STAGE, which is a different fact from funding amount and answers a different question.
# The amount says how much was raised; the stage says whether an institution underwrote it, which
# is what Siemens Financial Services' corporate-lending line and the Collaborate readiness check
# actually turn on — a €2M seed from angels and a €2M Series A from a fund are not the same
# counterparty risk. Ordered most-specific first: "pre-seed" must be tested before "seed", and
# "series a" before either, or every round collapses to seed.
_STAGE_PATTERNS = (
    ("series_b_plus", r"\bseries\s+[b-z]\b|\bgrowth\s+(?:round|equity|capital)\b|\bipo\b"
                      r"|\blate[-\s]stage\b|\bmezzanine\b"),
    ("series_a",      r"\bseries\s+a\b"),
    ("pre_seed",      r"\bpre[-\s]?seed\b|\bangel\b|\bfriends\s+and\s+family\b"),
    ("seed",          r"\bseed\b|\bbridge\b"),
    ("grant",         r"\bgrant\b|\bnon[-\s]dilutive\b|\bsubsidy\b|\bprize\b"),
)


def parse_funding_stage(value) -> str:
    """The funding stage a string names, or '' when it names none.

    Deterministic on purpose. The stage is already written in the funding strings the pipeline
    has painstakingly grounded ("Pre-Seed, amount obfuscated", "Seed, $2.5M (2024)"), so asking
    a model to re-derive it would add a call, a failure mode and a source of run-to-run drift
    to recover a fact already in hand.
    """
    text = str(value or "")
    if not text.strip():
        return ""
    import re as _re
    for stage, pattern in _STAGE_PATTERNS:
        if _re.search(pattern, text, _re.I):
            return stage
    return ""


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def _keywords(text: str) -> set[str]:
    return {w for w in _norm(text).split() if len(w) > 2 and w not in _STOP}


def _split_list(s: str) -> list[str]:
    return [x.strip() for x in re.split(r"[;,/]", str(s)) if x.strip()]
