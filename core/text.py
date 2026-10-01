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


def parse_funding_amount(value) -> float:
    """The currency amount a funding string states, or 0.0 when it states none.

    Scoring used to ask only whether a funding string *existed*, which made "€250K pre-seed"
    and "$1.4B Series F" the same signal. It also missed the amount entirely for GlassDollar
    rows, whose funding cell is a bare number that `FUNDING_SIGNAL` does not match at all.

    A bare number in prose is ignored unless it carries a currency symbol or a magnitude
    suffix — "Seed round, 2023" would otherwise read as a 2023-unit raise. The whole-string
    case is exempt because that is exactly the shape the xlsx cell and the API bigint take.
    Like `format_funding`, this returns a magnitude and not a currency; `parse_money` keeps it.

    Delegates to `parse_money`, whose own notation handling this used to lack: Tracxn's
    "USD 2500000" (an ISO code rather than a symbol) and "2,5 Mio €" both read as 0 here. A range
    now reads as its lower bound, as the traction rubric does.
    """
    money = parse_money(value)
    return max(0.0, money["low"]) if money else 0.0


# ---------------------------------------------------------------------------- money
# `parse_funding_amount` answers "how big" and deliberately drops the currency. The traction rubric
# needs the currency too — its bands are in euros, and the sources disagree: GlassDollar hands back
# a bare bigint, Tracxn "USD 2500000", the web "2,5 Mio €" or "₹15 crore". A parser that read none
# of those three would score them all as unfunded, which is the "unknown rendered as zero" mistake.
_SYMBOLS = {"us$": "USD", "ca$": "CAD", "c$": "CAD", "au$": "AUD", "a$": "AUD", "s$": "SGD",
            "hk$": "HKD", "$": "USD", "€": "EUR", "£": "GBP", "₹": "INR", "¥": "JPY"}
_ISO = ("USD", "EUR", "GBP", "CHF", "SAR", "AED", "INR", "JPY", "CNY", "RMB", "SEK", "NOK",
        "DKK", "PLN", "CAD", "AUD", "SGD", "HKD", "ILS", "BRL", "KRW", "QAR", "TRY")
_CURRENCY_WORDS = {"euro": "EUR", "euros": "EUR", "dollar": "USD", "dollars": "USD",
                   "pounds": "GBP", "rupees": "INR"}
_MONEY_MAG = {"k": 1e3, "thousand": 1e3, "m": 1e6, "mn": 1e6, "mio": 1e6, "million": 1e6,
              "millions": 1e6, "b": 1e9, "bn": 1e9, "mrd": 1e9, "billion": 1e9, "billions": 1e9,
              "trillion": 1e12, "trillions": 1e12, "tn": 1e12,
              "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5,
              "crore": 1e7, "crores": 1e7, "cr": 1e7}
# An ISO code may be glued to its number ("USD2M"), so it ends at the next non-letter, not at \b.
_CUR = (r"(?:US\$|CA\$|C\$|AU\$|A\$|S\$|HK\$|[$€£₹¥]|(?-i:\b(?:" + "|".join(_ISO)
        + r")(?![A-Za-z])))")
# Space-grouped thousands first ("750 000", French and German style), then ordinary digits, then a
# bare decimal (".5M") whose leading point would otherwise be dropped — a tenfold error.
_MNUM = r"\d{1,3}(?:[ \u202f]\d{3})+(?!\d)|\d[\d.,]*\d|\d|\.\d+"
# Longest alternatives first, so "m" never wins against "million" or "mio".
_MMAG = (r"(?:trillions|trillion|millions|million|thousand|billions|billion|crores|crore|lakhs|lakh|lacs|lac"
         r"|mrd|mio|mn|bn|tn|cr"
         r"|[kmb])\b\.?")
_MONEY = re.compile(
    rf"(?P<c1>{_CUR})?\s*(?P<n1>{_MNUM})\s*(?P<m1>{_MMAG})?"
    rf"(?:\s*(?:-|–|—|to)\s*(?P<c2>{_CUR})?\s*(?P<n2>{_MNUM})\s*(?P<m2>{_MMAG})?)?"
    # A trailing currency must not be followed by a number: in "Seed 2023 $2.3M" that "$" belongs
    # to 2.3M, and taking it made the year a USD 2023 and left the real amount without a currency.
    rf"\s*(?P<c3>(?:{_CUR}|\beuros?\b|\bdollars?\b|\bpounds\b|\brupees\b)(?!\s*[\d.]))?", re.I)


