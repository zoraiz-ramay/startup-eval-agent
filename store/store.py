# store.py – lightweight JSON store with schema validation
"""Utility functions for reading/writing JSON files used by the multi‑agent system.
All functions raise a clear exception on failure so the Orchestrator can abort.
"""
import json
import os
from typing import Any, Dict

def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)

def load_json(path: str) -> Dict[str, Any]:
    """Load a JSON file and return a dict. Raises FileNotFoundError if missing."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path: str, data: Dict[str, Any]) -> None:
    """Write *data* to *path* atomically (tmp → rename)."""
    _ensure_dir(path)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp_path, path)

def validate_schema(data: Dict[str, Any], schema: Dict[str, Any]) -> bool:
    """Very light‑weight validation – checks required top‑level keys.
    For full validation integrate jsonschema library later.
    """
    required = schema.get("required", [])
    missing = [k for k in required if k not in data]
    if missing:
        raise ValueError(f"Missing required keys {missing} for schema {schema.get('title')}")
    return True
