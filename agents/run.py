"""Auto-mode loop: ship features by running markdown-defined agents.

This is the single runner (there is always a runtime; markdown agents do not
self-execute). For each cycle it:

  1. repo_analysis   (.md, cheap)      -> shared repo snapshot
  2. product_planner (.md, expensive)  -> next feature spec (skips already-shipped)
  3. coding          (.md, expensive)  -> concrete files
  4. deterministic verifiers (real tools): pytest + flake8 + mypy + secret scan
  5. reasoning reviews (.md): applied_se, ui_review, fact_checking
  6. gate -> on approval copy files into the live repo + register the feature

Hard gates (always block): tests, engineering (lint+type), security. These run
real tools, so they cannot be faked. Soft gates (block only on an explicit fail
from the model): ui, credibility. Model flakiness never silently ships bad code
because the hard gates are deterministic.

Usage:
    python agents/run.py --max 3
    python agents/run.py --max 1 --dry-run     # plan+code, do not apply
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.runtime import harness, tools  # noqa: E402

# UI source dirs the ui_improver agent is allowed to see/edit, and where the fetched
# Tracxn reference is cached so every cycle doesn't re-hit the network.
_UI_DIRS = ("pages", "components")
_TRACXN_CACHE = REPO_ROOT / "store" / "tracxn_reference.json"
_TRACXN_CACHE_MAX_AGE_HOURS = 168  # 1 week; Tracxn's own UI patterns change slowly

# how many times the repair agent may retry to satisfy the deterministic gates
MAX_FIX_ATTEMPTS = int(__import__("os").getenv("AGENT_MAX_FIX_ATTEMPTS", "2"))

# candidate ideas the planner may draw from (it must avoid already-shipped ones)
DEFAULT_BACKLOG = [
    "Source quality scoring",
    "Confidence score per report section",
    "Contradiction detection",
    "Irrelevant source filter",
    "Evaluation reproducibility log",
    "Fact-checking test suite",
    "Cost dashboard for developers",
    "Exportable evaluation report",
]


def _log(msg: str) -> None:
    print(f"[run] {msg}", file=sys.stderr, flush=True)


def _repo_context() -> dict:
    top = sorted(p.name + ("/" if p.is_dir() else "")
                 for p in REPO_ROOT.iterdir() if not p.name.startswith("."))
    return {
        "root": REPO_ROOT.name,
        "top_level": top,
        "backend": "FastAPI (api/, core/)",
        "frontend": "React 18 + Vite (ui/)",
        "tests_dir": "tests/",
    }


def _load_core_web():
    """Import ``core.web`` without triggering ``core/__init__`` (avoids pandas etc.).

    Mirrors the loader in ``agents.runtime.harness`` for ``core.config``/``core.llm``.
    """
    import types
    core_dir = REPO_ROOT / "core"
    if "core" not in sys.modules or not hasattr(sys.modules["core"], "__path__"):
        pkg = types.ModuleType("core")
        pkg.__path__ = [str(core_dir)]  # type: ignore[attr-defined]
        sys.modules["core"] = pkg
    full = "core.web"
    if full not in sys.modules:
        spec = importlib.util.spec_from_file_location(full, core_dir / "web.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[full] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return sys.modules[full]


def _tracxn_reference() -> dict:
    """Return the design-standard reference for the UI Improver agent.

    Best-effort, SSRF-guarded live fetch of tracxn.com (cached on disk for a week);
    falls back to a static note pointing at the benchmark dimensions already encoded
    in ``benchmarks/tracxn.py`` so the agent never has to fabricate what Tracxn's UI
    looks like.
    """
    if _TRACXN_CACHE.is_file():
        try:
            cached = json.loads(_TRACXN_CACHE.read_text(encoding="utf-8"))
            fetched_at = datetime.fromisoformat(cached["fetched_at"])
            age_hours = (datetime.now(timezone.utc) - fetched_at).total_seconds() / 3600
            if age_hours < _TRACXN_CACHE_MAX_AGE_HOURS:
                return cached
        except Exception:
            pass
    pages: dict = {}
    try:
        web = _load_core_web()
        pages = web.fetch_site_text("tracxn.com", per_timeout=6.0, max_chars=6000)
    except Exception:
        pages = {}
    if pages:
        data = {
            "source": "https://tracxn.com",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "live_fetch_ok": True,
            "pages": pages,
        }
    else:
        data = {
            "source": "https://tracxn.com",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "live_fetch_ok": False,
            "pages": {},
            "note": (
                "Live fetch unavailable; fall back to the static benchmark dimensions "
                "in benchmarks/tracxn.py (Sector & Market, Founding Year, Location, "
                "Team & Founders, Funding & Investors, Business Model, Product & "
                "Technology, Traction & Customers, Competition). Treat any UI proposal "
                "as generic best-practice, not an observed Tracxn-specific pattern."
            ),
        }
    try:
        _TRACXN_CACHE.parent.mkdir(parents=True, exist_ok=True)
        _TRACXN_CACHE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")
    except Exception:
        pass
    return data


def _ui_source_files() -> dict:
    """Read every .jsx file under ui/src/{pages,components} as {relpath: content}."""
    out: dict = {}
    for sub in _UI_DIRS:
        d = REPO_ROOT / "ui" / "src" / sub
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.jsx")):
            try:
                rel = str(p.relative_to(REPO_ROOT)).replace("\\", "/")
                out[rel] = p.read_text(encoding="utf-8")
            except Exception:
                continue
    return out


def _already_shipped() -> list:
    reg = REPO_ROOT / "store" / "features.json"
    if not reg.is_file():
        return []
    try:
        data = json.loads(reg.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return [f.get("feature_name") for f in data.get("features", []) if f.get("feature_name")]


def _worktree_add(path: Path, branch: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "worktree", "add", "-b", branch, str(path), "HEAD"],
                   cwd=str(REPO_ROOT), check=True, capture_output=True, text=True)


def _worktree_remove(path: Path, branch: str) -> None:
    subprocess.run(["git", "worktree", "remove", "--force", str(path)],
                   cwd=str(REPO_ROOT), check=False, capture_output=True, text=True)
    subprocess.run(["git", "branch", "-D", branch],
                   cwd=str(REPO_ROOT), check=False, capture_output=True, text=True)


def _write_files(worktree: Path, files: list) -> list:
    written = []
    for f in files:
        rel = (f or {}).get("path")
        content = (f or {}).get("content")
        if not rel or content is None:
            continue
        dst = worktree / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(content, encoding="utf-8")
        written.append(rel)
    return written


def _apply_to_repo(worktree: Path, files: list) -> list:
    applied = []
    for rel in files:
        src = worktree / rel
        if not src.is_file():
            continue
        dst = REPO_ROOT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        applied.append(rel)
    return applied


def _register_feature(feature: dict, cycle_id: str, coding: dict,
                      fact: dict, applied: list) -> dict:
    reg_path = REPO_ROOT / "store" / "features.json"
    registry = {"features": []}
    if reg_path.is_file():
        try:
            registry = json.loads(reg_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            registry = {"features": []}
    entry = {
        "feature_name": feature.get("feature_name"),
        "status": "added",
        "cycle_id": cycle_id,
        "added_at": datetime.now(timezone.utc).isoformat(),
        "summary": coding.get("summary", ""),
        "files": applied,
        "tests": coding.get("tests_added", []),
        "benchmark": (fact or {}).get("benchmark", {}),
        "credibility_impact": feature.get("credibility_impact", ""),
    }
    others = [f for f in registry.get("features", [])
              if f.get("feature_name") != entry["feature_name"]]
    registry["features"] = others + [entry]
    reg_path.parent.mkdir(parents=True, exist_ok=True)
    reg_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    return entry


def _est_tokens(*results: dict) -> int:
    chars = sum(len((r or {}).get("raw", "")) for r in results)
    return chars // 4  # rough chars-per-token estimate


def run_cycle(dry_run: bool = False, ui_focus: bool = False,
              code_tier: str = "cheap") -> dict:
    cycle_id = f"cycle-{uuid.uuid4().hex[:8]}"
    branch = f"feature/{cycle_id}"
    worktree = REPO_ROOT / ".claude" / "worktrees" / cycle_id
    _log(f"starting {cycle_id}" + (" [ui-focus]" if ui_focus else ""))

    # 1. repo analysis (cheap)
    repo = harness.run_agent("repo_analysis", _repo_context())
    if not repo["available"]:
        return {"cycle_id": cycle_id, "merge_decision": "blocked",
                "blocking_reasons": ["llm_unavailable"], "error": repo["error"]}
    repo_summary = repo["output"] or {}
    _log(f"repo analysis via {repo['model']}")

    # 2. plan the next feature (expensive) - either the general planner, or the
    # UI-focused planner benchmarked against Tracxn + Siemens iX guidance.
    ui_files = _ui_source_files() if ui_focus else {}
    if ui_focus:
        planned = harness.run_agent("ui_improver", {
            "repo_summary": repo_summary,
            "already_shipped": _already_shipped(),
            "ui_files": ui_files,
            "tracxn_reference": _tracxn_reference(),
        }, max_tokens=3000)
    else:
        planned = harness.run_agent("product_planner", {
            "repo_summary": repo_summary,
            "already_shipped": _already_shipped(),
            "backlog": DEFAULT_BACKLOG,
        })
    feature = planned["output"] or {}
    if not feature.get("feature_name"):
        return {"cycle_id": cycle_id, "merge_decision": "blocked",
                "blocking_reasons": ["planner_no_feature"], "error": planned["error"]}
    _log(f"planned '{feature['feature_name']}' via {planned['model']}"
         + (" [ui]" if ui_focus else ""))

    # 3. implement. Non-UI cycles use the coding agent's own tier (expensive). UI-focused
    # cycles use `code_tier` (default cheap) so the loop can run continuously and cheaply,
    # but this can be set to expensive for higher-quality, more-reliable UI code.
    coding_override = code_tier if ui_focus else None
    coding_context = {"feature": feature, "repo_summary": repo_summary}
    if ui_focus:
        coding_context["ui_files"] = {
            p: ui_files[p] for p in feature.get("target_files", []) if p in ui_files
        }
    coded = harness.run_agent("coding", coding_context, max_tokens=8000,
                              model_override=coding_override)
    coding = coded["output"] or {}
    files = coding.get("files", [])
    if not files:
        return {"cycle_id": cycle_id, "active_feature": feature["feature_name"],
                "merge_decision": "blocked", "blocking_reasons": ["coding_no_files"],
                "error": coded["error"]}
    _log(f"coding produced {len(files)} file(s) via {coded['model']}")

    _worktree_add(worktree, branch)
    try:
        written = _write_files(worktree, files)

        def _verify(current: dict) -> dict:
            lint = [str(worktree / t) for t in current.get("lint_targets", [])
                    if str(t).endswith(".py")]
            abs_all = [str(worktree / (f or {}).get("path", ""))
                       for f in current.get("files", []) if (f or {}).get("path")]
            return {
                "qa": tools.run_pytest(worktree / "tests"),
                "flake": tools.run_flake8(lint, worktree),
                "mypy": tools.run_mypy(lint, worktree),
                "sec": tools.scan_secrets(abs_all),
            }

        # 4. deterministic hard gates, with a self-repair loop
        v = _verify(coding)
        fix_attempts = 0
        while fix_attempts < MAX_FIX_ATTEMPTS and (
                v["qa"]["status"] != "pass"
                or v["flake"]["status"] != "pass"
                or v["mypy"]["status"] != "pass"):
            fix_attempts += 1
            errors = {
                "pytest": v["qa"].get("output", ""),
                "flake8": v["flake"].get("output", ""),
                "mypy": v["mypy"].get("output", ""),
            }
            _log(f"repair attempt {fix_attempts}/{MAX_FIX_ATTEMPTS} "
                 f"(flake8={v['flake']['status']}, mypy={v['mypy']['status']}, "
                 f"tests={v['qa']['status']})")
            fix = harness.run_agent("coding_fix", {
                "files": coding.get("files", []), "errors": errors, "feature": feature,
            }, max_tokens=8000, model_override=coding_override)
            fixed = fix["output"] or {}
            if not fixed.get("files"):
                _log("repair produced no files; stopping repair loop")
                break
            # merge corrected files over the originals (repair may return only a subset)
            by_path = {f.get("path"): f for f in coding.get("files", []) if f.get("path")}
            for f in fixed["files"]:
                if f.get("path"):
                    by_path[f["path"]] = f
            coding["files"] = list(by_path.values())
            coding["lint_targets"] = fixed.get("lint_targets", coding.get("lint_targets", []))
            coding["tests_added"] = fixed.get("tests_added", coding.get("tests_added", []))
            coding["summary"] = fixed.get("summary", coding.get("summary", ""))
            written = _write_files(worktree, coding["files"])
            v = _verify(coding)

        files = coding.get("files", [])
        qa, flake, mypy, sec = v["qa"], v["flake"], v["mypy"], v["sec"]
        engineering_ok = flake["status"] == "pass" and mypy["status"] == "pass"

        # 5. reasoning reviews (soft gates)
        se = harness.run_agent("applied_se", {"files": files, "feature": feature})
        ui = harness.run_agent("ui_review", {"files": files})
        fact = harness.run_agent("fact_checking",
                                 {"feature": feature, "summary": coding.get("summary", ""),
                                  "files": [f.get("path") for f in files]},
                                 model_override=coding_override)
        se_out = se["output"] or {}
        ui_out = ui["output"] or {}
        fact_out = fact["output"] or {}

        cost = tools.check_budget(feature.get("engineering_effort", "small"),
                                  _est_tokens(repo, planned, coded, se, ui, fact))

        # hard gates block; soft gates block only on explicit fail
        hard = {
            "tests": qa["status"] == "pass",
            "engineering": engineering_ok,
            "security": sec["status"] == "pass",
            "cost": cost["budget_status"] == "within_budget",
        }
        soft = {
            "ui": ui_out.get("approved") is not False,
            "credibility": fact_out.get("credibility_status") != "fail",
        }
        blocking = [g for g, ok in {**hard, **soft}.items() if not ok]
        approved = not blocking

        result = {
            "cycle_id": cycle_id,
            "active_feature": feature["feature_name"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "repair_attempts": fix_attempts,
            "models_used": {
                "repo_analysis": repo["model"],
                "product_planner" if not ui_focus else "ui_improver": planned["model"],
                "coding": coded["model"], "applied_se": se["model"],
                "ui_review": ui["model"], "fact_checking": fact["model"],
            },
            "ui_focus": ui_focus,
            "files_changed": [f.get("path") for f in files if f.get("path")],
            "gate_details": {
                "tests": qa["status"], "flake8": flake["status"], "mypy": mypy["status"],
                "security": sec["status"], "cost": cost["budget_status"],
                "ui_approved": ui_out.get("approved"),
                "credibility": fact_out.get("credibility_status"),
            },
            "merge_decision": "approved" if approved else "blocked",
            "blocking_reasons": blocking,
            "summary": coding.get("summary", ""),
        }
        if not qa.get("status") == "pass":
            result["test_output"] = qa.get("output", "")
        if flake["status"] != "pass":
            result["flake8_output"] = flake.get("output", "")
        if mypy["status"] != "pass":
            result["mypy_output"] = mypy.get("output", "")

        if approved and not dry_run:
            apply_paths = [f.get("path") for f in files if f.get("path")]
            applied = _apply_to_repo(worktree, apply_paths)
            entry = _register_feature(feature, cycle_id, coding, fact_out, applied)
            result["applied_files"] = applied
            result["registered_feature"] = entry["feature_name"]
            _log(f"applied {len(applied)} file(s); registered '{entry['feature_name']}'")
        else:
            result["applied_files"] = []
            _log("blocked or dry-run - no files applied" if not approved
                 else "dry-run - no files applied")
    finally:
        _worktree_remove(worktree, branch)

    report = REPO_ROOT / "store" / f"cycle_{cycle_id}.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    _log(f"report -> {report.relative_to(REPO_ROOT)}")
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Auto-mode feature shipping loop.")
    ap.add_argument("--max", type=int, default=1,
                    help="number of cycles to run; 0 = run forever until interrupted "
                         "(Ctrl+C)")
    ap.add_argument("--dry-run", action="store_true", help="plan+code but do not apply")
    ap.add_argument("--ui-every", type=int, default=3,
                    help="every Nth cycle is UI-focused (benchmarked against Tracxn + "
                         "Siemens iX, always on the cheap tier); 0 disables the UI "
                         "Improver agent entirely; 1 = every cycle is UI-focused")
    ap.add_argument("--ui-code-tier", choices=["cheap", "expensive"], default="cheap",
                    help="which model tier writes the code on UI-focused cycles "
                         "(default cheap; use expensive for faster, more reliable "
                         "file generation at higher cost - needs the expensive key set)")
    args = ap.parse_args()

    forever = args.max <= 0
    results: list = []
    i = 0
    try:
        while forever or i < args.max:
            i += 1
            ui_focus = args.ui_every > 0 and i % args.ui_every == 0
            label = f"{i}/{args.max}" if not forever else f"{i}"
            _log(f"=== cycle {label} ===" + (" [ui-focus]" if ui_focus else ""))
            res = run_cycle(dry_run=args.dry_run, ui_focus=ui_focus,
                            code_tier=args.ui_code_tier)
            results.append(res)
            print(json.dumps(res, indent=2, ensure_ascii=False))
            if res.get("blocking_reasons") == ["llm_unavailable"]:
                _log("stopping: LLM unavailable (set OPENAI_API_KEY).")
                break
    except KeyboardInterrupt:
        _log("interrupted by user - stopping after current cycle")

    shipped = sum(1 for r in results if r.get("merge_decision") == "approved")
    _log(f"done: {shipped}/{len(results)} cycle(s) shipped a feature")
    return 0 if shipped else 1


if __name__ == "__main__":
    sys.exit(main())
