from features.section_confidence.scoring import SectionSignals, score_section_confidence


def test_high_confidence_for_supported_high_quality_section() -> None:
    result = score_section_confidence(
        SectionSignals(
            supported_claim_ratio=1.0,
            average_source_quality=0.9,
            unsupported_claims_present=False,
            evidence_backed_claim_count=3,
        )
    )

    assert result.confidence == "high"
    assert result.rationale["unsupported_claims_present"] is False


def test_medium_confidence_for_mixed_support_medium_quality() -> None:
    result = score_section_confidence(
        SectionSignals(
            supported_claim_ratio=0.6,
            average_source_quality=0.5,
            unsupported_claims_present=False,
            evidence_backed_claim_count=4,
        )
    )

    assert result.confidence == "medium"
    assert "medium" in result.rationale["rule_applied"]


def test_unsupported_claims_prevent_high_confidence() -> None:
    result = score_section_confidence(
        SectionSignals(
            supported_claim_ratio=0.95,
            average_source_quality=0.95,
            unsupported_claims_present=True,
            evidence_backed_claim_count=5,
        )
    )

    assert result.confidence == "medium"
    assert "not_high" in result.rationale["rule_applied"]


def test_no_evidence_backed_claims_are_always_low() -> None:
    result = score_section_confidence(
        SectionSignals(
            supported_claim_ratio=1.0,
            average_source_quality=1.0,
            unsupported_claims_present=False,
            evidence_backed_claim_count=0,
        )
    )

    assert result.confidence == "low"
    assert result.rationale["evidence_backed_claim_count"] == 0


def test_scoring_is_deterministic_for_same_fixture() -> None:
    signals = SectionSignals(
        supported_claim_ratio=0.72,
        average_source_quality=0.63,
        unsupported_claims_present=False,
        evidence_backed_claim_count=2,
    )

    first = score_section_confidence(signals)
    second = score_section_confidence(signals)

    assert first == second
