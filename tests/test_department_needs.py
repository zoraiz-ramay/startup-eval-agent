"""core/department_needs.py: the requirements xlsx replaces the five hand-picked demo keywords
per department with Siemens' own stated capability needs. Two things matter here: the real
workbook parses into something richer than the old demo lists, and a missing/broken file degrades
to `{}` rather than raising — the same rule as `GLASSDOLLAR_API_KEY` absence (CLAUDE.md)."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.department_needs import clear_cache, load_department_needs, load_department_requirements  # noqa: E402


def test_real_workbook_yields_rich_term_lists():
    clear_cache()
    needs = load_department_needs()
    assert set(needs) == {"si", "mobility", "di"}
    # The old demo lists were 5 terms each; the real requirements sheet is far larger.
    assert len(needs["si"]) > 15
    assert len(needs["mobility"]) > 20
    assert len(needs["di"]) > 20


def test_each_need_is_a_capability_with_what_it_means():
    clear_cache()
    book = load_department_requirements()
    assert book["si"]["label"] == "Smart Infrastructure"
    first = book["si"]["needs"][0]
    assert first["id"] == "SI-01.1" and first["capability"] == "Process Automation"
    assert first["category"] == "Automate Internal Processes" and first["description"].startswith("Automating")
    assert "workflow automation" in first["keywords"]
    assert sum(len(d["needs"]) for d in book.values()) == 52


def test_no_duplicate_terms_within_a_department():
    clear_cache()
    needs = load_department_needs()
    for dept_id, terms in needs.items():
        assert len(terms) == len(set(terms)), dept_id


def test_missing_file_degrades_to_empty_dict(monkeypatch):
    import core.department_needs as mod

    monkeypatch.setattr(mod, "_XLSX_PATH", mod._XLSX_PATH.parent / "does_not_exist.xlsx")
    clear_cache()
    try:
        assert mod.load_department_needs() == {}
        assert mod.load_department_requirements() == {}
    finally:
        clear_cache()
