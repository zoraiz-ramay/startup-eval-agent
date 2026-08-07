from features.alerts_export_csv.util import generate_tracked_companies_csv


def test_generate_tracked_companies_csv_basic():
    watched = [
        {
            "company": "Acme Corp",
            "score": 85,
            "pillar": "growth",
            "last_evaluated": "2023-01-01",
        },
        {
            "company": "Beta Ltd",
            "score": 70,
            "pillar": "risk",
            "last_evaluated": "2023-02-15",
        },
    ]
    csv_text = generate_tracked_companies_csv(watched)
    lines = csv_text.strip().splitlines()
    assert lines[0] == "company,score,pillar,last_evaluated"
    assert lines[1] == "Acme Corp,85,growth,2023-01-01"
    assert lines[2] == "Beta Ltd,70,risk,2023-02-15"
