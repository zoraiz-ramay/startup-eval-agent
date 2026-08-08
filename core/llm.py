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
MAX_RETRIES = 3
RETRY_BACKOFF = 2


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
                 model: str = "") -> str:
        if not self.available:
            return ""
        budget = max(max_tokens, LLM_MIN_BUDGET)
        if self.provider in _THINKING_PROVIDERS:
            budget += LLM_THINKING_HEADROOM
        use_model = (model or self.model)
        msgs = [
            {"role": "system",
             "content": system or "You are a precise startup-evaluation analyst for Siemens."},
            {"role": "user", "content": prompt},
        ]
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self._client.chat.completions.create(
                    model=use_model,
                    messages=msgs,
                    max_completion_tokens=budget,
                    timeout=LLM_TIMEOUT,
                )
                self.last_error = ""
                return resp.choices[0].message.content or ""
            except Exception as e:
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
