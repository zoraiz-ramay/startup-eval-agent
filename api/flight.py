"""How many evaluations run at once, and how many times one company is evaluated at once.

Every fresh evaluation goes through `api.main._run_evaluation`, from all three entry points
(/api/evaluate, /api/evaluate/stream and the job queue), so this is the one place both limits live:

- `slot()` caps concurrent pipeline runs across BOTH gunicorn workers. The jobs pool used to be 2
  threads per worker while the stream route was unbounded, so one path queued reviewers and the
  other let any number of runs hit the model quota at once. A waiter learns how many runs are
  ahead of it, which is what the page shows instead of an unexplained skeleton.
- `single_flight()` runs one evaluation per company at a time. A second reviewer asking for a
  company already being evaluated attaches to that run — its partials, then its result — instead
  of paying for the same ~26 model calls again.

Redis when the session store is Redis (production: shared by both workers in the container);
in-process otherwise (SESSION_BACKEND=memory, tests). Nothing here is evaluation-specific.
"""
from __future__ import annotations

import json
import logging
import os
import secrets
import threading
import time

from fastapi import HTTPException

from api.auth import sessions

log = logging.getLogger(__name__)

EVAL_CONCURRENCY = max(1, int(os.getenv("EVAL_CONCURRENCY", "6")))
# A waiter gives up rather than holding a request open indefinitely behind a stuck queue.
EVAL_QUEUE_WAIT = float(os.getenv("EVAL_QUEUE_WAIT", "900"))
# A held slot or a running flight is refreshed every HEARTBEAT seconds; one that stops being
# refreshed (its process died) is reclaimed after LEASE seconds rather than leaking forever.
HEARTBEAT = 10.0
LEASE = 45.0
_POLL = 0.5

_HOLDERS, _WAITERS, _SEEN = "evalq:holders", "evalq:waiters", "evalq:seen"

# Atomic admit-or-report: -1 when admitted, else the 1-based place in line. FIFO by arrival; a waiter whose heartbeat stopped is dropped, so a
# closed tab cannot hold its place in line.
_ACQUIRE = """
local holders, waiters, seen = KEYS[1], KEYS[2], KEYS[3]
local token, now = ARGV[1], tonumber(ARGV[2])
local limit, lease = tonumber(ARGV[3]), tonumber(ARGV[4])
redis.call('ZREMRANGEBYSCORE', holders, '-inf', now - lease)
for _, m in ipairs(redis.call('ZRANGEBYSCORE', seen, '-inf', now - lease)) do
  redis.call('ZREM', waiters, m); redis.call('ZREM', seen, m)
end
redis.call('ZADD', seen, now, token)
if not redis.call('ZSCORE', waiters, token) then redis.call('ZADD', waiters, now, token) end
local rank = redis.call('ZRANK', waiters, token)
local free = limit - redis.call('ZCARD', holders)
if rank < free then
  redis.call('ZREM', waiters, token); redis.call('ZREM', seen, token)
  redis.call('ZADD', holders, now, token)
  return -1
end
return rank - math.max(free, 0) + 1
"""


def _redis():
    return getattr(sessions(), "_client", None)


class _LocalQueue:
    """The same FIFO semantics in-process, for the memory session backend."""

    def __init__(self):
        self.cond = threading.Condition()
        self.holders: set[str] = set()
        self.waiters: list[str] = []

    def try_acquire(self, token: str, limit: int) -> int:
        with self.cond:
            if token not in self.waiters:
                self.waiters.append(token)
            rank = self.waiters.index(token)
            free = limit - len(self.holders)
            if rank < free:
                self.waiters.remove(token)
                self.holders.add(token)
                return -1
            return rank - max(free, 0) + 1

    def leave(self, token: str) -> None:
        with self.cond:
            self.holders.discard(token)
            if token in self.waiters:
                self.waiters.remove(token)


_local = _LocalQueue()


class slot:
    """`with slot(on_wait): run()` — admitted in arrival order, at most EVAL_CONCURRENCY at once.

    ``on_wait(position)`` is called whenever the caller's place in line changes (1 = next to
    start), and with 0 once admitted, so a caller that showed a position can clear it.
    """

    def __init__(self, on_wait=None, limit: int | None = None):
        self.on_wait = on_wait
        self.limit = limit or EVAL_CONCURRENCY
        self.token = secrets.token_hex(8)
        self._stop = threading.Event()

    def _try(self) -> int:
        client = _redis()
        if client is None:
            return _local.try_acquire(self.token, self.limit)
        return int(client.eval(_ACQUIRE, 3, _HOLDERS, _WAITERS, _SEEN,
                               self.token, time.time(), self.limit, LEASE))

    def _tell(self, position: int) -> None:
        if self.on_wait:
            try:
                self.on_wait(position)
            except Exception:
                pass

    def __enter__(self):
        deadline = time.time() + EVAL_QUEUE_WAIT
        last = None
        while True:
            position = self._try()
            if position < 0:
                break
            if position != last:
                self._tell(position)
                last = position
            if time.time() > deadline:
                self._leave()
                raise HTTPException(503, "Evaluations are queued longer than usual. Please try again shortly.")
            time.sleep(_POLL)
        if last:
            self._tell(0)
        client = _redis()
        if client is not None:
            # Keep the lease fresh while the run holds it; a crashed process stops refreshing and
            # its slot is reclaimed by the next _ACQUIRE after LEASE seconds.
            def beat():
                while not self._stop.wait(HEARTBEAT):
                    try:
                        client.zadd(_HOLDERS, {self.token: time.time()}, xx=True)
                    except Exception:
                        pass
            threading.Thread(target=beat, daemon=True).start()
        return self

    def _leave(self) -> None:
        client = _redis()
        if client is None:
            _local.leave(self.token)
            return
        try:
            client.zrem(_HOLDERS, self.token)
            client.zrem(_WAITERS, self.token)
            client.zrem(_SEEN, self.token)
        except Exception:
            log.warning("[flight] could not release slot %s; its lease will expire", self.token)

    def __exit__(self, *exc):
        self._stop.set()
        self._leave()
        return False


