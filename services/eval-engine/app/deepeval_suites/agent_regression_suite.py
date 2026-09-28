"""LLM-judge regression suite using DeepEval — catches quality regressions in the
agent's natural-language planning/explanation output (distinct from the deterministic
industry evaluators, which score the tabular models themselves).

DeepEval's metrics default to an OpenAI judge model and are "unusable until fixed"
(see `deepeval diagnose`) without OPENAI_API_KEY — this repo's .env.example only asks
for ANTHROPIC_API_KEY/OPENAI_API_KEY generically, so both judge_model below and every
metric explicitly pass model=judge_model to use whichever one is actually set,
Anthropic first.

Run with: pytest app/deepeval_suites/agent_regression_suite.py
Wired into CI (see .github/workflows/ci.yml).
"""

from __future__ import annotations

import os

from deepeval import assert_test
from deepeval.metrics import FaithfulnessMetric, GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams


def _judge_model():
    if os.getenv("ANTHROPIC_API_KEY"):
        from deepeval.models import AnthropicModel

        return AnthropicModel()  # DeepEval's own maintained default model
    if os.getenv("OPENAI_API_KEY"):
        from deepeval.models import GPTModel

        return GPTModel()
    raise RuntimeError(
        "Set ANTHROPIC_API_KEY or OPENAI_API_KEY in .env to run the DeepEval judge suite."
    )


judge_model = _judge_model()

leaderboard_explanation_quality = GEval(
    name="LeaderboardExplanationQuality",
    criteria=(
        "Does the agent's explanation of the model leaderboard correctly reference the "
        "actual metric values it was given, avoid unsupported claims, and stay specific "
        "to the industry (finance/healthcare) it was asked about?"
    ),
    evaluation_params=[
        LLMTestCaseParams.INPUT,
        LLMTestCaseParams.ACTUAL_OUTPUT,
        LLMTestCaseParams.CONTEXT,
    ],
    threshold=0.7,
    model=judge_model,
)

faithfulness = FaithfulnessMetric(threshold=0.8, model=judge_model)


def test_leaderboard_explanation_is_faithful_to_metrics():
    test_case = LLMTestCase(
        input="Explain why XGBoost ranked #1 for the finance credit-risk benchmark.",
        actual_output=(
            "XGBoost ranked #1 with an impact score of 0.81, driven by an AUROC of 0.79 "
            "and a low demographic parity gap of 0.04, meaning it discriminates well "
            "between defaulters and non-defaulters while treating protected groups "
            "similarly."
        ),
        context=[
            "XGBoost: auroc=0.79, ks_statistic=0.41, demographic_parity_gap=0.04, impact_score=0.81",
            "CatBoost: auroc=0.77, ks_statistic=0.39, demographic_parity_gap=0.09, impact_score=0.74",
        ],
        retrieval_context=[
            "XGBoost: auroc=0.79, ks_statistic=0.41, demographic_parity_gap=0.04, impact_score=0.81",
        ],
    )
    assert_test(test_case, [leaderboard_explanation_quality, faithfulness])
