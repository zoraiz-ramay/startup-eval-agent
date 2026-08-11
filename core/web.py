"""Free web enrichment via DuckDuckGo (no paid data APIs)."""
from __future__ import annotations

import contextvars
import functools
import hashlib

# ------------------------------------------------------------------------------- result cache
# Searches and site fetches are the slow, NON-REPRODUCIBLE part of an evaluation: DuckDuckGo
# returns a different mix of results run to run, so two evaluations of the same startup used to
# disagree. Caching both makes a re-run fast and byte-reproducible.
#
# The backend is injected rather than imported: nothing in core/ depends on api/, and keeping it
# that way lets the engine run uncached from tests, scripts and Streamlit. api/main.py installs
# the SQLite-backed store at startup via install_cache().
_cache_get = None
_cache_put = None

# Set False for a run that must hit the network — "Re-evaluate" has to re-search, otherwise it
# would just replay week-old results. A ContextVar rather than a parameter so the flag follows
# the request through _ddg_many's worker threads without touching every signature in between.
_cache_enabled: contextvars.ContextVar = contextvars.ContextVar("web_cache_enabled", default=True)


def install_cache(getter, putter) -> None:
    """Wire up the cache backend: ``getter(kind, key)`` and ``putter(kind, key, payload)``."""
    global _cache_get, _cache_put
    _cache_get, _cache_put = getter, putter


def set_cache_enabled(enabled: bool):
    """Enable/disable cache reads for the current context; returns the ContextVar token."""
    return _cache_enabled.set(bool(enabled))


def reset_cache_enabled(token) -> None:
    _cache_enabled.reset(token)


def _cache_key(*parts) -> str:
    return hashlib.sha256("\x00".join(str(p) for p in parts).encode("utf-8")).hexdigest()


def _cached(kind: str, key: str):
    if _cache_get is None or not _cache_enabled.get():
        return None
    try:
        return _cache_get(kind, key)
    except Exception:
        return None


def _store(kind: str, key: str, payload) -> None:
    # Written even when reads are disabled, so a forced refresh repopulates the cache.
    if _cache_put is None:
        return
    try:
        _cache_put(kind, key, payload)
    except Exception:
        pass


