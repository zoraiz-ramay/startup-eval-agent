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
