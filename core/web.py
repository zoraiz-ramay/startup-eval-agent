"""Free web enrichment via DuckDuckGo (no paid data APIs)."""
from __future__ import annotations


def ddg_search(query: str, max_results: int = 5,
               attempts: int = 3, base_delay: float = 0.6) -> list[dict]:
    """Single DuckDuckGo text search with light retry + exponential backoff.

    DuckDuckGo rate-limits bursts of free queries and then recovers within a second or
    two, so an empty or failed result is retried a few times (backoff + jitter) before
    giving up. This turns transient throttling — which otherwise surfaces as a false
    'No match ... on the web' for a real but small company — into a brief extra wait.
    Returns [] only if every attempt fails, so callers still degrade gracefully."""
    import time
    import random
    try:
        from ddgs import DDGS
    except Exception:
        try:
            from duckduckgo_search import DDGS  # older package name
        except Exception:
            return []
    hits: list[dict] = []
    for i in range(max(1, attempts)):
        try:
            with DDGS() as ddgs:
                hits = list(ddgs.text(query, max_results=max_results))
            if hits:
                return hits
        except Exception:
            hits = []
        if i < attempts - 1:                     # backoff before the next try
            time.sleep(base_delay * (2 ** i) + random.uniform(0, 0.3))
    return hits


def _ddg_many(queries: dict, max_results: int = 4, max_workers: int = 6,
              overall_timeout: float = 25.0) -> dict:
    """Run several DuckDuckGo searches concurrently and return {key: hits}.

    Web search is network-bound, so issuing the independent enrichment queries in parallel
    (instead of one after another) sharply reduces total wait time. A hard ``overall_timeout``
    bounds the whole wave: if DuckDuckGo is throttling (it rate-limits free use and the client
    retries with backoff), any searches that haven't returned by the deadline are abandoned and
    their key maps to an empty list, so an evaluation degrades to partial/offline results in a
    few seconds instead of hanging for minutes.

    Uses daemon threads (capped by a semaphore) so abandoned in-flight searches can never block
    process shutdown or pile up across evaluations.
    """
    import threading
    out: dict = {k: [] for k in (queries or {})}
    items = [(k, q) for k, q in (queries or {}).items() if str(q).strip()]
    if not items:
        return out
    sem = threading.Semaphore(max(1, min(max_workers, len(items))))
    lock = threading.Lock()
    remaining = {"n": len(items)}
    done = threading.Event()

    def worker(key: str, query: str):
        with sem:
            try:
                hits = ddg_search(query, max_results)
            except Exception:
                hits = []
        with lock:
            out[key] = hits
            remaining["n"] -= 1
            if remaining["n"] == 0:
                done.set()

    for k, q in items:
        threading.Thread(target=worker, args=(k, q), daemon=True).start()
    done.wait(timeout=overall_timeout)   # returns early once all finish, else at the deadline
    return out


# --------------------------------------------------------------------------- direct site fetch
# DuckDuckGo indexes pages slowly and skips a lot of a company's own site, so ecosystem /
# partnership / customer facts that live only on the startup's website (e.g. an /partners or
# /ecosystem page) are invisible to search. A direct, SSRF-guarded HTTP fetch of the company's
# OWN domain closes that recall gap without any paid data API.

_UA = ("Mozilla/5.0 (compatible; StartupEvalBot/1.0; +https://siemens.com) "
       "AppleWebKit/537.36")
_MAX_BYTES = 800_000            # cap the download so a huge page can't exhaust memory
_FETCH_PATHS = ("", "/about", "/about-us", "/company", "/partners", "/ecosystem",
                "/customers", "/team")
_TAG_RE = None                 # compiled lazily in _strip_html


def _is_public_host(host: str) -> bool:
    """SSRF guard: resolve the host and reject loopback/private/link-local/reserved IPs.

    Only public, internet-routable addresses are allowed, so a crafted company domain
    (or a redirect) can never make the server fetch an internal metadata endpoint,
    localhost, or a RFC1918 address."""
    import socket
    import ipaddress
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return False
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr.split("%")[0])
        except ValueError:
            return False
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                or ip.is_multicast or ip.is_unspecified):
            return False
    return True


def _strip_html(html: str) -> str:
    """Cheap HTML -> visible text: drop script/style blocks and tags, unescape entities."""
    import re
    import html as _htmlmod
    global _TAG_RE
    if _TAG_RE is None:
        _TAG_RE = re.compile(r"<[^>]+>")
    text = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    text = _TAG_RE.sub(" ", text)
    text = _htmlmod.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_url(url: str, timeout: float = 8.0, max_bytes: int = _MAX_BYTES) -> str:
    """Fetch a single URL and return its visible text, or '' on any failure.

    Hardened against SSRF: only http/https, the resolved host must be public
    (``_is_public_host``), redirects are disabled (a 3xx returns '' rather than being
    followed to a possibly-internal target), the download is size-capped, and any error
    degrades to '' so a bad site never breaks enrichment."""
    from urllib.parse import urlparse
    try:
        import requests
    except Exception:
        return ""
    if not url:
        return ""
    parsed = urlparse(url if "//" in url else "https://" + url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return ""
    if not _is_public_host(parsed.hostname):
        return ""
    try:
        resp = requests.get(
            parsed.geturl(), timeout=timeout, allow_redirects=False, stream=True,
            headers={"User-Agent": _UA, "Accept": "text/html,application/xhtml+xml"},
        )
    except Exception:
        return ""
    try:
        ctype = resp.headers.get("Content-Type", "")
        if resp.status_code != 200 or ("html" not in ctype and "text" not in ctype):
            return ""
        chunks, total = [], 0
        for chunk in resp.iter_content(chunk_size=16_384, decode_unicode=False):
            if not chunk:
                continue
            chunks.append(chunk)
            total += len(chunk)
            if total >= max_bytes:
                break
        raw = b"".join(chunks)
    except Exception:
        return ""
    finally:
        resp.close()
    try:
        html = raw.decode(resp.encoding or "utf-8", errors="ignore")
    except Exception:
        html = raw.decode("utf-8", errors="ignore")
    return _strip_html(html)


def fetch_site_text(domain: str, paths: tuple = _FETCH_PATHS,
                    per_timeout: float = 6.0, max_chars: int = 12_000) -> dict:
    """Fetch a handful of a company's own pages (home + about/partners/ecosystem/...) and
    return {path: text}. Best-effort: unreachable paths are simply omitted. This surfaces
    ecosystem/partnership/customer facts that live only on the site and never got indexed
    by DuckDuckGo (the phena.tech 'part of X ecosystem' case)."""
    domain = str(domain or "").strip()
    if not domain:
        return {}
    # Normalise to a bare host, then rebuild canonical https URLs per path.
    from urllib.parse import urlparse
    host = urlparse(domain if "//" in domain else "https://" + domain).hostname or ""
    if not host or not _is_public_host(host):
        return {}
    out: dict = {}
    for path in paths:
        text = fetch_url(f"https://{host}{path}", timeout=per_timeout)
        if text:
            out[path or "/"] = text[:max_chars]
    return out
