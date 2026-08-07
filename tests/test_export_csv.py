import features.export_csv as ec


def test_generate_csv() -> None:
    watched = [
        {
            "company": "Acme Corp",
            "final_score": 84.7,
            "pillar": "tech",
            "created_at": "2023-08-01T12:34:56Z",
        },
        {
            "company": "Beta LLC",
            "final_score": 69.2,
            "pillar": "biz",
            "created_at": "2023-08-02T09:10:11Z",
        },
    ]
    csv_text = ec.generate_csv(watched)
    expected = (
        "company,score,pillar,last_evaluated\n"
        "Acme Corp,85,tech,2023-08-01\n"
        "Beta LLC,69,biz,2023-08-02"
    )
    assert csv_text == expected


def test_exported_message() -> None:
    assert ec.exported_message() == "CSV exported"
