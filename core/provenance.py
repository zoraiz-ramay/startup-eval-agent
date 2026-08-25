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
        """Days since this evidence was retrieved, or -1 when the timestamp is unusable.

        Only meaningful against a LIVE Fact. It is deliberately not serialised — see `as_dict`.
        """
        try:
            ts = _dt.datetime.fromisoformat(self.retrieved_at)
            return max(0, (_dt.datetime.now(_dt.timezone.utc) - ts).days)
        except Exception:
            return -1

    def as_dict(self) -> dict:
        """The stored form. Note what is NOT in it: `freshness_days`.

        It used to be, and it was a stored constant zero — every Fact is built during the run that
        gathers it, so the age is always 0 at serialisation time, and it then sat frozen in
        `result_json` while the run aged. A two-year-old evaluation reported its evidence as
        retrieved today. Nothing ever read the field, which is the only reason it was never
        noticed. `retrieved_at` is the durable fact; age is derived from it at read time, by
        whoever is doing the reading and against their own clock.
        """
        return asdict(self)
