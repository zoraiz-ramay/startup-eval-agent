"""List features added by the multi-agent orchestrator.

Reads store/features.json (written on each approved cycle) and prints a table.

    python scripts/list_features.py
    python scripts/list_features.py --json
"""
import json
import pathlib
import sys

# Windows consoles often default to cp1252, which can't encode every character a
# feature name/summary might contain (e.g. a non-ASCII hyphen). Reconfigure stdout to
# UTF-8 with a safe fallback so listing the registry never crashes on print().
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY = REPO_ROOT / "store" / "features.json"


def main() -> int:
    if not REGISTRY.is_file():
        print("No features registered yet. Run the orchestrator to add one.")
        return 0

    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    features = data.get("features", [])

    if "--json" in sys.argv:
        print(json.dumps(features, indent=2))
        return 0

    if not features:
        print("No features registered yet.")
        return 0

    print(f"\n{len(features)} feature(s) added:\n")
    for f in features:
        bench = f.get("benchmark", {}) or {}
        print(f"  * {f.get('feature_name')}  [{f.get('status', 'added')}]")
        print(f"      cycle:     {f.get('cycle_id')}")
        print(f"      added_at:  {f.get('added_at')}")
        if f.get("summary"):
            print(f"      summary:   {f['summary']}")
        if f.get("files"):
            print(f"      files:     {len(f['files'])}")
            for rel in f["files"]:
                print(f"                 - {rel}")
        if bench.get("name"):
            print(f"      benchmark: {bench['name']} ({bench.get('source', '')})")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
