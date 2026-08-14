"""OpenAI-compatible LLM client.

Primary provider is the Siemens LLM gateway at llm.sdc.siemens.cloud, authenticated via
OPENAI_API_KEY (sent as an 'x-api-key' header). If that key isn't set, falls back to
Gemini's OpenAI-compatible endpoint using GEMINI_API_KEY — handy for local dev without
gateway access.
"""
from __future__ import annotations

import os
import re
import json
import time
import logging
from typing import Optional

from . import web as _web
from .config import LLM_MODEL, LLM_TIMEOUT

log = logging.getLogger(__name__)

LLM_BASE_URL = (os.getenv("LLM_BASE_URL") or "https://llm.sdc.siemens.cloud/v1").strip()
GEMINI_BASE_URL = (os.getenv("GEMINI_BASE_URL")
                   or "https://generativelanguage.googleapis.com/v1beta/openai/").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
LLM_MIN_BUDGET = int(os.getenv("LLM_MIN_BUDGET", "1024"))
# Gemini 2.5 is a THINKING model: its reasoning tokens are billed against
# max_completion_tokens, before a single character of the answer is emitted. A budget sized
# for the answer alone therefore gets consumed by thinking and the reply comes back truncated
# mid-token — which parse_json rejects, so the caller silently falls back to keyword-only
# extraction. That failure is invisible (the request itself succeeds, so last_error stays
# empty) and it degraded EVERY profile to method='offline_keyword': no founders, no headcount,
# no founding year. Reasoning models get this headroom added on top of the requested budget.
LLM_THINKING_HEADROOM = int(os.getenv("LLM_THINKING_HEADROOM", "6144"))
_THINKING_PROVIDERS = ("gemini",)
# Deterministic by default. Unset, Gemini samples at 1.0 and four identical extraction calls
# returned three different JSON spellings, so re-evaluating a startup never reproduced exactly.
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))
# Cache completions alongside the web results (same store, same TTL, same refresh bypass).
# Safe only because LLM_TEMPERATURE is 0 — see complete().
LLM_CACHE = os.getenv("LLM_CACHE", "1") != "0"
MAX_RETRIES = 3
RETRY_BACKOFF = 2


def _unsupported_param(exc: Exception, sent: dict) -> str:
    """Name of a tuning parameter the endpoint rejected, or '' if the error is something else.

    Only 4xx *parameter* complaints qualify: a timeout or a 500 must still go through the normal
    retry/backoff path rather than silently stripping the request down."""
    msg = str(exc).lower()
    if not any(tok in msg for tok in ("400", "invalid", "unsupported", "unrecognized",
                                      "not supported", "unknown")):
        return ""
    for name in sent:
        if name.lower() in msg:
            return name
    return ""


def openai_api_key() -> str:
    return os.getenv("OPENAI_API_KEY", "").strip().strip("<>").strip()


def gemini_api_key() -> str:
    return os.getenv("GEMINI_API_KEY", "").strip().strip("<>").strip()


