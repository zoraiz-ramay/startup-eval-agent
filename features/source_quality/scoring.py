from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TypedDict
from urllib.parse import urlparse


PRIMARY_DOMAINS = {
    ".gov": 95,
    ".edu": 90,
    ".org": 75,
}

NEWS_HOST_KEYWORDS = (
    "news",
    "times",
    "post",
    "journal",
    "reuters",
    "apnews",
    "bloomberg",
    "bbc",
    "forbes",
    "wsj",
    "cnn",
)

PROMOTIONAL_KEYWORDS = (
    "pricing",
    "book-demo",
    "demo",
    "get-started",
    "contact-sales",
    "free-trial",
    "try-now",
    "signup",
    "register",
    "buy",
)

VENDOR_HOST_KEYWORDS = (
    "app",
    "cloud",
    "platform",
    "crm",
    "software",
    "solutions",
)


@dataclass(frozen=True)
class SourceQualityBreakdown:
    domain_type: str
    attribution_present: bool
    date_present: bool
    promotional_signals: int
    reasoning: str


@dataclass(frozen=True)
class SourceScore:
    quality_score: int
    quality_breakdown: SourceQualityBreakdown


class SourceQualityBreakdownDict(TypedDict):
    domain_type: str
    attribution_present: bool
    date_present: bool
    promotional_signals: int
    reasoning: str


class SourceScoreDict(TypedDict):
    quality_score: int
    quality_breakdown: SourceQualityBreakdownDict


def _host_from_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.netloc:
        return parsed.netloc.lower()
    if parsed.path and "." in parsed.path:
        return parsed.path.split("/")[0].lower()
    return ""


def _classify_domain(host: str) -> str:
    if not host:
        return "unknown"
    for suffix in PRIMARY_DOMAINS:
        if host.endswith(suffix):
            return suffix[1:]
    if any(keyword in host for keyword in NEWS_HOST_KEYWORDS):
        return "news"
    if any(keyword in host for keyword in VENDOR_HOST_KEYWORDS):
        return "vendor"
    return "commercial"


def _base_score(domain_type: str) -> int:
    if domain_type == "gov":
        return 95
    if domain_type == "edu":
        return 90
    if domain_type == "org":
        return 75
    if domain_type == "news":
        return 78
    if domain_type == "vendor":
        return 45
    if domain_type == "commercial":
        return 55
    return 40


def _promotional_signal_count(url: str, title: str, snippet: str) -> int:
    haystack = " ".join([url.lower(), title.lower(), snippet.lower()])
    return sum(1 for keyword in PROMOTIONAL_KEYWORDS if keyword in haystack)


def _reasoning_parts(
    domain_type: str,
    attribution_present: bool,
    date_present: bool,
    promotional_signals: int,
) -> list[str]:
    parts = [f"domain type: {domain_type}"]
    parts.append(
        "author/attribution present"
        if attribution_present
        else "no attribution found"
    )
    parts.append(
        "publication date present" if date_present else "no publication date found"
    )
    if promotional_signals:
        parts.append(f"{promotional_signals} promotional signal(s) detected")
    else:
        parts.append("no clear promotional signals")
    return parts


def _to_breakdown_dict(
    breakdown: SourceQualityBreakdown,
) -> SourceQualityBreakdownDict:
    return {
        "domain_type": breakdown.domain_type,
        "attribution_present": breakdown.attribution_present,
        "date_present": breakdown.date_present,
        "promotional_signals": breakdown.promotional_signals,
        "reasoning": breakdown.reasoning,
    }


def score_source(
    url: str,
    title: str = "",
    snippet: str = "",
    author: Optional[str] = None,
    published_at: Optional[str] = None,
) -> SourceScoreDict:
    host = _host_from_url(url)
    domain_type = _classify_domain(host)
    attribution_present = bool(author and author.strip())
    date_present = bool(published_at and published_at.strip())
    promotional_signals = _promotional_signal_count(url, title, snippet)

    score = _base_score(domain_type)
    if attribution_present:
        score += 8
    else:
        score -= 6
    if date_present:
        score += 7
    else:
        score -= 4
    score -= promotional_signals * 12

    score = max(0, min(100, score))
    reasoning = "; ".join(
        _reasoning_parts(
            domain_type=domain_type,
            attribution_present=attribution_present,
            date_present=date_present,
            promotional_signals=promotional_signals,
        )
    )

    breakdown = SourceQualityBreakdown(
        domain_type=domain_type,
        attribution_present=attribution_present,
        date_present=date_present,
        promotional_signals=promotional_signals,
        reasoning=reasoning,
    )
    result = SourceScore(quality_score=score, quality_breakdown=breakdown)
    return {
        "quality_score": result.quality_score,
        "quality_breakdown": _to_breakdown_dict(result.quality_breakdown),
    }
