# Runs Promptfoo's red-team CLI and turns the results into RedTeamFinding records.
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
