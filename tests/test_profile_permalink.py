import os
import importlib

# Reload the module each test to avoid env var side‑effects
def load_module():
    if "features.profile_permalink" in importlib.sys.modules:
        del importlib.sys.modules["features.profile_permalink"]
    return importlib.import_module("features.profile_permalink")

def test_build_permalink_with_origin(monkeypatch):
    monkeypatch.setenv("ORIGIN", "https://example.com")
    mod = load_module()
    assert mod.build_permalink("abc123") == "https://example.com/startup/abc123"

def test_build_permalink_default_origin(monkeypatch):
    # Ensure ORIGIN is unset
    monkeypatch.delenv("ORIGIN", raising=False)
    mod = load_module()
    assert mod.build_permalink("xyz") == "http://localhost/startup/xyz"
