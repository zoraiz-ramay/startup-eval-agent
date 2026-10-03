"""scripts/prewarm.py decides which startups need evaluating; it never re-evaluates a current one."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.prewarm import plan  # noqa: E402


def test_current_runs_are_skipped_and_names_are_deduplicated_in_order():
    todo, fresh = plan(["Phena", " bliro ", "PHENA", "", "Celonis", "Bliro"],
                       is_current=lambda n: n == "Celonis")
    assert todo == ["Phena", "bliro"]
    assert fresh == ["Celonis"]
