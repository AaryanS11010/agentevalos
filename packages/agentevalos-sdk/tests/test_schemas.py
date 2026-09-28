from agentevalos_sdk.schemas import IndustryDomain, ModelLeaderboardEntry


def test_model_leaderboard_entry_can_be_built():
    entry = ModelLeaderboardEntry(
        industry=IndustryDomain.FINANCE,
        model_name="xgboost",
        dataset_ref="FINANCE.BENCHMARK_DATASET",
        primary_metric_name="auroc",
        primary_metric_value=0.9,
        impact_score=0.85,
    )
    assert entry.model_name == "xgboost"
    assert entry.impact_score == 0.85
