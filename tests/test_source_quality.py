from features.source_quality.scoring import score_source


def test_scores_independent_sources_higher_than_promotional_vendor_pages() -> None:
    gov_source = score_source(
        url="https://www.energy.gov/articles/grid-modernization-update",
        title="Grid modernization update",
        snippet="A federal program update with implementation details.",
        author="U.S. Department of Energy",
        published_at="2024-01-12",
    )
    vendor_source = score_source(
        url="https://acmecrm.com/pricing/book-demo",
        title="Book a demo for Acme CRM",
        snippet="Try now and contact sales for enterprise pricing.",
        author="",
        published_at="",
    )

    assert gov_source["quality_score"] > vendor_source["quality_score"]
    assert vendor_source["quality_breakdown"]["promotional_signals"] >= 2


def test_scoring_is_deterministic() -> None:
    kwargs = {
        "url": "https://www.reuters.com/markets/deals/example-story",
        "title": "Example deal coverage",
        "snippet": "Reuters reports on a funding round.",
        "author": "Staff",
        "published_at": "2024-05-01",
    }

    first = score_source(**kwargs)
    second = score_source(**kwargs)

    assert first == second


def test_missing_metadata_and_malformed_url_are_handled_gracefully() -> None:
    result = score_source(
        url="not-a-valid-url",
        title="Anonymous landing page",
        snippet="Sign up now for the best solution.",
        author=None,
        published_at=None,
    )

    assert isinstance(result["quality_score"], int)
    assert 0 <= result["quality_score"] <= 100
    breakdown = result["quality_breakdown"]
    assert breakdown["domain_type"] in {"unknown", "commercial", "vendor"}
    assert breakdown["attribution_present"] is False
    assert breakdown["date_present"] is False
    assert isinstance(breakdown["reasoning"], str)


def test_breakdown_contains_required_fields_for_news_source() -> None:
    result = score_source(
        url="https://www.bbc.com/news/technology-123456",
        title="Technology report",
        snippet="Independent reporting on startup infrastructure.",
        author="Jane Reporter",
        published_at="2024-02-11",
    )

    breakdown = result["quality_breakdown"]
    assert set(breakdown.keys()) == {
        "domain_type",
        "attribution_present",
        "date_present",
        "promotional_signals",
        "reasoning",
    }
    assert breakdown["domain_type"] == "news"
