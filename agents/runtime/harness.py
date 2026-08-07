"""Generic agent harness.

This is the runtime that actually *runs* a markdown-defined agent, the same way
Claude Code runs its agent files: the ``.md`` frontmatter selects the model tier
and declares which tools the agent may use, and the markdown body is the system
prompt. The harness injects a JSON context, calls the LLM, and parses one JSON
object back out.

Agent definition format (``agents/definitions/<name>.md``)::

    ---
    name: coding
    model: expensive          # cheap | expensive | or an explicit model name
    description: Implements a feature as concrete files.
    tools: [pytest, flake8]   # informational; deterministic tools run in the loop
    ---
    <system prompt / instructions in markdown>

Usage::

    from agents.runtime.harness import run_agent
    result = run_agent("product_planner", {"already_shipped": [...]})
    result["output"]   # parsed JSON dict (or None if the model returned no JSON)
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import types

# make the repo root importable so ``core`` resolves no matter the CWD
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_llm_client_cls():
    """Import ``core.llm.LLMClient`` without triggering ``core/__init__``.

    The real ``core`` package eagerly imports heavy app dependencies (pandas etc.)
    that the light agent runtime does not need. We register a minimal stand-in
    ``core`` package and load only ``config`` + ``llm`` from their source files,
    reusing the exact same client the app uses.
    """
    core_dir = REPO_ROOT / "core"
    if "core" not in sys.modules or not hasattr(sys.modules["core"], "__path__"):
        pkg = types.ModuleType("core")
        pkg.__path__ = [str(core_dir)]  # type: ignore[attr-defined]
        sys.modules["core"] = pkg
    for name in ("config", "llm"):
        full = f"core.{name}"
        if full not in sys.modules:
            spec = importlib.util.spec_from_file_location(full, core_dir / f"{name}.py")
            mod = importlib.util.module_from_spec(spec)
            sys.modules[full] = mod
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return sys.modules["core.llm"].LLMClient


LLMClient = _load_llm_client_cls()

from agents.runtime.models import (  # noqa: E402
    resolve_model, resolve_tier, tier_credentials,
)

DEFINITIONS = pathlib.Path(__file__).resolve().parents[1] / "definitions"

# one client per tier (cheap / expensive), each with its own key + base URL
_CLIENTS: dict[str, "LLMClient"] = {}


def _client_for(tier: str) -> "LLMClient":
    """Return a cached LLMClient for the tier, built with that tier's credentials."""
    canonical = resolve_tier(tier)
    client = _CLIENTS.get(canonical)
    if client is None:
        key, base_url = tier_credentials(canonical)
        client = LLMClient(key=key, base_url=base_url, model=resolve_model(canonical))
        _CLIENTS[canonical] = client
    return client



def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split a markdown file into (frontmatter_dict, body).

    Supports a minimal YAML subset: ``key: value`` scalars and inline lists
    ``key: [a, b, c]``. Avoids a PyYAML dependency.
    """
    meta: dict = {}
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            raw = text[3:end].strip()
            body = text[end + 4:].lstrip("\n")
            for line in raw.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or ":" not in line:
                    continue
                key, _, val = line.partition(":")
                key = key.strip()
                val = val.strip()
                if val.startswith("[") and val.endswith("]"):
                    items = [v.strip().strip("'\"") for v in val[1:-1].split(",")]
                    meta[key] = [v for v in items if v]
                else:
                    meta[key] = val.strip("'\"")
    return meta, body


def load_definition(name: str) -> tuple[dict, str]:
    path = DEFINITIONS / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"agent definition not found: {path}")
    return _parse_frontmatter(path.read_text(encoding="utf-8"))


def run_agent(name: str, context: dict, max_tokens: int = 4000,
              model_override: str | None = None) -> dict:
    """Run a markdown-defined agent and return a structured result.

    ``model_override`` (a tier name like "cheap"/"expensive") forces the agent onto
    that tier for this call, overriding its own frontmatter default - used to run an
    otherwise-expensive agent (e.g. coding) on the cheap tier for cost-sensitive runs.

    Returns a dict with keys: agent, model, tier, available, raw, output, error.
    ``output`` is the parsed JSON object the model produced (or None).
    """
    meta, system_prompt = load_definition(name)
    tier = model_override or meta.get("model", "cheap")
    model = resolve_model(tier)

    client = _client_for(tier)
    if not client.available:
        return {
            "agent": name, "model": model, "tier": resolve_tier(tier),
            "available": False, "raw": "", "output": None,
            "error": (f"LLM unavailable for '{resolve_tier(tier)}' tier "
                      f"(set its API key: see agents/runtime/models.py)."),
        }

    user = (
        "CONTEXT (JSON):\n"
        + json.dumps(context, indent=2, ensure_ascii=False)
        + "\n\nRespond with ONLY a single JSON object matching the schema described "
        + "in your instructions. No prose, no markdown fences."
    )
    raw = client.complete(user, system=system_prompt, max_tokens=max_tokens, model=model)
    parsed = LLMClient.parse_json(raw)
    return {
        "agent": name, "model": model, "tier": resolve_tier(tier),
        "available": True, "raw": raw, "output": parsed,
        "error": "" if parsed is not None else (client.last_error or "no JSON in model output"),
    }


if __name__ == "__main__":
    # ad-hoc: python -m agents.runtime.harness <agent_name> '<json-context>'
    _name = sys.argv[1] if len(sys.argv) > 1 else "repo_analysis"
    _ctx = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    print(json.dumps(run_agent(_name, _ctx), indent=2, ensure_ascii=False))
