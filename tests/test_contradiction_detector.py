from features.contradiction_detector.detector import detect_contradictions
from features.contradiction_detector.models import Claim, SourceRef
from features.contradiction_detector.normalization import normalize_claim_value


def test_normalize_equivalent_money_values_match() -> None:
    left = normalize_claim_value("funding_total", "$2M")
    right = normalize_claim_value("funding_total", "2 million USD")
    assert left == "USD:2000000"
    assert left == right


def test_normalize_date_and_year_topics() -> None:
    assert normalize_claim_value("launch_date", "January 2023") == "2023-01-01"
    assert normalize_claim_value("founding_year", "Founded in 2019") == 2019


def test_detects_distinct_values_for_same_topic_and_entity() -> None:
    source_a = SourceRef(source_id="a", title="A")
    source_b = SourceRef(source_id="b", title="B")
    claims = [
        Claim(
            topic="employee_count",
            entity="Acme",
            value="50 employees",
            section="team",
            source=source_a,
        ),
        Claim(
            topic="employee_count",
            entity="Acme",
            value="75 employees",
            section="team",
            source=source_b,
        ),
    ]

    contradictions = detect_contradictions(claims)

    assert len(contradictions) == 1
    contradiction = contradictions[0]
    assert contradiction.topic == "employee_count"
    assert {item.normalized_value for item in contradiction.values} == {50, 75}
    assert {item.source.source_id for item in contradiction.values} == {"a", "b"}


def test_equivalent_normalized_values_are_not_flagged() -> None:
    source_a = SourceRef(source_id="a", title="A")
    source_b = SourceRef(source_id="b", title="B")
    claims = [
        Claim(
            topic="funding_total",
            entity="Acme",
            value="$2M",
            section="funding",
            source=source_a,
        ),
        Claim(
            topic="funding_total",
            entity="Acme",
            value="2 million USD",
            section="funding",
            source=source_b,
        ),
    ]

    contradictions = detect_contradictions(claims)

    assert contradictions == []


def test_unsupported_topics_are_ignored() -> None:
    source = SourceRef(source_id="a", title="A")
    claims = [
        Claim(
            topic="market_size",
            entity="Acme",
            value="large",
            section="market",
            source=source,
        )
    ]

    assert detect_contradictions(claims) == []
