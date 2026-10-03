"""The Siemens-fit match call gets time to finish, and a run records the model that produced it.

Both were found by the first SigNoz trace of a real evaluation (Wandelbots, 90s):

- pipeline.fit took 65s of it. The final match call needs ~35s on Gemini 2.5 Flash (34.5-36.2s
  over three measured runs) and LLM_TIMEOUT is 30s, so its first attempt was always killed and
  retried, and a run where every attempt died fell back to keyword matching silently — 11 of 52
  stored runs did, with a working model.
- The result's `engine` said openai:gpt-5.4 while every span in the trace was gemini-2.5-flash.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core import fit, llm as llm_mod, pipeline  # noqa: E402
from core.config import LLM_TIMEOUT  # noqa: E402
from tests.test_evaluate_stream import offline, _run  # noqa: E402,F401  (fixture reuse)

# The slowest match call measured. A timeout below this kills a call that was going to succeed.
MEASURED_MATCH_SECONDS = 36.2

TOOLS = [{"product": "Process Simulate", "category": "Robotics simulation", "division": "DI SW",
          "description": "Robot programming and simulation for production lines"}]


class _RecordingLLM:
    """Answers like a model that is available, and records how each call was made."""

    available = True
    provider, model = "gemini", "gemini-2.5-flash"

    def __init__(self):
        self.calls = []

    def complete(self, prompt, **kw):
        self.calls.append((prompt, kw))
        if "Return ONLY JSON: {\"keywords\"" in prompt:
            return '{"keywords": ["robot simulation", "robot programming"]}'
        return ('{"aligned": true, "matches": [{"tool": "Process Simulate", "division": "DI SW",'
                ' "confidence": 70, "relation": "complement", "rationale": "r"}]}')

    def __getattr__(self, name):
        # Any other stage's helper: behave like a model that had nothing to say.
        return lambda *a, **kw: None


def test_the_match_call_is_allowed_longer_than_it_measurably_takes():
    llm = _RecordingLLM()
    row = pd.Series({"company_name": "Wandelbots", "short_description": "Robot OS for factories"})
    result = fit.match_siemens_tools(row, "", TOOLS, llm)

    assert result["method"] == "llm"
    _, match_kw = next(c for c in llm.calls if "SIEMENS PORTFOLIO" in c[0])
    assert match_kw["timeout"] > MEASURED_MATCH_SECONDS > LLM_TIMEOUT
    # Bounded, so a hung provider cannot outlast gunicorn's 300s worker timeout on its own.
    assert match_kw["timeout"] * match_kw["max_attempts"] < 300


def test_complete_sends_the_per_call_timeout_and_defaults_to_the_global(monkeypatch):
    sent = []

    class _Completions:
        def create(self, **kw):
            sent.append(kw["timeout"])

            class R:
                choices = [type("C", (), {"message": type("M", (), {"content": "ok"})()})()]
            return R()

    client = llm_mod.LLMClient.__new__(llm_mod.LLMClient)
    client.available, client.provider, client.model = True, "gemini", "gemini-2.5-flash"
    client.last_error = ""
    client._client = type("Client", (), {"chat": type("Chat", (), {"completions": _Completions()})()})()
    monkeypatch.setattr(llm_mod, "LLM_CACHE", False)

    assert client.complete("a", timeout=90) == "ok"
    assert client.complete("b") == "ok"
    assert sent == [90, LLM_TIMEOUT]


def test_engine_names_the_provider_and_model_that_ran(offline, monkeypatch):
    df, tools = offline
    monkeypatch.setattr(pipeline, "LLMClient", lambda *a, **kw: _RecordingLLM())
    result = _run(df, tools)
    assert result["engine"].startswith("gemini:gemini-2.5-flash")
    assert "openai" not in result["engine"]
