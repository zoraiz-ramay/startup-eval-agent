"""Plain-language summary of what a startup does, for a Siemens reviewer."""
from __future__ import annotations

import pandas as pd

from .llm import LLMClient


def summarize_offering(row: pd.Series, pitch_pdf: str, llm: LLMClient) -> str:
    pitch = " ".join(str(row.get(c, "")) for c in
                     ("Your pitch", "short_description", "Differentiation", "about_enriched"))
    if llm.available:
        prompt = (f"Summarize what this startup does in 2-3 plain sentences for a Siemens reviewer.\n\n"
                  f"Company: {row.get('company_name','')}\nPitch/desc: {pitch}\n"
                  f"Deck excerpt: {pitch_pdf[:2000]}")
        out = llm.complete(prompt, max_tokens=300).strip()
        if out:
            return out
    # offline fallback
    sd = str(row.get("short_description", "")).strip() or str(row.get("Your pitch", "")).strip()
    return (sd[:400] + ("…" if len(sd) > 400 else "")) or "No description available."
