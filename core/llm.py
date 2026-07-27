"""OpenAI-compatible LLM client with pluggable providers.

Provider selection (first match wins):
  1. GEMINI_API_KEY set  -> Google Gemini via its OpenAI-compatible endpoint
     (default model: gemini-2.5-flash; override with LLM_MODEL)
  2. OPENAI_API_KEY set  -> Siemens LLM gateway / OpenAI
     (default model from config.LLM_MODEL; override with LLM_BASE_URL for other gateways)
  3. neither             -> offline keyword fallbacks throughout the app
"""
from __future__ import annotations

import os
import re
import json
from typing import Optional

from .config import LLM_MODEL, LLM_TIMEOUT

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_DEFAULT_MODEL = "gemini-2.5-flash"


def openai_api_key() -> str:
    """LLM gateway API key from OPENAI_API_KEY. Stray angle brackets/whitespace are stripped."""
    return os.getenv("OPENAI_API_KEY", "").strip().strip("<>").strip()


def gemini_api_key() -> str:
    return os.getenv("GEMINI_API_KEY", "").strip().strip("<>").strip()


# OpenAI-compatible gateway default (used for the OPENAI_API_KEY provider). The Siemens
# gateway authenticates via an 'x-api-key' header (not Bearer), so we pass the key both
# as the SDK api_key and as a default x-api-key header. Override with LLM_BASE_URL.
LLM_BASE_URL = (os.getenv("LLM_BASE_URL") or "https://llm.sdc.siemens.cloud/v1").strip()
# Floor for the per-call token budget: reasoning models consume hidden tokens before the
# visible answer, so a tiny cap can yield empty content.
LLM_MIN_BUDGET = int(os.getenv("LLM_MIN_BUDGET", "1024"))


class LLMClient:
    def __init__(self):
        gem, oai = gemini_api_key(), openai_api_key()
        self.provider = "gemini" if gem else ("openai" if oai else "none")
        self.key = gem or oai
        self.available = bool(self.key)
        self._client = None
        if self.provider == "gemini":
            self.base_url = GEMINI_BASE_URL
            # honour an explicit LLM_MODEL env override, else use the Gemini default
            self.model = os.getenv("LLM_MODEL", "").strip() or GEMINI_DEFAULT_MODEL
        else:
            self.base_url = LLM_BASE_URL
            self.model = LLM_MODEL
        if self.available:
            try:
                from openai import OpenAI
                headers = {} if self.provider == "gemini" else {"x-api-key": self.key}
                self._client = OpenAI(api_key=self.key, base_url=self.base_url,
                                      default_headers=headers,
                                      timeout=LLM_TIMEOUT, max_retries=0)
            except Exception as e:
                self.available = False
                self.last_error = str(e)

    last_error: str = ""

    def complete(self, prompt: str, system: str = "", max_tokens: int = 1200) -> str:
        if not self.available:
            return ""
        budget = max(max_tokens, LLM_MIN_BUDGET)
        # Gemini's OpenAI-compat layer expects 'max_tokens'; gpt-5.x reasoning gateways
        # expect 'max_completion_tokens'.
        tok_kw = {"max_tokens": budget} if self.provider == "gemini" \
            else {"max_completion_tokens": budget}
        try:
            resp = self._client.chat.completions.create(
                model=self.model, timeout=LLM_TIMEOUT,
                messages=[
                    {"role": "system",
                     "content": system or "You are a precise startup-evaluation analyst for Siemens."},
                    {"role": "user", "content": prompt},
                ],
                **tok_kw,
            )
            self.last_error = ""
            return resp.choices[0].message.content or ""
        except Exception as e:
            self.last_error = str(e)
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
