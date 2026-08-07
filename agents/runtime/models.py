"""Model tiers for the agent harness.

Auto-selects a concrete gateway model from a coarse tier so that regular work runs
on a cheap model and heavy reasoning (planning / coding) runs on an expensive one.

Each tier has its OWN model name, API key, and (optional) base URL, because the
cheap and expensive models may live behind different gateways / credentials.

Env vars (all optional; sensible fallbacks applied):
    Model names:
        LLM_MODEL_CHEAP        (default: gpt-oss-120b)
        LLM_MODEL_EXPENSIVE    (default: gpt-5.4)
    API keys (fall back to OPENAI_API_KEY if a tier-specific key is unset):
        OPENAI_API_KEY_CHEAP       (also accepts ANTHROPIC_AUTH_TOKEN)
        OPENAI_API_KEY_EXPENSIVE
    Base URLs (fall back to LLM_BASE_URL, then the Siemens gateway):
        LLM_BASE_URL_CHEAP         (also accepts ANTHROPIC_BASE_URL;
                                    default: https://api.siemens.com/llm)
        LLM_BASE_URL_EXPENSIVE
"""
from __future__ import annotations

import os

_DEFAULT_BASE = (os.getenv("LLM_BASE_URL") or "https://llm.sdc.siemens.cloud/v1").strip()
_SHARED_KEY = os.getenv("OPENAI_API_KEY", "").strip()

# The cheap tier lives on the api.siemens.com/llm gateway. Its credentials may be supplied
# with tier-specific vars OR the Claude-style ANTHROPIC_* vars from the Siemens LLM portal
# config, so the same values you paste into Claude Code work here unchanged.
_CHEAP_BASE = (os.getenv("LLM_BASE_URL_CHEAP")
               or os.getenv("ANTHROPIC_BASE_URL")
               or "https://api.siemens.com/llm").strip()
_CHEAP_KEY = (os.getenv("OPENAI_API_KEY_CHEAP")
              or os.getenv("ANTHROPIC_AUTH_TOKEN")
              or _SHARED_KEY).strip()

# tier -> concrete model name on the gateway
MODEL_TIERS = {
    "cheap": os.getenv("LLM_MODEL_CHEAP", "gpt-oss-120b"),
    "expensive": os.getenv("LLM_MODEL_EXPENSIVE", "gpt-5.4"),
}

# tier -> credentials (key + base_url), each independently overridable
TIER_KEYS = {
    "cheap": _CHEAP_KEY,
    "expensive": (os.getenv("OPENAI_API_KEY_EXPENSIVE") or _SHARED_KEY).strip(),
}
TIER_BASE_URLS = {
    "cheap": _CHEAP_BASE,
    "expensive": (os.getenv("LLM_BASE_URL_EXPENSIVE") or _DEFAULT_BASE).strip(),
}

# a few friendly aliases so agent frontmatter can be expressive
_ALIASES = {
    "": "cheap",
    "small": "cheap",
    "fast": "cheap",
    "regular": "cheap",
    "cheap": "cheap",
    "large": "expensive",
    "big": "expensive",
    "smart": "expensive",
    "planning": "expensive",
    "expensive": "expensive",
}


def resolve_tier(tier: str) -> str:
    """Normalise an arbitrary tier string to 'cheap' or 'expensive'."""
    return _ALIASES.get((tier or "").strip().lower(), "cheap")


def resolve_model(tier: str) -> str:
    """Map a tier (or alias) to a concrete gateway model name.

    If the value is already a concrete model name (contains a '-' and is not a
    known alias) it is returned unchanged, so frontmatter may pin an exact model.
    """
    raw = (tier or "").strip()
    key = raw.lower()
    if key in _ALIASES:
        return MODEL_TIERS[_ALIASES[key]]
    if key in MODEL_TIERS:
        return MODEL_TIERS[key]
    # treat as an explicit model name
    return raw or MODEL_TIERS["cheap"]


def tier_credentials(tier: str) -> tuple[str, str]:
    """Return (api_key, base_url) for the given tier (or alias)."""
    canonical = resolve_tier(tier)
    return TIER_KEYS[canonical], TIER_BASE_URLS[canonical]

