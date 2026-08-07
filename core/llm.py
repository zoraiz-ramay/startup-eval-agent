"""OpenAI-compatible LLM client for the Siemens LLM gateway.

Uses OPENAI_API_KEY with the Siemens gateway at llm.sdc.siemens.cloud.
The gateway authenticates via an 'x-api-key' header.
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
LLM_MIN_BUDGET = int(os.getenv("LLM_MIN_BUDGET", "1024"))
MAX_RETRIES = 3
RETRY_BACKOFF = 2


def openai_api_key() -> str:
    return os.getenv("OPENAI_API_KEY", "").strip().strip("<>").strip()


class LLMClient:
    def __init__(self, key: str = "", base_url: str = "", model: str = ""):
        self.key = (key or openai_api_key()).strip().strip("<>").strip()
        self.provider = "openai" if self.key else "none"
        self.available = bool(self.key)
        self.base_url = (base_url or LLM_BASE_URL).strip()
        self.model = model or LLM_MODEL
        self._client = None
        self.last_error: str = ""

        if self.available:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.key,
                    base_url=self.base_url,
                    default_headers={"x-api-key": self.key},
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
