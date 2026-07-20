#!/usr/bin/env python3
"""
Migration gate — verifies test suites stay green across restructuring phases.

Why this exists:
    The restructure (see RESTRUCTURE-PLAN.md) moves code around in 7 phases.
    Each phase must keep all existing tests passing. This script runs every
    test suite that existed at the start of the restructure and reports the
    total count + pass/fail. It is the single source of truth for "did this
    phase break anything".

Runner modes (a suite runs in exactly one mode):
  - "root":     `uv run pytest <path>` from repo root (pre-Phase 2 Python code)
  - "package":  `uv run --package <pkg> pytest <path>` from python/ (MCP servers
                with their own deps; need uv workspace member resolution)
  - "py-aquan": `uv run pytest <path>` from python/ (post-migration aquan tests)

Usage:
    python scripts/check_migration.py           # run all suites
    python scripts/check_migration.py --baseline # record baseline (Phase 0 only)

Exit code:
    0 — all suites green (or tolerated known-broken)
    1 — at least one suite failed or count regressed from baseline
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
PYTHON_ROOT = ROOT / "python"

# Each suite: (name, runner, path, package?)
#   runner="root"     -> cwd=ROOT,    cmd=`uv run pytest <path>`
#   runner="package"  -> cwd=python/, cmd=`uv run --package <pkg> pytest <path>`
#   runner="py-aquan" -> cwd=python/, cmd=`uv run pytest <path>`
TEST_SUITES = [
    # Phase 4: root-level tests/notebooks moved into python/. All Python
    # code now lives under python/, so everything uses py-aquan runner.
    ("root-integration", "py-aquan", "tests", None),
    ("etl", "py-aquan", "etl/tests", None),
    ("metrics", "py-aquan", "aquan/metrics/tests", None),
    ("notebooks", "py-aquan", "notebooks", None),
    # MCP servers — moved to python/mcp-servers/ in Phase 2, run via --package
    ("akshare-server", "package", "mcp-servers/akshare-server", "aquan-akshare-server"),
    ("tushare-server", "package", "mcp-servers/tushare-server", "aquan-tushare-server"),
    ("internal-store", "package", "mcp-servers/internal-store", "aquan-internal-store-server"),
    # aquan smoke tests + metrics catalog tests (Phase 1+)
    ("aquan-smoke", "py-aquan", "aquan/tests", None),
]

# Known-broken suites (pre-existing, not caused by restructure).
# Tolerated; everything else must stay green. suite-name -> reason.
KNOWN_BROKEN = {
    "simulation-integration": "imports `scripts.simulator` which doesn't exist as importable module — pre-existing drift (not in TEST_SUITES)",
    "tushare-server": "server.py raises ValueError at import time if TUSHARE_TOKEN env var is missing — pre-existing design issue, deferred",
}

BASELINE_FILE = ROOT / "scripts" / ".migration-baseline.json"


def run_suite(name: str, runner: str, rel_path: str, package: str | None) -> dict:
    """Run pytest for one suite per its runner mode. Return result dict."""
    if runner == "root":
        cwd, path = ROOT, ROOT / rel_path
        cmd = ["uv", "run", "pytest", str(path), "-q", "--no-header", "--tb=no", "-p", "no:cacheprovider"]
    elif runner == "package":
        cwd, path = PYTHON_ROOT, PYTHON_ROOT / rel_path
        cmd = [
            "uv", "run", "--package", package,
            "pytest", str(path), "-q", "--no-header", "--tb=no", "-p", "no:cacheprovider",
        ]
    elif runner == "py-aquan":
        cwd, path = PYTHON_ROOT, PYTHON_ROOT / rel_path
        cmd = ["uv", "run", "pytest", str(path), "-q", "--no-header", "--tb=no", "-p", "no:cacheprovider"]
    else:
        return {"name": name, "path": rel_path, "status": "missing", "passed": 0, "failed": 0, "total": 0, "error": f"unknown runner {runner}"}

    if not path.exists():
        return {"name": name, "path": rel_path, "status": "missing", "passed": 0, "failed": 0, "total": 0}

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd))

    # Parse "X passed" or "X failed, Y passed" from the summary line.
    passed, failed = 0, 0
    for line in result.stdout.splitlines() + result.stderr.splitlines():
        line = line.strip()
        if "passed" in line and "error" not in line.lower():
            parts = line.split()
            for i, part in enumerate(parts):
                if part == "passed" and i > 0 and parts[i - 1].isdigit():
                    passed = int(parts[i - 1])
                elif part == "failed," and i > 0 and parts[i - 1].isdigit():
                    failed = int(parts[i - 1])

    status = "green" if result.returncode == 0 else "red"
    return {
        "name": name,
        "path": rel_path,
        "runner": runner,
        "package": package,
        "status": status,
        "passed": passed,
        "failed": failed,
        "total": passed + failed,
    }


def main():
    parser = argparse.ArgumentParser(description="Migration test gate")
    parser.add_argument("--baseline", action="store_true", help="Record baseline (Phase 0 only)")
    parser.add_argument("--quiet", action="store_true", help="Only print summary")
    args = parser.parse_args()

    print("=" * 60)
    print("Migration Gate — test suites")
    print("=" * 60)

    results = []
    for suite in TEST_SUITES:
        name, runner, rel_path, package = suite
        if args.quiet:
            print(f"  running {name}...", end=" ", flush=True)
        result = run_suite(name, runner, rel_path, package)
        # Known-broken suites don't fail CI, but their pass counts still track regressions.
        if name in KNOWN_BROKEN and result["status"] == "red":
            result["status"] = "tolerated"
            result["known_broken_reason"] = KNOWN_BROKEN[name]
        results.append(result)
        icons = {"green": "✅", "red": "❌", "tolerated": "⚠️ ", "missing": "🕳️ "}
        if args.quiet:
            print(f"{icons[result['status']]} {result['passed']} passed")
        else:
            suffix = f"  [tolerated: {result.get('known_broken_reason', '')}]" if result["status"] == "tolerated" else ""
            runner_tag = f" ({runner}" + (f":{package}" if package else "") + ")"
            print(f"  [{name:24s}] {icons[result['status']]} {result['passed']:>4d} passed  ({rel_path}){runner_tag}{suffix}")

    total_passed = sum(r["passed"] for r in results)
    real_red = [r for r in results if r["status"] == "red"]

    print("-" * 60)
    print(f"Total: {total_passed} tests passed across {len(results)} suites")

    if args.baseline:
        BASELINE_FILE.write_text(json.dumps({"total_passed": total_passed, "suites": results}, indent=2))
        print(f"\n📄 Baseline recorded: {total_passed} tests → {BASELINE_FILE.relative_to(ROOT)}")
        return 0

    if BASELINE_FILE.exists():
        baseline = json.loads(BASELINE_FILE.read_text())
        baseline_total = baseline["total_passed"]
        if total_passed < baseline_total:
            print(f"\n❌ REGRESSION: {baseline_total} → {total_passed} ({baseline_total - total_passed} tests lost)")
            return 1
        elif total_passed > baseline_total:
            print(f"\n📈 GROWTH: {baseline_total} → {total_passed} (+{total_passed - baseline_total} new tests)")

    if real_red:
        print(f"\n❌ {len(real_red)} suite(s) failed")
        for r in real_red:
            print(f"   - {r['name']} ({r['path']})")
        return 1

    tolerated = [r for r in results if r["status"] == "tolerated"]
    if tolerated:
        print(f"\n⚠️  {len(tolerated)} suite(s) tolerated (known-broken, see KNOWN_BROKEN)")
    print("\n✅ All suites green (or tolerated)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
