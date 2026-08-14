"""The Fact dataclass — a single piece of evidence carrying full provenance."""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field, asdict
from typing import Any

# How evidence was obtained -> what kind of source it is.
#   self_reported: the startup's own application/pitch data
#   public: found on the open web with a source URL
#   inferred: derived by the model/heuristics, no direct source
#   private: from a licensed source with no publicly linkable URL
_METHOD_SOURCE_TYPE = {
    "glassdollar_db": "self_reported",
    # The GlassDollar REST API is a curated third-party database, not the startup writing
    # about itself and not something a reader can open in a browser. It is deliberately
    # neither "self_reported" (GlassDollar corroborates across LinkedIn/Crunchbase/PitchBook
    # rather than taking the pitch form at its word) nor "public" — a "public" claim with no
    # URL is demoted to "inferred" below, and this is not an inference either.
    "glassdollar_api": "private",
    "pitch_pdf": "self_reported",
    "ddg_search": "public",
    "profile_research": "public",
    "derived": "inferred",
}


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


@dataclass
class Fact:
    """A single piece of evidence with provenance."""
    key: str
    value: Any
    source_url: str = ""
    method: str = ""          # glassdollar_db | pitch_pdf | ddg_search | profile_research | derived
    confidence: float = 0.5   # 0..1
    verified: bool = False
    retrieved_at: str = field(default_factory=_now)
    source_type: str = ""     # self_reported | public | inferred | private

    def __post_init__(self):
        if not self.source_type:
            st = _METHOD_SOURCE_TYPE.get(self.method, "inferred")
            # a "public" claim without an actual URL is really an inference
            if st == "public" and not str(self.source_url).startswith("http"):
                st = "inferred"
            self.source_type = st

    @property
    def freshness_days(self) -> int:
        try:
            ts = _dt.datetime.fromisoformat(self.retrieved_at)
            return max(0, (_dt.datetime.now(_dt.timezone.utc) - ts).days)
        except Exception:
            return -1

    def as_dict(self) -> dict:
        d = asdict(self)
        d["freshness_days"] = self.freshness_days
        return d
