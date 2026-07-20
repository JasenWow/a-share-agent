#!/usr/bin/env python3
"""
Migration gate — verifies test suites stay green across restructuring phases.

Why this exists:
    The restructure (see RESTRUCTURE-PLAN.md) moves code around in 7 phases.
    Each phase must keep all existing tests passing. This script runs every
    test suite that existed at the start of the restructure and reports the
    total count + pass/fail. It is the single source of truth for "did this
    phase break anything".

Why per-directory invocation:
    Several test files share the basename `test_server.py` (one per MCP
    server). Running pytest from root fails with import ambiguity. Invoking
    each directory separately sidesteps the conflict.

Usage:
    python scripts/check_migration.py           # run all suites
    python scripts/check_migration.py --baseline # record baseline (Phase 0 only)

Exit code:
    0 — all suites green
    1 — at least one suite failed or count regressed from baseline
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Directories with standalone test suites at restructure start (Phase 0).
# Order matters only for readability. Each is invoked independently.
TEST_SUITES = [
    ("root-integration", "tests"),
    ("etl", "scripts/etl/tests"),
    ("metrics", "metrics"),
    ("notebooks", "notebooks"),
    ("akshare-server", "mcp-servers/akshare-server"),
    ("tushare-server", "mcp-servers/tushare-server"),
    ("internal-store", "mcp-servers/internal-store"),
]

# Known-broken at Phase 0 (pre-existing, not caused by restructure).
# These are tolerated; everything else must stay green.
# Each entry: suite-name -> reason.
KNOWN_BROKEN = {
    "simulation-integration": "imports `scripts.simulator` which doesn't exist as importable module — pre-existing drift",
    "tushare-server": "tests require TUSHARE_TOKEN env var; editable install also fails (missing setuptools exclude) — pre-existing, fixed in Phase 2",
}

BASELINE_FILE = ROOT / "scripts" / ".migration-baseline.json"


def run_suite(name: str, rel_path: str) -> dict:
    """Run pytest in a single directory, return result dict."""
    suite_dir = ROOT / rel_path
    if not suite_dir.exists():
        return {"name": name, "path": rel_path, "status": "missing", "passed": 0, "failed": 0, "total": 0}

    result = subprocess.run(
        ["uv", "run", "pytest", str(suite_dir), "-q", "--no-header", "--tb=no", "-p", "no:cacheprovider"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )

    # Parse "X passed" or "X failed, Y passed" from the summary line.
    passed = 0
    failed = 0
    for line in result.stdout.splitlines() + result.stderr.splitlines():
        line = line.strip()
        if "passed" in line and ("error" not in line.lower()):
            # e.g. "132 passed in 0.69s" or "2 failed, 130 passed in 0.7s"
            parts = line.split()
            for i, part in enumerate(parts):
                if part == "passed":
                    # Look backwards for the number
                    if i > 0 and parts[i - 1].isdigit():
                        passed = int(parts[i - 1])
                elif part == "failed,":
                    if i > 0 and parts[i - 1].isdigit():
                        failed = int(parts[i - 1])

    status = "green" if result.returncode == 0 else "red"
    return {"name": name, "path": rel_path, "status": status, "passed": passed, "failed": failed, "total": passed + failed}


def main():
    parser = argparse.ArgumentParser(description="Migration test gate")
    parser.add_argument("--baseline", action="store_true", help="Record baseline (Phase 0 only)")
    parser.add_argument("--quiet", action="store_true", help="Only print summary")
    args = parser.parse_args()

    print("=" * 60)
    print("Migration Gate — test suites")
    print("=" * 60)

    results = []
    for name, path in TEST_SUITES:
        if args.quiet:
            print(f"  running {name}...", end=" ", flush=True)
        result = run_suite(name, path)
        # Known-broken suites get their status overridden so they don't fail CI,
        # but their pass counts are still tracked (regression = count drops further).
        if name in KNOWN_BROKEN and result["status"] == "red":
            result["status"] = "tolerated"
            result["known_broken_reason"] = KNOWN_BROKEN[name]
        results.append(result)
        if args.quiet:
            status_icon = {"green": "✅", "red": "❌", "tolerated": "⚠️ ", "missing": "🕳️ "}[result["status"]]
            print(f"{status_icon} {result['passed']} passed")
        else:
            status_icon = {"green": "✅", "red": "❌", "tolerated": "⚠️ ", "missing": "🕳️ "}[result["status"]]
            suffix = f"  [tolerated: {result.get('known_broken_reason', '')}]" if result["status"] == "tolerated" else ""
            print(f"  [{name:20s}] {status_icon} {result['passed']:>4d} passed  ({result['path']}){suffix}")

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
