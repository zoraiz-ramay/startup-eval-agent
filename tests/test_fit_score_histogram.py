def test_fit_score_histogram_placeholder():
    buckets = [
        (0, 20),
        (21, 40),
        (41, 60),
        (61, 80),
        (81, 100),
    ]
    assert len(buckets) == 5
    assert buckets[0] == (0, 20)
    assert buckets[-1] == (81, 100)
