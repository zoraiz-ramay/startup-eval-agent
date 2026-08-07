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


# --------------------------------------------------------------- same-site redirect following

def test_same_site_matches_host_and_www_but_not_foreign_hosts():
    assert web._same_site("phena.tech", "phena.tech") is True
    assert web._same_site("phena.tech", "www.phena.tech") is True
    assert web._same_site("phena.tech", "evil.com") is False
    assert web._same_site("phena.tech", "169.254.169.254") is False
    assert web._same_site("", "phena.tech") is False


class _FakeResp:
    def __init__(self, status, headers, body=b""):
        self.status_code, self.headers, self._body = status, headers, body
        self.encoding = "utf-8"

    def iter_content(self, chunk_size=0, decode_unicode=False):
        yield self._body

    def close(self):
        pass


def _patch_requests(monkeypatch, routes, calls):
    """Route fetch_url's HTTP through a table of {url: _FakeResp}, recording every request."""
    import requests

    def fake_get(url, **kwargs):
        calls.append(url)
        return routes.get(url) or _FakeResp(404, {})

    monkeypatch.setattr(requests, "get", fake_get)
    # Every host in these tests is treated as public; the SSRF *decision* under test is the
    # redirect check, which is asserted separately below with a real private target.
    monkeypatch.setattr(web, "_is_public_host",
                        lambda h: h not in ("169.254.169.254", "127.0.0.1", "10.0.0.5"))


def test_fetch_url_follows_same_site_redirect(monkeypatch):
    """A root that 301s to a locale prefix must still yield text.

    This is the phena.tech case the direct-site fetcher exists for: refusing all 3xx made
    every path return '', so the /partners and /ecosystem pages were never read.
    """
    calls = []
    _patch_requests(monkeypatch, {
        "https://phena.tech/": _FakeResp(301, {"Location": "/en"}),
        "https://phena.tech/en": _FakeResp(
            200, {"Content-Type": "text/html"}, b"<p>Part of NVIDIA Inception</p>"),
    }, calls)
    assert web.fetch_url("https://phena.tech/") == "Part of NVIDIA Inception"
    assert calls == ["https://phena.tech/", "https://phena.tech/en"]


def test_fetch_url_refuses_offsite_and_internal_redirect_targets(monkeypatch):
    """The redirect must not become an SSRF hole or an open off-site fetch."""
    calls = []
    _patch_requests(monkeypatch, {
        "https://acme.com/meta": _FakeResp(302, {"Location": "http://169.254.169.254/latest/"}),
        "https://acme.com/away": _FakeResp(302, {"Location": "https://evil.com/"}),
        "http://169.254.169.254/latest/": _FakeResp(200, {"Content-Type": "text/html"}, b"secret"),
        "https://evil.com/": _FakeResp(200, {"Content-Type": "text/html"}, b"evil"),
    }, calls)
    assert web.fetch_url("https://acme.com/meta") == ""
    assert web.fetch_url("https://acme.com/away") == ""
    # Neither redirect target may be requested at all.
    assert calls == ["https://acme.com/meta", "https://acme.com/away"]


def test_fetch_url_stops_after_redirect_budget(monkeypatch):
    """A redirect loop terminates instead of spinning."""
    calls = []
    _patch_requests(monkeypatch, {
        "https://acme.com/a": _FakeResp(301, {"Location": "/b"}),
        "https://acme.com/b": _FakeResp(301, {"Location": "/a"}),
    }, calls)
    assert web.fetch_url("https://acme.com/a") == ""
    assert len(calls) <= web._MAX_REDIRECTS + 1


def test_fetch_site_text_dedupes_paths_resolving_to_same_page(monkeypatch):
    """'/' redirecting to '/en' must not store the same text twice."""
    calls = []
    page = _FakeResp(200, {"Content-Type": "text/html"}, b"<p>Acme partners page</p>")
    _patch_requests(monkeypatch, {
        "https://acme.com": _FakeResp(301, {"Location": "/en"}),
        "https://acme.com/en": page,
    }, calls)
    out = web.fetch_site_text("acme.com", paths=("", "/en"))
    assert list(out.values()) == ["Acme partners page"]
    assert len(out) == 1


# ------------------------------------------------------------------ search-wave observability

def test_ddg_many_reports_empty_and_timed_out(monkeypatch):
    """stats must separate 'came back with nothing' from 'never came back'.

    Downstream these look identical (both yield []), which is why a throttled run used to be
    indistinguishable from a company the web genuinely knows nothing about.
    """
    monkeypatch.setattr(web, "ddg_search",
                        lambda q, n=4: [{"title": "hit"}] if "good" in q else [])
    stats = {}
    out = web._ddg_many({"a": "good one", "b": "bad one"}, stats=stats)
    assert out["a"] and out["b"] == []
    assert stats == {"requested": 2, "returned": 2, "empty": 1, "timed_out": 0}


def test_ddg_many_stats_on_empty_input():
    stats = {}
    assert web._ddg_many({}, stats=stats) == {}
    assert stats["requested"] == 0 and stats["timed_out"] == 0
