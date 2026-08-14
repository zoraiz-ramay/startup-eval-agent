from features.profile_dimension_radar.logic import should_show_radar


def test_radar_shown_when_any_field_present():
    run = {"traction": 5, "market": None}
    assert should_show_radar(run) is True


def test_radar_not_shown_when_no_fields():
    run = {"some_other": 1}
    assert should_show_radar(run) is False


def test_radar_not_shown_when_fields_null():
    run = {"traction": None, "market": None}
    assert should_show_radar(run) is False


def test_radar_not_shown_when_run_is_none():
    assert should_show_radar(None) is False
