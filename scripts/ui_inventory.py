#!/usr/bin/env python3
"""Generate docs/ui-inventory.json — a factual map of the frontend, derived from source.

Agents hallucinate component names, props and routes when they answer from memory. This file is
regenerated as a gate step and read by agents instead, so what they act on is what the repo
actually contains. It is checked in deliberately: `--check` fails when it is stale, which is what
turns "the inventory is accurate" into something CI can enforce rather than hope for.

Usage:
    py -3 scripts/ui_inventory.py            # write docs/ui-inventory.json
    py -3 scripts/ui_inventory.py --check    # exit 1 if the file is stale
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
UI_SRC = ROOT / "ui" / "src"
OUT = ROOT / "docs" / "ui-inventory.json"

# <Route path="/startup/:id" element={<Profile />} />
_ROUTE = re.compile(r'<Route\s+path="([^"]+)"\s+element=\{<(\w+)', re.S)
# export default function Name(  |  export function Name(  |  export const Name = (
_EXPORT = re.compile(r"export\s+(?:default\s+)?(?:function|const)\s+(\w+)")
# api.js entries:  name: (args) => request(...)
_API = re.compile(r"^\s{2}(\w+):\s*\(([^)]*)\)\s*=>", re.M)
# --token-name: value;  (declarations only, not var() references)
_TOKEN = re.compile(r"^\s*(--[\w-]+)\s*:", re.M)
# className="a b c"
_CLASS = re.compile(r'className="([^"{]+)"')


def _rel(p: pathlib.Path) -> str:
    return p.relative_to(ROOT).as_posix()


def _read(p: pathlib.Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def build() -> dict:
    app = _read(UI_SRC / "App.jsx")
    routes = [{"path": path, "component": comp} for path, comp in _ROUTE.findall(app)]

    files = []
    for p in sorted(UI_SRC.rglob("*.jsx")):
        src = _read(p)
        files.append({
            "path": _rel(p),
            "lines": src.count("\n") + 1 if src else 0,
            "exports": sorted(set(_EXPORT.findall(src))),
            # Which shared CSS classes a file leans on — the quickest signal that a change is
            # drifting from the established Tracxn layout vocabulary.
            "css_classes": sorted({c for m in _CLASS.findall(src) for c in m.split() if c}),
        })

    api_src = _read(UI_SRC / "api.js")
    api = [{"method": name, "args": [a.strip() for a in args.split(",") if a.strip()]}
           for name, args in _API.findall(api_src)]

    tokens = sorted(set(_TOKEN.findall(_read(UI_SRC / "tokens.css"))))

    return {
        "_generated_by": "scripts/ui_inventory.py",
        "_note": "Generated from source. Do not edit by hand; run the script.",
        "routes": routes,
        "api_methods": api,
        "design_tokens": tokens,
        "files": files,
        "totals": {
            "routes": len(routes),
            "api_methods": len(api),
            "design_tokens": len(tokens),
            "jsx_files": len(files),
            "jsx_lines": sum(f["lines"] for f in files),
        },
    }


def main() -> int:
    data = json.dumps(build(), indent=2, ensure_ascii=False) + "\n"
    if "--check" in sys.argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != data:
            print(f"STALE: {_rel(OUT)} does not match the source tree.\n"
                  f"       Run: py -3 scripts/ui_inventory.py", file=sys.stderr)
            return 1
        print(f"ok: {_rel(OUT)} is current")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(data, encoding="utf-8")
    print(f"wrote {_rel(OUT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
