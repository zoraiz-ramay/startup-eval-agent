from features.quality_badge import get_quality_badge


def test_known_qualities():
    high = get_quality_badge("high")
    assert high["label"] == "High"
    assert high["background"] == "#d4edda"
    assert high["color"] == "#155724"

    medium = get_quality_badge("Medium")
    assert medium["label"] == "Medium"
    assert medium["background"] == "#fff3cd"
    assert medium["color"] == "#856404"

    low = get_quality_badge("LOW")
    assert low["label"] == "Low"
    assert low["background"] == "#f8d7da"
    assert low["color"] == "#721c24"


def test_unknown_quality():
    unknown = get_quality_badge("unknown")
    assert unknown["label"] == "unknown"
    assert unknown["background"] == "#e0e0e0"
    assert unknown["color"] == "#000000"


def test_none_and_empty():
    empty = get_quality_badge("")
    assert empty["label"] == ""
    assert empty["background"] == "#e0e0e0"
    assert empty["color"] == "#000000"

    none_val = get_quality_badge(None)
    assert none_val["label"] == ""
    assert none_val["background"] == "#e0e0e0"
    assert none_val["color"] == "#000000"