def _money_number(s: str, has_magnitude: bool) -> float | None:
    """One number in any of the notations the sources use, or None.

    "2.500.000" and "2,5" are European; "2,500,000" and "2.5" are English. A lone comma group of
    exactly three digits ("2,500") is read as thousands unless a magnitude follows, because
    "2,500 Mio" is not a thing anyone writes but "2,5 Mio" is.
    """
    s = re.sub(r"[  ]", "", s).rstrip(".,")
    if s.startswith("."):                                     # .5 (M)
        return float("0" + s) if re.fullmatch(r"\.\d+", s) else None
    if re.fullmatch(r"\d{1,2}(?:,\d{2})+,\d{3}", s):          # 2,50,000 (Indian grouping)
        return float(s.replace(",", ""))
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+,\d+", s):           # 2.500.000,50
        return float(s.replace(".", "").replace(",", "."))
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+\.\d+", s):           # 2,500,000.50
        return float(s.replace(",", ""))
    if re.fullmatch(r"\d{1,3}(?:\.\d{3}){2,}", s) or (
            re.fullmatch(r"\d{1,3}\.\d{3}", s) and not has_magnitude):
        return float(s.replace(".", ""))                      # 2.500.000 / 1.500 (no suffix)
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+", s) and not (has_magnitude and s.count(",") == 1):
        return float(s.replace(",", ""))                      # 2,500,000 / 2,500
    if re.fullmatch(r"\d+,\d+", s):
        return float(s.replace(",", "."))                     # 2,5 (Mio)
    try:
        return float(s)
    except ValueError:
        return None


def _currency_of(token: str | None) -> str:
    t = (token or "").strip()
    if not t:
        return ""
    if t.upper() in _ISO:
        return "CNY" if t.upper() == "RMB" else t.upper()
    return _SYMBOLS.get(t.lower(), "") or _CURRENCY_WORDS.get(t.lower(), "")


def find_money(value) -> list[dict]:
    """Every amount a string states, each as {low, high, currency, currency_assumed, text}.

    A range ("$1-2M", "€1–2 Mio") keeps both ends: the rubric scores the lower one, because the
    upper end is exactly the kind of number a startup rounds up to. A number with neither a
    currency nor a magnitude is not an amount ("Seed round, 2023"), except when it is the whole
    string — that is the shape of GlassDollar's bigint and the xlsx cell. Neither of those states
    a currency, so it is reported as '' with ``currency_assumed`` for the caller to resolve.
    """
    text = str(value or "").replace("\u00a0", " ").strip()
    if not text:
        return []
    if re.fullmatch(r"\d+(?:\.\d+)?|\d{1,3}(?:,\d{3})+(?:\.\d+)?", text):
        amount = float(text.replace(",", ""))
        return [{"low": amount, "high": amount, "currency": "", "currency_assumed": True,
                 "text": text, "start": 0, "end": len(text)}] if amount > 0 else []
    out = []
    for m in _MONEY.finditer(text):
        mag1 = (m.group("m1") or "").lower().rstrip(".")
        mag2 = (m.group("m2") or "").lower().rstrip(".")
        currency = next((c for c in (_currency_of(m.group(g)) for g in ("c1", "c2", "c3")) if c), "")
        if not currency and mag1 in ("lakh", "lakhs", "lac", "lacs", "crore", "crores", "cr"):
            currency = "INR"            # nobody counts in lakh and crore in any other currency
        if not (currency or mag1 or mag2):
            continue
        n1 = _money_number(m.group("n1"), bool(mag1 or mag2))
        if n1 is None:
            continue
        # "$1-2M": the suffix after the second number applies to both.
        f1 = _MONEY_MAG.get(mag1 or mag2, 1.0)
        low = high = n1 * f1
        # "$5M - 2023" is an amount and a year, not a five-to-two-thousand-million range.
        if m.group("n2") and not (not mag2 and re.fullmatch(r"(?:19|20)\d\d", m.group("n2"))):
            n2 = _money_number(m.group("n2"), bool(mag1 or mag2))
            if n2 is not None:
                high = n2 * _MONEY_MAG.get(mag2 or mag1, 1.0)
                low, high = min(low, high), max(low, high)
        if high <= 0:
            continue
        out.append({"low": low, "high": high, "currency": currency,
                    "currency_assumed": not currency, "text": m.group(0).strip(),
                    "start": m.start(), "end": m.end()})
    return out


