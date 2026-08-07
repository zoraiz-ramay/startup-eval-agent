from features.evaluation_reproducibility import (
    build_reproducibility_log,
    ensure_list_of_strings,
)


def test_builder_includes_required_fields_with_defaults() -> None:
    payload = build_reproducibility_log()

    assert payload["run_id"]
    assert payload["timestamp"].endswith("Z")
    assert payload["startup_name"] is None
    assert payload["query"] is None
    assert payload["steps_executed"] == []
    assert payload["source_urls_considered"] == []
    assert payload["source_urls_used"] == []
    assert payload["used_source_count"] == 0
    assert payload["model_identifiers"] == []
    assert payload["report_id"] is None
    assert payload["evaluation_id"] is None
    assert payload["final_report_ref"] is None
    assert payload["extra"] == {}


def test_builder_normalizes_and_deduplicates_inputs() -> None:
    payload = build_reproducibility_log(
        startup_name="Acme AI",
        query="Evaluate Acme AI",
        steps_executed=["collect_sources", "score_sources", "draft_report"],
        source_urls_considered=[
            "https://example.com/a",
            "https://example.com/a",
            " https://example.com/b ",
        ],
        source_urls_used=[
            "https://example.com/b",
            None,
            "https://example.com/c",
            "https://example.com/b",
        ],
        model_identifiers=["gpt-4", "gpt-4", "judge-v1"],
        report_id="report-123",
        evaluation_id="eval-456",
        run_id="run-789",
        timestamp="2025-01-01T00:00:00Z",
        extra={"pipeline_version": "1"},
    )

    assert payload["run_id"] == "run-789"
    assert payload["timestamp"] == "2025-01-01T00:00:00Z"
    assert payload["source_urls_considered"] == [
        "https://example.com/a",
        "https://example.com/b",
    ]
    assert payload["source_urls_used"] == [
        "https://example.com/b",
        "https://example.com/c",
    ]
    assert payload["used_source_count"] == 2
    assert payload["model_identifiers"] == ["gpt-4", "judge-v1"]
    assert payload["final_report_ref"] == "report-123"
    assert payload["extra"] == {"pipeline_version": "1"}


def test_ensure_list_of_strings_filters_empty_values() -> None:
    result = ensure_list_of_strings([None, "  ", "alpha", 42])

    assert result == ["alpha", "42"]
