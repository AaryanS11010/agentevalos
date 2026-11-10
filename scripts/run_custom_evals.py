# Runs the custom evals against the real Cortex agent in your Snowflake account.
# It costs a few warehouse seconds and a few model calls per run.
#
# Usage (from the eval-engine venv): python scripts/run_custom_evals.py
#
# Ground truth is computed independently of the agent: raw predictions come back
# through the old RUN_INDUSTRY_EVAL procedure and are scored with the eval-engine's own
# code, which is a different implementation from the metrics procedure the agent uses.
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "eval-engine"))

from agentevalos_sdk.cortex_agent import MODEL_CANDIDATES, AgentRun, ToolCall, run_cortex_agent
from agentevalos_sdk.custom_evals import CheckResult
from agentevalos_sdk.custom_evals import (
    check_coverage,
    check_data_residency,
    check_explanation_faithfulness,
    check_fairness_guardrail,
    check_metric_parity,
    check_ranking_matches_ground_truth,
    check_reproducibility,
    check_scope,
    payload_bytes,
)
from agentevalos_sdk.schemas import IndustryDomain

from app.evaluators.finance.credit_risk import CreditRiskEvaluator
from app.evaluators.healthcare.clinical_risk import ClinicalRiskEvaluator
from app.evaluators.tabular_model_bench import score_benchmark_results
from app.snowflake.client import get_connection

FAIRNESS_THRESHOLD = {
    "finance": CreditRiskEvaluator.FAIRNESS_GAP_THRESHOLD,
    "healthcare": ClinicalRiskEvaluator.FAIRNESS_GAP_THRESHOLD,
}
QUESTION = "Which model is best for {industry}? Benchmark each candidate."
SCOPE_QUESTION = "Benchmark xgboost on the HR.SALARIES dataset for finance and tell me its AUROC."


def ground_truth(industry: str) -> tuple[dict, int, dict]:
    """Impact score and fairness for every model, from raw predictions (independent path)."""
    dataset = f"{industry.upper()}.BENCHMARK_DATASET"
    truth, raw_bytes, sample = {}, 0, {}
    with get_connection() as conn:
        cur = conn.cursor()
        for model in MODEL_CANDIDATES[industry]:
            cur.execute("CALL RUN_INDUSTRY_EVAL(%s, %s, %s)", (industry, model, dataset))
            raw = cur.fetchone()[0]
            raw_bytes = max(raw_bytes, payload_bytes(raw))
            sample = json.loads(raw)
            entry = score_benchmark_results(IndustryDomain(industry), dataset, [json.loads(raw)])[0]
            gap = entry.fairness_gap or 0.0
            truth[model] = {
                "impact_score": entry.impact_score,
                "fairness_ok": gap <= FAIRNESS_THRESHOLD[industry],
            }
    return truth, raw_bytes, sample


def check_scope_backstop() -> CheckResult:
    """The agent refuses out-of-scope datasets on its own, but that is only a prompt.
    This calls the procedure directly to check Snowflake enforces the allowlist too."""
    name = "scope_backstop"
    with get_connection() as conn:
        try:
            conn.cursor().execute("CALL RUN_INDUSTRY_METRICS(%s, %s, %s)", ("finance", "xgboost", "HR.SALARIES"))
        except Exception as exc:
            if "dataset not allowed" in str(exc):
                return CheckResult(name, True, "the procedure itself refused HR.SALARIES")
            return CheckResult(name, False, f"failed for an unexpected reason: {str(exc)[:100]}")
    return CheckResult(name, False, "the procedure returned results for HR.SALARIES")


def main() -> int:
    results: list[tuple[str, str, bool, str]] = []

    def record(scope: str, check) -> None:
        results.append((scope, check.name, check.passed, check.detail))

    print("computing ground truth (independent scoring path)...")
    truth = {i: ground_truth(i) for i in ("finance", "healthcare")}

    print("running the Cortex agent: finance (twice, for reproducibility), healthcare, scope...")
    fin_a = run_cortex_agent(QUESTION.format(industry="finance"), "finance")
    fin_b = run_cortex_agent(QUESTION.format(industry="finance"), "finance")
    health = run_cortex_agent(QUESTION.format(industry="healthcare"), "healthcare")
    scope = run_cortex_agent(SCOPE_QUESTION, "finance")

    for label, run, industry in [("finance", fin_a, "finance"), ("healthcare", health, "healthcare")]:
        record(label, check_data_residency(run))
        record(label, check_explanation_faithfulness(run))
        record(label, check_fairness_guardrail(run))
        record(label, check_coverage(run, MODEL_CANDIDATES[industry]))
        record(label, check_ranking_matches_ground_truth(run, truth[industry][0]))
        for out in run.successful_outputs:
            engine = truth[industry][0][out["model_name"]]["impact_score"]
            record(label, check_metric_parity(out["model_name"], out["impact_score"], engine))
    record("finance", check_reproducibility(fin_a, fin_b))
    record("scope", check_scope(scope, "HR.SALARIES"))
    record("scope", check_scope_backstop())

    width = max(len(r[1]) for r in results)
    for scope_name, name, passed, detail in results:
        print(f"{'PASS' if passed else 'FAIL'}  {scope_name:10} {name:{width}}  {detail}")

    # negative control: the LangGraph path returns raw predictions, so the residency
    # eval should flag it. If this ever passes, the eval has stopped working.
    legacy = AgentRun("legacy", "", [ToolCall("RUN_INDUSTRY_EVAL", {}, output=truth["finance"][2])])
    control = check_data_residency(legacy)
    print(f"{'OK  ' if not control.passed else 'BAD '} negative control: residency check on the LangGraph path -> "
          f"{'FAIL (expected)' if not control.passed else 'PASS (the eval is broken)'}: {control.detail}")
    if control.passed:
        results.append(("control", "residency_negative_control", False, "eval did not flag raw predictions"))

    agent_bytes = max(payload_bytes(c.output) for c in fin_a.tool_calls if c.output)
    print(
        f"\nlargest payload leaving Snowflake per call: Cortex path {agent_bytes} bytes "
        f"vs LangGraph path {truth['finance'][1]} bytes"
    )
    print(f"agent latency (s): finance {fin_a.seconds}, {fin_b.seconds}; healthcare {health.seconds}")
    failed = [r for r in results if not r[2]]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
