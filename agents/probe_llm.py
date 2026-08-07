"""Connectivity probe for the agent LLM tiers.

Verifies that each tier's model + key + base URL actually answer, WITHOUT running a
full feature cycle. Run this once after setting your keys to confirm the gateway and
protocol are correct.

    python agents/probe_llm.py            # probe both tiers
    python agents/probe_llm.py cheap      # probe only the cheap tier

Set credentials in your terminal first (values are read from the environment):

    # cheap tier (api.siemens.com/llm) -- ANTHROPIC_* names from the portal work too
    $env:OPENAI_API_KEY_CHEAP = "SIAK-..."       # or $env:ANTHROPIC_AUTH_TOKEN
    # expensive tier (llm.sdc.siemens.cloud)
    $env:OPENAI_API_KEY_EXPENSIVE = "..."
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.runtime import harness, models  # noqa: E402


def probe(tier: str) -> bool:
    key, base = models.tier_credentials(tier)
    model = models.resolve_model(tier)
    canonical = models.resolve_tier(tier)
    print(f"\n=== {canonical} tier ===")
    print(f"  model    : {model}")
    print(f"  base_url : {base or '(default)'}")
    print(f"  key set  : {'yes' if key else 'NO -- set it first'}")
    if not key:
        return False

    client = harness._client_for(tier)
    if not client.available:
        print(f"  RESULT   : client unavailable ({client.last_error or 'unknown'})")
        return False

    reply = client.complete(
        "Reply with exactly the word: OK",
        system="You are a connectivity probe. Answer with a single word.",
        max_tokens=16,
        model=model,
    )
    if reply.strip():
        print(f"  RESULT   : OK -- gateway answered: {reply.strip()[:60]!r}")
        return True
    print(f"  RESULT   : FAILED -- no response. last_error: {client.last_error or 'empty'}")
    print("             If this is a 404, the base URL may need a '/v1' suffix.")
    print("             If this is a 401/403, check the token/header for this gateway.")
    return False


def main() -> int:
    tiers = sys.argv[1:] or ["cheap", "expensive"]
    ok = all(probe(t) for t in tiers)
    print("\n" + ("All probed tiers responded." if ok else "One or more tiers failed -- see above."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