# ------------------------------------------------------------------------------- single flight

_FLIGHT_TTL = 1800
_DONE_TTL = 120            # long enough for an attached follower to read the result
_local_flights: dict[str, dict] = {}
_local_flights_lock = threading.Lock()


def flight_key(*parts) -> str:
    return "flight:" + ":".join(str(p).strip().casefold() for p in parts)


def _claim(key: str, record: dict) -> bool:
    client = _redis()
    if client is None:
        with _local_flights_lock:
            cur = _local_flights.get(key)
            if cur and cur.get("expires", 0) > time.time():
                return False
            _local_flights[key] = {**record, "expires": time.time() + _FLIGHT_TTL}
            return True
    return bool(client.set(key, json.dumps(record, default=str), nx=True, ex=_FLIGHT_TTL))


def _read(key: str) -> dict | None:
    client = _redis()
    if client is None:
        with _local_flights_lock:
            cur = _local_flights.get(key)
            return json.loads(json.dumps(cur, default=str)) if cur and cur.get("expires", 0) > time.time() else None
    raw = client.get(key)
    return json.loads(raw) if raw else None


def _write(key: str, record: dict, ttl: int) -> None:
    client = _redis()
    if client is None:
        with _local_flights_lock:
            _local_flights[key] = {**record, "expires": time.time() + ttl}
        return
    client.set(key, json.dumps(record, default=str), ex=ttl)


def single_flight(key: str, run, on_partial=None):
    """Run ``run(emit)`` once for ``key``; concurrent callers with the same key share it.

    The leader's ``emit(section, data)`` reaches its own ``on_partial`` directly and is recorded
    for followers, which replay every partial in order and then return the leader's result — or
    raise the leader's HTTPException. A follower whose leader stops heartbeating (its process
    died) takes over and runs the evaluation itself.
    """
    token = secrets.token_hex(8)
    while True:
        record = {"owner": token, "status": "running", "partials": [], "beat": time.time()}
        if _claim(key, record):
            return _lead(key, record, run, on_partial)
        outcome = _follow(key, on_partial)
        if outcome is not None:
            return outcome
        # The leader vanished without finishing: loop and try to claim the flight ourselves.


def _lead(key, record, run, on_partial):
    lock = threading.Lock()
    stop = threading.Event()

    def save(ttl=_FLIGHT_TTL):
        with lock:
            record["beat"] = time.time()
            _write(key, record, ttl)

    def emit(section, data):
        if on_partial:
            try:
                on_partial(section, data)
            except Exception:
                pass
        with lock:
            record["partials"].append([section, data])
        save()

    def beat():
        while not stop.wait(HEARTBEAT):
            save()
    threading.Thread(target=beat, daemon=True).start()
    try:
        result = run(emit)
    except HTTPException as exc:
        stop.set()
        record.update(status="error", status_code=exc.status_code, detail=exc.detail)
        save(_DONE_TTL)
        raise
    except Exception:
        stop.set()
        record.update(status="error", status_code=500, detail="Research failed. Please retry this startup.")
        save(_DONE_TTL)
        raise
    stop.set()
    record.update(status="done", result=result)
    save(_DONE_TTL)
    return result


# Delete only the dead leader's record: between reading it and deleting it, another follower may
# already have claimed the flight, and deleting THAT would start a third run.
_DROP_IF_OWNER = """
local raw = redis.call('GET', KEYS[1])
if raw and cjson.decode(raw)['owner'] == ARGV[1] then return redis.call('DEL', KEYS[1]) end
return 0
"""


def _drop_if_owner(key: str, owner) -> None:
    client = _redis()
    if client is None:
        with _local_flights_lock:
            if (_local_flights.get(key) or {}).get("owner") == owner:
                _local_flights.pop(key, None)
        return
    client.eval(_DROP_IF_OWNER, 1, key, owner or "")


def _follow(key, on_partial):
    seen = 0
    while True:
        record = _read(key)
        if record is None:
            return None
        partials = record.get("partials") or []
        for section, data in partials[seen:]:
            if on_partial:
                try:
                    on_partial(section, data)
                except Exception:
                    pass
        seen = len(partials)
        if record.get("status") == "done":
            return record.get("result")
        if record.get("status") == "error":
            raise HTTPException(record.get("status_code") or 500, record.get("detail") or "Research failed.")
        if time.time() - float(record.get("beat") or 0) > LEASE:
            _drop_if_owner(key, record.get("owner"))
            return None
        time.sleep(_POLL)
