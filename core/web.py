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


def _ddg_many(queries: dict, max_results: int = 4, max_workers: int = 10,
              overall_timeout: float = 40.0, stats: dict | None = None) -> dict:
    """Run several DuckDuckGo searches concurrently and return {key: hits}.

    Web search is network-bound, so issuing the independent enrichment queries in parallel
    (instead of one after another) sharply reduces total wait time. A hard ``overall_timeout``
    bounds the whole wave: if DuckDuckGo is throttling (it rate-limits free use and the client
    retries with backoff), any searches that haven't returned by the deadline are abandoned and
    their key maps to an empty list, so an evaluation degrades to partial/offline results in a
    few seconds instead of hanging for minutes.

    The budget must scale with the wave: abandoning a query is indistinguishable downstream
    from "the web knows nothing about this company", so too tight a deadline silently turns
    throttling into missing profile fields (parent group, programs, funding) that reappear on
    the next run. The defaults leave headroom for the ~12-query enrichment wave plus its
    per-customer verification queries, each of which may internally retry with backoff.

    Pass ``stats`` to receive observability for exactly that failure mode: it is populated with
    ``requested`` / ``returned`` / ``empty`` / ``timed_out``, where ``timed_out`` counts queries
    still in flight at the deadline (silently dropped) as distinct from those that genuinely
    came back with no hits.

    Uses daemon threads (capped by a semaphore) so abandoned in-flight searches can never block
    process shutdown or pile up across evaluations.
    """
    import threading
    out: dict = {k: [] for k in (queries or {})}
    items = [(k, q) for k, q in (queries or {}).items() if str(q).strip()]
    if isinstance(stats, dict):
        stats.update({"requested": len(items), "returned": 0, "empty": 0, "timed_out": len(items)})
    if not items:
        return out
    sem = threading.Semaphore(max(1, min(max_workers, len(items))))
    lock = threading.Lock()
    remaining = {"n": len(items)}
    finished: set = set()
    done = threading.Event()

    def worker(key: str, query: str):
        with sem:
            try:
                hits = ddg_search(query, max_results)
            except Exception:
                hits = []
        with lock:
            out[key] = hits
            finished.add(key)
            remaining["n"] -= 1
            if remaining["n"] == 0:
                done.set()

    for k, q in items:
        threading.Thread(target=worker, args=(k, q), daemon=True).start()
    done.wait(timeout=overall_timeout)   # returns early once all finish, else at the deadline
    if isinstance(stats, dict):
        # Snapshot under the lock: workers may still be running past the deadline.
        with lock:
            settled = set(finished)
        stats["returned"] = len(settled)
        stats["timed_out"] = len(items) - len(settled)
        stats["empty"] = sum(1 for k in settled if not out.get(k))
    return out


# --------------------------------------------------------------------------- direct site fetch
# DuckDuckGo indexes pages slowly and skips a lot of a company's own site, so ecosystem /
# partnership / customer facts that live only on the startup's website (e.g. an /partners or
# /ecosystem page) are invisible to search. A direct, SSRF-guarded HTTP fetch of the company's
# OWN domain closes that recall gap without any paid data API.

_UA = ("Mozilla/5.0 (compatible; StartupEvalBot/1.0; +https://siemens.com) "
       "AppleWebKit/537.36")
_MAX_BYTES = 800_000            # cap the download so a huge page can't exhaust memory
_FETCH_PATHS = ("", "/en", "/about", "/about-us", "/company", "/partners",
                "/partners-and-supporters", "/supporters", "/ecosystem",
                "/customers", "/team")
_MAX_REDIRECTS = 2              # same-host hops allowed per fetch (see _same_site)
_TAG_RE = None                 # compiled lazily in _strip_html


def _registrable(host: str) -> str:
    """Best-effort registrable domain: the last two labels, lowercased.

    Deliberately naive (no public-suffix list, so 'a.co.uk' -> 'co.uk'). It is only ever used
    to decide whether a redirect stays on the SAME site, and the target is independently
    re-checked by ``_is_public_host`` before any request, so the worst case of an over-broad
    match is fetching another public page on a neighbouring domain — never an internal one."""
    parts = [p for p in str(host or "").lower().strip(".").split(".") if p]
    return ".".join(parts[-2:]) if len(parts) >= 2 else ".".join(parts)


def _same_site(a: str, b: str) -> bool:
    """True when two hosts belong to the same site (exact, www-, or shared registrable domain)."""
    a, b = str(a or "").lower(), str(b or "").lower()
    if not a or not b:
        return False
    if a == b:
        return True
    return _registrable(a) == _registrable(b)


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
    (``_is_public_host``), the download is size-capped, and any error degrades to '' so a
    bad site never breaks enrichment.

    Redirects are followed MANUALLY (requests' own following stays disabled) for at most
    ``_MAX_REDIRECTS`` hops, and only when the target stays on the same site (``_same_site``)
    AND independently re-passes the public-host check. Refusing 3xx outright — as this did
    originally — is not a safe default but a silent recall bug: a site whose root redirects
    to a locale prefix (phena.tech -> /en) returns '' for EVERY path, so the ecosystem and
    partner pages this fetcher exists to read are never seen. Re-validating each hop keeps
    the SSRF guarantee: an off-site or internal redirect target is still refused."""
    from urllib.parse import urlparse, urljoin
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

    current = parsed.geturl()
    origin_host = parsed.hostname
    for _ in range(_MAX_REDIRECTS + 1):
        try:
            resp = requests.get(
                current, timeout=timeout, allow_redirects=False, stream=True,
                headers={"User-Agent": _UA, "Accept": "text/html,application/xhtml+xml"},
            )
        except Exception:
            return ""
        try:
            if resp.status_code in (301, 302, 303, 307, 308):
                target = urljoin(current, resp.headers.get("Location", "") or "")
                t = urlparse(target)
                if (t.scheme not in ("http", "https") or not t.hostname
                        or not _same_site(origin_host, t.hostname)
                        or not _is_public_host(t.hostname)):
                    return ""
                current = t.geturl()
                continue                      # next hop (bounded by the loop)
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
    return ""                                  # redirect budget exhausted


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
    seen: set = set()
    for path in paths:
        text = fetch_url(f"https://{host}{path}", timeout=per_timeout)
        if not text:
            continue
        # Now that same-site redirects are followed, distinct paths routinely resolve to the
        # same page ('/' -> '/en', '/about' -> '/about-us'). Keeping both would duplicate the
        # text in the evidence corpus and crowd out other pages under the prompt's char cap.
        fingerprint = hash(text[:2000])
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        out[path or "/"] = text[:max_chars]
    return out
