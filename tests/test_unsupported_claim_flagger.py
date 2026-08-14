from typing import Any, Mapping, Sequence

from features.unsupported_claim_flagger import (
    build_sentence_support,
    summarize_unsupported,
)


def test_build_sentence_support_marks_supported_and_unsupported_claims() -> None:
    claim_sentences: Sequence[Mapping[str, Any]] = [
        {"sentence_id": "s1", "text": "Revenue grew quickly."},
        {"sentence_id": "s2", "text": "The market is guaranteed to expand."},
        {"sentence_id": "s3", "text": "Customer churn improved."},
    ]
    matrix: Sequence[Mapping[str, Any]] = [
        {"sentence_id": "s1", "evidence_ids": ["e1", "e2"]},
        {"sentence_id": "s3", "evidence_id": "e3"},
    ]

    rows = build_sentence_support(claim_sentences, matrix)

    assert [row.unsupported for row in rows] == [False, True, False]
    assert rows[0].evidence_ids == ["e1", "e2"]
    assert rows[1].evidence_ids == []
    assert rows[2].evidence_ids == ["e3"]


def test_build_sentence_support_uses_direct_sentence_evidence_ids_when_present() -> None:
    claim_sentences: Sequence[Mapping[str, Any]] = [
        {"text": "Claim A", "evidence_ids": ["a1", "a1", " ", "a2"]},
        {"text": "Claim B", "evidence_ids": []},
    ]

    rows = build_sentence_support(claim_sentences, [])

    assert rows[0].unsupported is False
    assert rows[0].evidence_ids == ["a1", "a2"]
    assert rows[1].unsupported is True


def test_summarize_unsupported_counts_rows() -> None:
    rows = build_sentence_support(
        [
            {"sentence_id": "one", "text": "Supported claim."},
            {"sentence_id": "two", "text": "Unsupported claim."},
        ],
        [{"sentence_id": "one", "evidence_ids": ["ev-1"]}],
    )

    summary = summarize_unsupported(rows)

    assert summary == {
        "unsupported_claim_count": 1,
        "supported_claim_count": 1,
        "total_claim_count": 2,
    }
