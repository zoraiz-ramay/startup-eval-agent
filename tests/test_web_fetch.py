"""Unit tests for the SSRF-guarded direct site fetch in core/web.py.

core/__init__.py imports pandas (heavy), so we load web.py as a standalone module by
file path to keep these tests dependency-light and network-free. Every assertion here
either exercises pure string logic (_strip_html) or the SSRF guard, so no real HTTP
request is ever made.
"""
import importlib.util
import os

_WEB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "core", "web.py"))
_spec = importlib.util.spec_from_file_location("core_web_standalone", _WEB_PATH)
web = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(web)


def test_strip_html_removes_tags_and_scripts():
    html = ("<html><head><style>.x{color:red}</style>"
            "<script>alert(1)</script></head>"
            "<body><h1>Acme</h1><p>Part&nbsp;of the Foo &amp; Bar ecosystem.</p>"
            "</body></html>")
    text = web._strip_html(html)
    assert "alert(1)" not in text
    assert "color:red" not in text
    assert "Acme" in text
    assert "Part of the Foo & Bar ecosystem." in text


def test_is_public_host_rejects_loopback_and_private():
    assert web._is_public_host("127.0.0.1") is False
    assert web._is_public_host("localhost") is False
    assert web._is_public_host("10.0.0.5") is False
    assert web._is_public_host("192.168.1.1") is False
    assert web._is_public_host("169.254.169.254") is False   # cloud metadata endpoint
    assert web._is_public_host("") is False


def test_fetch_url_rejects_bad_scheme_and_ssrf():
    assert web.fetch_url("") == ""
    assert web.fetch_url("ftp://example.com/file") == ""
    assert web.fetch_url("file:///etc/passwd") == ""
    # Private/loopback targets must be blocked BEFORE any network call is attempted.
    assert web.fetch_url("http://127.0.0.1/") == ""
    assert web.fetch_url("http://169.254.169.254/latest/meta-data/") == ""


def test_fetch_site_text_empty_domain():
    assert web.fetch_site_text("") == {}
    assert web.fetch_site_text("   ") == {}