def parse_money(value) -> dict | None:
    """The largest amount a string states (by its lower bound), or None.

    Largest, like `parse_funding_amount`: a funding line that names a round and a total ("Seed
    $2.5M, $4M raised to date") is best read by its total, and any single round is a floor on it.
    """
    found = find_money(value)
    return max(found, key=lambda a: a["low"]) if found else None


def parse_headcount(value) -> dict | None:
    """A headcount as {low, high}, or None when the text states no usable count.

    "11-50" is a band and scores by its lower bound; "10+" is a floor; "<10" names no lower bound
    at all and is therefore unknown rather than read as ten.
    """
    text = str(value or "").replace("\u00a0", " ").strip()
    if not text or re.match(r"^\s*(?:<|under|fewer than|less than)", text, re.I):
        return None
    nums = []
    for n, mag in re.findall(r"(\d[\d,]*(?:\.\d+)?)\s*(k\b|thousand\b)?", text, re.I):
        try:
            nums.append(float(n.replace(",", "")) * (1000 if mag else 1))
        except ValueError:
            continue
    if not nums:
        return None
    return {"low": int(min(nums)), "high": int(max(nums))}


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


# What a customer list split out of free text leaves behind when it is not a name: the start of a
# clause ("In parallel", "For scale-up", "as well as …"), a description of a kind of buyer
# ("Chemical producers", "Materials and polymer value chains"), a half-closed bracket, or a
# sentence that ran on ("… and suppliers. Currently"). An application form's "Reference
# customers" box is often prose, and every piece of it used to be kept as a named account.
_CLAUSE_START = re.compile(
    r"^(?:in|for|to|with|and|or|as|at|on|of|by|from|over|under|about|around|approx(?:imately)?|"
    r"currently|including|include|includes|such|e\.?g\.?|i\.?e\.?|our|we|they|also|plus|more|"
    r"most|some|many|few|several|all|each|other|others|both|either|various|mainly|mostly|"
    r"primarily|especially|partly|then|than|while|when|where|which|who|this|these|those|"
    r"it|its|there|here|now|soon|already|still|yet|not|no|n/?a|tbd|none|up|down|over)\b", re.I)
_BUYER_KIND = re.compile(
    r"\b(?:factor(?:y|ies)|sectors?|industr(?:y|ies)|companies|clients?|customers?|enterprises?|"
    r"manufacturers?|producers?|suppliers?|operators?|providers?|owners?|outfits?|agenc(?:y|ies)|"
    r"organi[sz]ations|institutions|utilities|municipalities|hospitals|retailers|distributors|"
    r"startups?|businesses|firms|brands|smbs?|smes?|value chains?|end[- ]users?|consumers|"
    r"segments)\b", re.I)


def is_named_org(value) -> bool:
    """True when a string reads as the name of one organisation, not a fragment of prose.

    Deliberately strict: a real customer dropped here costs a few traction points, while a
    fragment kept is shown to a reviewer as a named account and scored as one.
    """
    s = str(value or "").strip().strip(".,;:")
    if not s or len(s) > 60 or not re.search(r"[A-Z]", s):
        return False
    if s.count("(") != s.count(")") or s.count("[") != s.count("]"):
        return False
    if re.search(r"[.!?]\s+\S", s) or re.search(r"\d", s) and not re.search(r"[A-Za-z]{2,}", s):
        return False
    return not (_CLAUSE_START.search(s) or _BUYER_KIND.search(s))


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def _keywords(text: str) -> set[str]:
    return {w for w in _norm(text).split() if len(w) > 2 and w not in _STOP}


def _split_list(s: str) -> list[str]:
    return [x.strip() for x in re.split(r"[;,/]", str(s)) if x.strip()]


def _clean_source_url(value) -> str:
    """Keep a real http(s) link, otherwise ''.

    Asked for a source_url, the model sometimes answers with the corpus label it read the fact
    from ('f1, f2') rather than the link. Those reach the UI and render as a broken 'web-sourced'
    link, so anything that is not a URL is dropped — the fact is still kept, just without a
    citation. Mirrors the guard in profile._clean_employee_series.

    Lives here rather than in core/profile.py because core/trend.py's market landscape holds every
    competitor and funded peer to the same bar, and a second copy of a two-line grounding rule is
    exactly how the two drift apart. core.profile re-exports it, so existing imports still work.
    """
    url = str(value or "").strip()
    return url if url.lower().startswith(("http://", "https://")) else ""
