from unittest.mock import Mock
from core.collaborate_profile import extract_tech_profile, TECH_PROFILE_VERSION

RUN = {"company": "Alpha", "summary": "Industrial inspection software with two customer pilots.",
       "deep_profile": {"founders": [{"name": "Jane", "background": "Machine vision engineering"}]}}


def llm(data):
    model = Mock(available=True)
    model.complete.return_value = "irrelevant-raw-text"
    model.parse_json.return_value = data
    return model


def test_extracts_and_normalizes_terms_from_existing_evidence():
    data = {"technologies": ["Computer Vision", "computer vision", "  Edge AI  "],
            "capabilities": ["Defect detection"], "use_cases": ["Quality control"]}
    result = extract_tech_profile(RUN, llm(data))
    assert result["status"] == "assessed"
    assert result["version"] == TECH_PROFILE_VERSION
    assert result["technologies"] == ["computer vision", "edge ai"]  # deduped, lowercased
    assert result["capabilities"] == ["defect detection"]
    assert result["use_cases"] == ["quality control"]
    model = Mock(available=True); model.parse_json.return_value = data
    extract_tech_profile(RUN, model)
    assert "Machine vision engineering" in model.complete.call_args.args[0]


def test_caps_each_bucket_at_ten_terms():
    data = {"technologies": [f"tech{i}" for i in range(15)], "capabilities": [], "use_cases": []}
    result = extract_tech_profile(RUN, llm(data))
    assert len(result["technologies"]) == 10


def test_degrades_when_the_model_is_unavailable_or_returns_invalid_json():
    result = extract_tech_profile(RUN, Mock(available=False))
    assert result["status"] == "unavailable"
    assert result["technologies"] == result["capabilities"] == result["use_cases"] == []

    model = Mock(available=True); model.parse_json.return_value = None
    assert extract_tech_profile(RUN, model)["status"] == "unavailable"

    model = Mock(available=True); model.parse_json.return_value = {"technologies": "not-a-list"}
    result = extract_tech_profile(RUN, model)
    assert result["status"] == "assessed" and result["technologies"] == []


def test_no_evidence_never_reaches_the_model():
    model = Mock(available=True)
    result = extract_tech_profile({}, model)
    assert result["status"] == "unavailable"
    model.complete.assert_not_called()
