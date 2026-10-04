"""api/flight.py: one concurrency cap for every entry point, one run per company at a time.

Each test runs against both backends — in-process (SESSION_BACKEND=memory) and Redis, through
fakeredis with Lua so the production scripts themselves execute — because the two are separate
implementations of the same promise and only one of them runs in production.
"""
import os
import sys
import threading
import time

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api import flight  # noqa: E402


@pytest.fixture(params=["memory", "redis"])
def backend(request, monkeypatch):
    monkeypatch.setattr(flight, "_local", flight._LocalQueue())
    monkeypatch.setattr(flight, "_local_flights", {})
    monkeypatch.setattr(flight, "_POLL", 0.02)
    if request.param == "redis":
        fakeredis = pytest.importorskip("fakeredis")
        client = fakeredis.FakeRedis(decode_responses=True)
        monkeypatch.setattr(flight, "_redis", lambda: client)
    else:
        monkeypatch.setattr(flight, "_redis", lambda: None)
    return request.param


def test_no_more_than_the_limit_run_at_once_and_everyone_finishes(backend):
    running, peak, done = [0], [0], []
    lock = threading.Lock()

    def work(i):
        with flight.slot(limit=2):
            with lock:
                running[0] += 1
                peak[0] = max(peak[0], running[0])
            time.sleep(0.1)
            with lock:
                running[0] -= 1
        done.append(i)

    threads = [threading.Thread(target=work, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert peak[0] == 2
    assert sorted(done) == list(range(6))


def test_a_waiter_is_told_its_place_in_line_and_then_that_it_started(backend):
    release = threading.Event()
    admitted = threading.Event()

    def holder():
        with flight.slot(limit=1):
            admitted.set()
            release.wait(5)

    t = threading.Thread(target=holder)
    t.start()
    admitted.wait(5)
    seen = []
    waiter = threading.Thread(target=lambda: flight.slot(seen.append, limit=1).__enter__().__exit__())
    waiter.start()
    deadline = time.time() + 5
    while not seen and time.time() < deadline:
        time.sleep(0.01)
    release.set()
    t.join(5)
    waiter.join(5)
    assert seen == [1, 0]          # first in line, then admitted


def test_one_company_is_evaluated_once_however_many_ask(backend):
    calls, results, partials = [], [], []
    started = threading.Event()

    def run(emit):
        calls.append(1)
        emit("identity", {"company": "Acme"})
        started.set()
        time.sleep(0.2)
        emit("profile", {"profile": {"hq": "Munich"}})
        return {"company": "Acme", "run_id": 7}

    def ask(store_partials):
        results.append(flight.single_flight("flight:acme", run,
                                            (lambda s, d: partials.append(s)) if store_partials else None))

    leader = threading.Thread(target=ask, args=(False,))
    leader.start()
    started.wait(5)
    follower = threading.Thread(target=ask, args=(True,))
    follower.start()
    leader.join(5)
    follower.join(5)
    assert len(calls) == 1
    assert results == [{"company": "Acme", "run_id": 7}] * 2
    # The follower attached mid-run and still saw every partial, in order.
    assert partials == ["identity", "profile"]


def test_a_failed_run_fails_its_followers_with_the_same_error(backend):
    started = threading.Event()
    errors = []

    def run(emit):
        started.set()
        time.sleep(0.1)
        raise HTTPException(404, "No match for 'Acme'.")

    def ask():
        try:
            flight.single_flight("flight:acme", run)
        except HTTPException as exc:
            errors.append((exc.status_code, exc.detail))

    leader = threading.Thread(target=ask)
    leader.start()
    started.wait(5)
    follower = threading.Thread(target=ask)
    follower.start()
    leader.join(5)
    follower.join(5)
    assert errors == [(404, "No match for 'Acme'.")] * 2


def test_different_companies_do_not_wait_for_each_other(backend):
    order = []

    def run_for(name):
        def run(emit):
            order.append(name)
            return {"company": name}
        return run

    assert flight.single_flight("flight:a", run_for("a")) == {"company": "a"}
    assert flight.single_flight("flight:b", run_for("b")) == {"company": "b"}
    assert order == ["a", "b"]


def test_a_follower_takes_over_when_the_leader_died(backend, monkeypatch):
    # A record left by a process that crashed mid-run: still "running", heartbeat long stale.
    flight._write("flight:acme", {"owner": "dead", "status": "running", "partials": [],
                                  "beat": time.time() - 3600}, 60)
    calls = []
    result = flight.single_flight("flight:acme", lambda emit: calls.append(1) or {"company": "Acme"})
    assert calls == [1]
    assert result == {"company": "Acme"}


def test_the_api_runs_the_pipeline_once_and_files_the_second_search_as_shared(backend, monkeypatch):
    """The wiring, not just the primitive: two reviewers, one company, one pipeline run."""
    from api import main
    runs, searches = [], []
    started = threading.Event()

    def fake_fresh(name, body, principal, on_partial, user, department, tracxn):
        runs.append(name)
        started.set()
        time.sleep(0.2)
        return {"company": "Acme Robotics", "run_id": 41, "found": True}

    monkeypatch.setattr(main, "_fresh_evaluation", fake_fresh)
    monkeypatch.setattr(main.store, "record_search",
                        lambda principal, query, **kw: searches.append((principal["upn"], kw["served_from"])))
    body = main.EvaluateBody(name="Acme Robotics")
    out = []

    def reviewer(upn):
        out.append(main._run_evaluation("Acme Robotics", body, {"upn": upn}))

    first = threading.Thread(target=reviewer, args=("a@siemens.com",))
    first.start()
    started.wait(5)
    second = threading.Thread(target=reviewer, args=("b@siemens.com",))
    second.start()
    first.join(5)
    second.join(5)
    assert runs == ["Acme Robotics"]
    assert [r["run_id"] for r in out] == [41, 41]
    # The leader's search is recorded by _saved inside the (stubbed) pipeline path; the follower's
    # is recorded here, as shared.
    assert searches == [("b@siemens.com", "shared")]


def test_background_work_never_takes_a_slot_while_a_reviewer_waits(backend):
    """Prewarming the cache must not delay anyone: it starts only when no one is queued."""
    release, held = threading.Event(), threading.Event()

    def reviewer_holding():
        with flight.slot(limit=1):
            held.set()
            release.wait(5)

    t = threading.Thread(target=reviewer_holding)
    t.start()
    held.wait(5)
    waiting = threading.Thread(target=lambda: flight.slot(limit=1).__enter__().__exit__())
    waiting.start()                                       # a second reviewer queues behind the first
    time.sleep(0.1)
    order = []
    bg = threading.Thread(target=lambda: (flight.slot(limit=2, background=True).__enter__().__exit__(),
                                          order.append("background")))
    bg.start()
    time.sleep(0.2)
    # One slot of two is free, but a reviewer is waiting: background work stays out.
    assert order == []
    release.set()
    t.join(5); waiting.join(5); bg.join(5)
    assert order == ["background"]


def test_background_work_runs_at_its_own_lower_cap_when_idle(backend):
    with flight.slot(limit=2, background=True):
        with flight.slot(limit=2, background=True):
            # A third would exceed the cap of 2; it is refused rather than queued.
            assert flight.slot(limit=2, background=True)._try() == 1


def test_a_request_after_a_run_finished_starts_a_new_run(backend):
    """A refresh pressed after another one finished got that finished run back, because the
    finished record stayed on the flight key for its followers. It must start a run of its own."""
    calls = []
    run = lambda emit: calls.append(1) or {"run_id": len(calls)}
    assert flight.single_flight("flight:acme", run) == {"run_id": 1}
    assert flight.single_flight("flight:acme", run) == {"run_id": 2}
    assert len(calls) == 2
