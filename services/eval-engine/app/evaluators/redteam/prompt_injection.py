"""Thin wrapper that shells out to Promptfoo's redteam CLI and parses results into
RedTeamFinding records. Used as a CI release gate (see .github/workflows/ci.yml) and
exposed via POST /redteam/run for on-demand runs from the console.

Promptfoo does the heavy lifting (probe generation, grading); this module just adapts
its JSON output into AgentEvalOS's shared schema so findings land in the same
Postgres table / console view as everything else.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from agentevalos_sdk.schemas import RedTeamFinding


def run_promptfoo_redteam(config_path: str, output_path: str = "/tmp/redteam_results.json") -> list[RedTeamFinding]:
    subprocess.run(
        ["promptfoo", "redteam", "eval", "-c", config_path, "-o", output_path],
        check=True,
    )
    raw = json.loads(Path(output_path).read_text())

    findings: list[RedTeamFinding] = []
    for result in raw.get("results", {}).get("results", []):
        grading = result.get("gradingResult", {})
        findings.append(
            RedTeamFinding(
                probe=result.get("testCase", {}).get("description", "unknown_probe"),
                category=result.get("testCase", {}).get("metadata", {}).get("category", "general"),
                severity=result.get("testCase", {}).get("metadata", {}).get("severity", "medium"),
                prompt=result.get("prompt", {}).get("raw", ""),
                response=result.get("response", {}).get("output", ""),
                flagged=not grading.get("pass", True),
                rationale=grading.get("reason"),
            )
        )
    return findings
