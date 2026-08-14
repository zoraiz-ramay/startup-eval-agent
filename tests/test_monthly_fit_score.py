import pytest
from features.monthly_fit_score import monthly_average


def make_run(date_str: str, score: float | None):
    return {"created_at": date_str, "final_score": score}


def test_monthly_average_multiple_months():
    runs = [
        make_run("2024-01-10T12:00:00Z", 70),
        make_run("2024-01-20T08:30:00Z", 80),
        make_run("2024-02-05T09:00:00Z", 60),
        make_run("2024-02-25T15:45:00Z", 90),
        make_run("2024-03-01T00:00:00Z", 100),
    ]
    result = monthly_average(runs)
    assert len(result) == 3
    # Expect chronological order Jan, Feb, Mar
    assert result[0][0] == "Jan 2024"
    assert result[0][1] == pytest.approx((70 + 80) / 2)
    assert result[1][0] == "Feb 2024"
    assert result[1][1] == pytest.approx((60 + 90) / 2)
    assert result[2][0] == "Mar 2024"
    assert result[2][1] == pytest.approx(100)


def test_monthly_average_single_month():
    runs = [
        make_run("2024-04-01T00:00:00Z", 50),
        make_run("2024-04-15T12:00:00Z", 70),
    ]
    result = monthly_average(runs)
    assert len(result) == 1
    assert result[0][0] == "Apr 2024"
    assert result[0][1] == pytest.approx((50 + 70) / 2)


def test_monthly_average_missing_dates_or_scores():
    runs = [
        {"created_at": "invalid", "final_score": 40},
        {"final_score": 80},  # missing date
        {"created_at": "2024-05-10T00:00:00Z"},  # missing score defaults to 0
    ]
    result = monthly_average(runs)
    # Only the valid May entry should be included with a score of 0
    assert len(result) == 1
    assert result[0][0] == "May 2024"
    assert result[0][1] == 0.0