class LLMClient:
    def __init__(self, key: str = "", base_url: str = "", model: str = ""):
        oa_key = (key or openai_api_key()).strip().strip("<>").strip()
        ge_key = gemini_api_key()

        if oa_key:
            self.key, self.provider = oa_key, "openai"
            self.base_url = (base_url or LLM_BASE_URL).strip()
            self.model = model or LLM_MODEL
        elif ge_key:
            self.key, self.provider = ge_key, "gemini"
            self.base_url = (base_url or GEMINI_BASE_URL).strip()
            self.model = model or GEMINI_MODEL
        else:
            self.key, self.provider = "", "none"
            self.base_url = (base_url or LLM_BASE_URL).strip()
            self.model = model or LLM_MODEL

        self.available = bool(self.key)
        self._client = None
        self.last_error: str = ""

        if self.available:
            try:
                from openai import OpenAI
                # The x-api-key header is Siemens-gateway-specific; Gemini's compat layer
                # only wants the standard Authorization: Bearer header the client sets itself.
                headers = {"x-api-key": self.key} if self.provider == "openai" else {}
                self._client = OpenAI(
                    api_key=self.key,
                    base_url=self.base_url,
                    default_headers=headers,
                    timeout=LLM_TIMEOUT,
                    max_retries=0,
                )
            except Exception as e:
                self.available = False
                self.last_error = str(e)

    def complete(self, prompt: str, system: str = "", max_tokens: int = 1200,
                 model: str = "", temperature: float = LLM_TEMPERATURE,
                 reasoning: str = "") -> str:
        """Run one completion; '' on failure.

        ``temperature`` defaults to 0 so repeated runs agree: left unset, Gemini defaults to 1.0
        and four identical extraction calls returned three different JSON spellings, which is
        why re-evaluating the same startup kept producing subtly different profiles.

        ``reasoning`` maps to OpenAI's ``reasoning_effort`` and is sent ONLY to providers that
        actually reason (``_THINKING_PROVIDERS``); the Siemens gateway never sees it. Pass
        "none" for calls that transcribe supplied evidence into JSON — measured on the profile
        extraction prompt, that is ~5x faster AND more accurate than thinking (it recovered a
        founding year the thinking run missed), because the work is reading, not reasoning.
        """
        if not self.available:
            return ""
        budget = max(max_tokens, LLM_MIN_BUDGET)
        # Applied even when reasoning is off. max_completion_tokens is a ceiling, not a charge,
        # so a generous one costs nothing — whereas trimming it to the "no thought tokens
        # needed" figure truncated the largest profile extractions mid-JSON and dropped them
        # back to keyword-only, because the per-call max_tokens values were never sized for a
        # full founders+advisors+programs+customers reply on their own.
        if self.provider in _THINKING_PROVIDERS:
            budget += LLM_THINKING_HEADROOM
        use_model = (model or self.model)
        msgs = [
            {"role": "system",
             "content": system or "You are a precise startup-evaluation analyst for Siemens."},
            {"role": "user", "content": prompt},
        ]
        extra: dict = {}
        if temperature is not None:
            extra["temperature"] = temperature
        if reasoning and self.provider in _THINKING_PROVIDERS:
            extra["reasoning_effort"] = reasoning
        # Replies are cached on the full request. Sound only because temperature is 0: at the
        # old default of 1.0 the same prompt gave a different answer every time, so a cache
        # would have frozen one arbitrary sample. A changed prompt changes the key, so prompt
        # edits can never be masked by a stale entry. LLM_CACHE=0 disables.
        ckey = _web._cache_key("llm", use_model, system, prompt, budget,
                               extra.get("temperature"), extra.get("reasoning_effort"))
        if LLM_CACHE:
            cached = _web._cached("llm", ckey)
            if isinstance(cached, str):
                self.last_error = ""
                return cached
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self._client.chat.completions.create(
                    model=use_model,
                    messages=msgs,
                    max_completion_tokens=budget,
                    timeout=LLM_TIMEOUT,
                    **extra,
                )
                self.last_error = ""
                text = resp.choices[0].message.content or ""
                if LLM_CACHE and text:
                    _web._store("llm", ckey, text)
                return text
            except Exception as e:
                # A gateway that rejects one of the tuning parameters fails every call with a
                # 400. Drop the offending parameter and carry on rather than letting a model
                # swap silently disable the LLM entirely.
                dropped = _unsupported_param(e, extra)
                if dropped:
                    log.warning("LLM rejected %r; retrying without it", dropped)
                    extra.pop(dropped, None)
                    continue
                self.last_error = str(e)
                log.warning("LLM attempt %d/%d failed: %s", attempt, MAX_RETRIES, e)
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_BACKOFF * attempt)
        return ""

    @staticmethod
    def parse_json(text: str) -> Optional[dict]:
        if not text:
            return None
        m = re.search(r"\{.*\}", text, re.DOTALL)
        try:
            return json.loads(m.group(0)) if m else None
        except Exception:
            return None