def ddg_search(query: str, max_results: int = 5,
               attempts: int = 3, base_delay: float = 0.6) -> list[dict]:
    """Single DuckDuckGo text search with light retry + exponential backoff.

    DuckDuckGo rate-limits bursts of free queries and then recovers within a second or
    two, so an empty or failed result is retried a few times (backoff + jitter) before
    giving up. This turns transient throttling — which otherwise surfaces as a false
    'No match ... on the web' for a real but small company — into a brief extra wait.
    Returns [] only if every attempt fails, so callers still degrade gracefully.

    Results are cached (see install_cache): re-running the same query inside the TTL replays
    the same hits, which is what makes a re-evaluation fast AND reproducible."""
    import time
    import random
    key = _cache_key("ddg", query, max_results)
    hit = _cached("ddg", key)
    if hit is not None:
        return hit
    try:
        from ddgs import DDGS
    except Exception:
        try:
            from duckduckgo_search import DDGS  # older package name
        except Exception:
            return []
    hits: list[dict] = []
    failed = False
    for i in range(max(1, attempts)):
        try:
            with DDGS() as ddgs:
                hits = list(ddgs.text(query, max_results=max_results))
            failed = False
            if hits:
                _store("ddg", key, hits)
                return hits
        except Exception:
            hits, failed = [], True
        if i < attempts - 1:                     # backoff before the next try
            time.sleep(base_delay * (2 ** i) + random.uniform(0, 0.3))
    # A genuinely empty result is worth caching; a run that only ever threw is not — caching
    # that would pin a transient throttle in place for the whole TTL.
    if not failed:
        _store("ddg", key, hits)
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
        # A new thread starts with an EMPTY context, so the cache-bypass ContextVar would fall
        # back to its default and a forced refresh would quietly read from the cache anyway.
        # Each worker therefore runs inside its own copy of the caller's context (a Context can
        # only be entered once, so the copy has to be per-thread).
        threading.Thread(target=contextvars.copy_context().run,
                         args=(worker, k, q), daemon=True).start()
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
_ATTR_RE = None                # ditto — alt/title text rescued before tags are dropped


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
    """Cheap HTML -> visible text: drop script/style blocks and tags, unescape entities.

    ``alt`` / ``title`` attribute text is lifted into the output BEFORE tags are removed.
    Stripping tags wholesale silently discards it, and on logo-wall sections that attribute
    is the ONLY textual carrier of the fact: phena.tech publishes its NVIDIA Inception and
    Microsoft for Startups memberships purely as <img alt="..."> badges, so the page yielded
    text with zero program names and the ecosystem section came back empty. Order matters —
    the script/style blocks are removed first so an alt= inside inline JS is never harvested.
    """
    import re
    import html as _htmlmod
    global _TAG_RE, _ATTR_RE
    if _TAG_RE is None:
        _TAG_RE = re.compile(r"<[^>]+>")
    if _ATTR_RE is None:
        _ATTR_RE = re.compile(
            r"""(?is)<[^>]*?\b(?:alt|title)\s*=\s*(?:"([^"]*)"|'([^']*)')[^>]*>""")
    text = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    text = _ATTR_RE.sub(lambda m: f" {m.group(1) or m.group(2) or ''} ", text)
    text = _TAG_RE.sub(" ", text)
    text = _htmlmod.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _fetch_with_url(url: str, timeout: float = 8.0,
                    max_bytes: int = _MAX_BYTES) -> tuple[str, str]:
    """Fetch a URL and return ``(visible_text, resolved_url)``; ``('', '')`` on any failure.

    Same contract as :func:`fetch_url` (which wraps this), but it also hands back the URL the
    request actually landed on after redirects. ``fetch_site_text`` needs that to notice a
    site whose root redirects into a locale prefix (phena.tech -> /en) and follow the rest of
    its paths there instead of requesting bare paths the SPA answers with its homepage.

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
        return "", ""
    if not url:
        return "", ""
    parsed = urlparse(url if "//" in url else "https://" + url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return "", ""
    if not _is_public_host(parsed.hostname):
        return "", ""

    current = parsed.geturl()
    origin_host = parsed.hostname
    for _ in range(_MAX_REDIRECTS + 1):
        try:
            resp = requests.get(
                current, timeout=timeout, allow_redirects=False, stream=True,
                headers={"User-Agent": _UA, "Accept": "text/html,application/xhtml+xml"},
            )
        except Exception:
            return "", ""
        try:
            if resp.status_code in (301, 302, 303, 307, 308):
                target = urljoin(current, resp.headers.get("Location", "") or "")
                t = urlparse(target)
                if (t.scheme not in ("http", "https") or not t.hostname
                        or not _same_site(origin_host, t.hostname)
                        or not _is_public_host(t.hostname)):
                    return "", ""
                current = t.geturl()
                continue                      # next hop (bounded by the loop)
            ctype = resp.headers.get("Content-Type", "")
            if resp.status_code != 200 or ("html" not in ctype and "text" not in ctype):
                return "", ""
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
            return "", ""
        finally:
            resp.close()
        try:
            html = raw.decode(resp.encoding or "utf-8", errors="ignore")
        except Exception:
            html = raw.decode("utf-8", errors="ignore")
        return _strip_html(html), current
    return "", ""                              # redirect budget exhausted


def _fetch_cached(url: str, timeout: float = 8.0,
                  max_bytes: int = _MAX_BYTES) -> tuple[str, str]:
    """:func:`_fetch_with_url` with the result cache in front of it.

    Caches the resolved URL alongside the text, because fetch_site_text derives the site's
    locale prefix from it — replaying only the text would lose the prefix and send the cached
    run down a different set of paths than the live one."""
    key = _cache_key("site", url, max_bytes)
    hit = _cached("site", key)
    if isinstance(hit, list) and len(hit) == 2:
        return hit[0], hit[1]
    text, resolved = _fetch_with_url(url, timeout=timeout, max_bytes=max_bytes)
    # Only successful fetches are cached: a timeout or a transient 5xx must not pin an empty
    # page in place for the whole TTL.
    if text:
        _store("site", key, [text, resolved])
    return text, resolved


def fetch_url(url: str, timeout: float = 8.0, max_bytes: int = _MAX_BYTES) -> str:
    """Fetch a single URL and return its visible text, or '' on any failure.

    Thin text-only wrapper over :func:`_fetch_with_url` — see that function for the SSRF and
    redirect guarantees."""
    return _fetch_with_url(url, timeout=timeout, max_bytes=max_bytes)[0]


def fetch_site_text(domain: str, paths: tuple = _FETCH_PATHS,
                    per_timeout: float = 6.0, max_chars: int = 12_000) -> dict:
    """Fetch a handful of a company's own pages (home + about/partners/ecosystem/...) and
    return {path: text}. Best-effort: unreachable paths are simply omitted. This surfaces
    ecosystem/partnership/customer facts that live only on the site and never got indexed
    by DuckDuckGo (the phena.tech 'part of X ecosystem' case).

    The root is fetched first so its RESOLVED url can reveal a locale prefix ('/en'), which is
    then applied to the remaining paths. Without this, a localised SPA answers every bare path
    ('/about', '/team') with its homepage: the fingerprint dedup below drops them all as
    duplicates and the genuinely distinct '/en/about' is never requested. Detecting the prefix
    keeps the request count flat instead of trying both spellings of every path."""
    domain = str(domain or "").strip()
    if not domain:
        return {}
    # Normalise to a bare host, then rebuild canonical https URLs per path.
    from urllib.parse import urlparse
    import re
    host = urlparse(domain if "//" in domain else "https://" + domain).hostname or ""
    if not host or not _is_public_host(host):
        return {}
    import concurrent.futures

    # Root first and alone: it is both a wanted page and the probe that reveals the locale
    # prefix the remaining paths need.
    rest = [p for p in paths if p != ""]
    root_text, resolved = _fetch_cached(f"https://{host}", timeout=per_timeout)
    prefix = ""
    if resolved:
        # e.g. https://www.phena.tech/en -> '/en'; ignore anything that is not a locale.
        landed = "/" + urlparse(resolved).path.strip("/").split("/")[0]
        if re.fullmatch(r"/[a-z]{2}(-[A-Za-z]{2})?", landed):
            prefix = landed

    # The rest are independent GETs. Sequentially they cost up to per_timeout each — ~7s of a
    # run for a site where most paths 404 — so they are fetched concurrently and reassembled
    # in the ORIGINAL path order below. Completion order must not decide the result: it would
    # vary run to run and change which duplicate survives the fingerprint check.
    texts: dict = {"": root_text}
    if rest:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(rest))) as ex:
            # copy_context per submission: pool threads do not inherit the caller's context,
            # which the cache-bypass flag lives in.
            futures = {
                p: ex.submit(contextvars.copy_context().run,
                             functools.partial(
                                 _fetch_cached,
                                 f"https://{host}{p if p.startswith(prefix) else prefix + p}",
                                 timeout=per_timeout))
                for p in rest
            }
            for p, fut in futures.items():
                try:
                    texts[p] = fut.result()[0]
                except Exception:
                    texts[p] = ""

    out: dict = {}
    seen: set = set()
    for path in paths:
        text = texts.get(path, "")
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
