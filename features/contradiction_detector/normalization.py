from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from .models import SUPPORTED_TOPICS


_MONTH_DAY_YEAR_FORMATS = (
    "%B %d, %Y",
    "%b %d, %Y",
)

_MONTH_YEAR_FORMATS = (
    "%B %Y",
    "%b %Y",
)

_CURRENCY_WORD_MULTIPLIERS = {
    "k": Decimal("1000"),
    "thousand": Decimal("1000"),
    "m": Decimal("1000000"),
    "million": Decimal("1000000"),
    "b": Decimal("1000000000"),
    "billion": Decimal("1000000000"),
}


def normalize_claim_value(topic: str, value: str) -> Optional[Any]:
    if topic not in SUPPORTED_TOPICS:
        return None

    text = value.strip()
    if not text:
        return None

    if topic == "founding_year":
        return _normalize_year(text)
    if topic == "launch_date":
        return _normalize_date(text)
    if topic in {"funding_total", "pricing"}:
        return _normalize_money(text)
    if topic == "employee_count":
        return _normalize_count(text)
    if topic == "headquarters":
        return _normalize_text(text)
    return None


def _normalize_year(text: str) -> Optional[int]:
    match = re.search(r"\b(19\d{2}|20\d{2}|21\d{2})\b", text)
    if match is None:
        return None
    return int(match.group(1))


def _normalize_date(text: str) -> Optional[str]:
    text = text.strip()
    for fmt in _MONTH_DAY_YEAR_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass

    for fmt in _MONTH_YEAR_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt).date()
            return parsed.replace(day=1).isoformat()
        except ValueError:
            pass

    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass

    year_match = re.fullmatch(r"(19\d{2}|20\d{2}|21\d{2})", text)
    if year_match is not None:
        return f"{year_match.group(1)}-01-01"
    return None


def _normalize_money(text: str) -> Optional[str]:
    cleaned = text.strip().lower().replace(",", "")
    amount_match = re.search(
        r"(?P<currency>\$|usd\s*)?(?P<number>\d+(?:\.\d+)?)\s*"
        r"(?P<multiplier>k|m|b|thousand|million|billion)?",
        cleaned,
    )
    if amount_match is None:
        return None

    number = _safe_decimal(amount_match.group("number"))
    if number is None:
        return None

    multiplier_key = amount_match.group("multiplier")
    if multiplier_key:
        number *= _CURRENCY_WORD_MULTIPLIERS[multiplier_key]

    normalized = _decimal_to_string(number)
    return f"USD:{normalized}"


def _normalize_count(text: str) -> Optional[int]:
    cleaned = text.strip().lower().replace(",", "")
    match = re.search(
        r"(?P<number>\d+(?:\.\d+)?)\s*(?P<multiplier>k|m|b|thousand|million|billion)?",
        cleaned,
    )
    if match is None:
        return None

    number = _safe_decimal(match.group("number"))
    if number is None:
        return None

    multiplier_key = match.group("multiplier")
    if multiplier_key:
        number *= _CURRENCY_WORD_MULTIPLIERS[multiplier_key]

    return int(number)


def _normalize_text(text: str) -> str:
    lowered = text.strip().lower()
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip()


def _safe_decimal(raw: str) -> Optional[Decimal]:
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def _decimal_to_string(value: Decimal) -> str:
    integral = value.to_integral() if value == value.to_integral() else value.normalize()
    return format(integral, "f")
