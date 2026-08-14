from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Sequence


@dataclass(frozen=True)
class SentenceSupport:
    sentence_text: str
    unsupported: bool
    evidence_ids: List[str]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "sentence_text": self.sentence_text,
            "unsupported": self.unsupported,
            "evidence_ids": list(self.evidence_ids),
        }


def _normalize_evidence_ids(raw_ids: Iterable[Any]) -> List[str]:
    normalized: List[str] = []
    seen = set()
    for raw in raw_ids:
        text = str(raw).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _extract_evidence_ids(
    sentence: Mapping[str, Any],
    matrix_entries: Sequence[Mapping[str, Any]],
    index: int,
) -> List[str]:
    direct = sentence.get("evidence_ids")
    if isinstance(direct, list):
        return _normalize_evidence_ids(direct)

    sentence_id = sentence.get("sentence_id")
    collected: List[Any] = []
    for entry in matrix_entries:
        entry_sentence_id = entry.get("sentence_id")
        entry_index = entry.get("sentence_index")
        matches = False
        if sentence_id is not None and entry_sentence_id == sentence_id:
            matches = True
        elif entry_index == index:
            matches = True

        if not matches:
            continue

        evidence_ids = entry.get("evidence_ids")
        if isinstance(evidence_ids, list):
            collected.extend(evidence_ids)

        single_id = entry.get("evidence_id")
        if single_id is not None:
            collected.append(single_id)
    return _normalize_evidence_ids(collected)


def build_sentence_support(
    claim_sentences: Sequence[Mapping[str, Any]],
    claim_evidence_matrix: Sequence[Mapping[str, Any]],
) -> List[SentenceSupport]:
    support_rows: List[SentenceSupport] = []
    for index, sentence in enumerate(claim_sentences):
        sentence_text = str(sentence.get("text", "")).strip()
        evidence_ids = _extract_evidence_ids(sentence, claim_evidence_matrix, index)
        support_rows.append(
            SentenceSupport(
                sentence_text=sentence_text,
                unsupported=len(evidence_ids) == 0,
                evidence_ids=evidence_ids,
            )
        )
    return support_rows


def summarize_unsupported(rows: Sequence[SentenceSupport]) -> Dict[str, int]:
    unsupported_count = sum(1 for row in rows if row.unsupported)
    return {
        "unsupported_claim_count": unsupported_count,
        "supported_claim_count": len(rows) - unsupported_count,
        "total_claim_count": len(rows),
    }
