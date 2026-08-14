from features.alerts_loading import get_alerts_state


def test_loading_state():
    assert get_alerts_state(None, "") == "loading"


def test_error_state():
    assert get_alerts_state(None, "network error") == "error"
    assert get_alerts_state([], "api failure") == "error"


def test_empty_state():
    assert get_alerts_state([], "") == "empty"


def test_data_state():
    sample = [{"id": 1, "company": "Acme"}]
    assert get_alerts_state(sample, "") == "data"
