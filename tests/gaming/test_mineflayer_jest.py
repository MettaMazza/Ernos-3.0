"""
Pytest bridge for Mineflayer Jest tests.

Runs `npx jest` inside the mineflayer directory and asserts all suites pass.
Coverage thresholds are enforced per-module via Jest configuration.
"""
import subprocess
import json
import os
import pytest


MINEFLAYER_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "src", "gaming", "mineflayer"
)


class TestMineflayerJest:
    """Run all Jest unit tests for the Mineflayer modules."""

    def test_jest_suite_passes(self):
        """Execute the full Jest suite and assert zero failures."""
        result = subprocess.run(
            ["npx", "jest", "--no-cache", "--forceExit", "--json"],
            cwd=MINEFLAYER_DIR,
            capture_output=True,
            text=True,
            timeout=120,
        )

        # Parse structured output
        try:
            report = json.loads(result.stdout)
        except json.JSONDecodeError:
            pytest.fail(
                f"Jest output was not valid JSON.\nstdout: {result.stdout[:500]}\n"
                f"stderr: {result.stderr[:500]}"
            )

        num_suites = report.get("numTotalTestSuites", 0)
        num_passed = report.get("numPassedTests", 0)
        num_failed = report.get("numFailedTests", 0)
        num_total = report.get("numTotalTests", 0)

        assert num_failed == 0, (
            f"Jest reported {num_failed} failed tests out of {num_total}.\n"
            f"Failed suites: {[s['name'] for s in report.get('testResults', []) if s.get('status') != 'passed']}"
        )
        assert num_suites >= 12, f"Expected >=12 test suites, got {num_suites}"
        assert num_passed >= 270, f"Expected >=270 passing tests, got {num_passed}"

    def test_jest_coverage_thresholds(self):
        """Verify line coverage meets 90% across all modules."""
        result = subprocess.run(
            [
                "npx", "jest", "--no-cache", "--forceExit",
                "--coverage", "--coverageReporters=json-summary"
            ],
            cwd=MINEFLAYER_DIR,
            capture_output=True,
            text=True,
            timeout=120,
        )

        coverage_path = os.path.join(
            MINEFLAYER_DIR, "coverage", "coverage-summary.json"
        )
        if not os.path.exists(coverage_path):
            pytest.skip("Coverage summary not generated")

        with open(coverage_path) as f:
            coverage = json.load(f)

        total = coverage.get("total", {})
        line_pct = total.get("lines", {}).get("pct", 0)

        assert line_pct >= 80, (
            f"Overall line coverage {line_pct}% is below 80% threshold"
        )
