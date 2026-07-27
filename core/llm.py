"""Azure OpenAI LLM client.

Uses AZURE_OPEN_AI_ENDPOINT and AZURE_OPEN_AI_KEY env vars.
Default deployment: gpt-4o (override with LLM_MODEL).
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

MAX_RETRIES = 3
RETRY_BACKOFF = 2


class LLMClient:
    def __init__(self):
        self.endpoint = os.getenv("AZURE_OPEN_AI_ENDPOINT", "").strip().rstrip("/")
        self.key = os.getenv("AZURE_OPEN_AI_KEY", "").strip()
        self.model = LLM_MODEL
        self.provider = "azure_openai" if (self.endpoint and self.key) else "none"
        self.available = self.provider != "none"
        self._client = None
        self.last_error: str = ""

        if self.available:
            try:
                from openai import AzureOpenAI
                self._client = AzureOpenAI(
                    azure_endpoint=self.endpoint,
                    api_key=self.key,
                    api_version="2024-12-01-preview",
                    timeout=LLM_TIMEOUT,
                    max_retries=0,
                )
            except Exception as e:
                self.available = False
                self.last_error = str(e)

    def complete(self, prompt: str, system: str = "", max_tokens: int = 1200) -> str:
        if not self.available:
            return ""
        msgs = [
            {"role": "system",
             "content": system or "You are a precise startup-evaluation analyst for Siemens."},
            {"role": "user", "content": prompt},
        ]
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self._client.chat.completions.create(
                    model=self.model,
                    messages=msgs,
                    max_tokens=max_tokens,
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
