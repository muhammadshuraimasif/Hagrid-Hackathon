import pytest
from eval.real_pipeline_eval import run_real_pipeline_evaluation


def test_real_pipeline_eval_execution():
    """Verifies that the real-pipeline evaluation executes end-to-end on image fixtures."""
    res = run_real_pipeline_evaluation(n_samples=10, seed=42)
    assert res["pipeline_type"] == "REAL_PIPELINE_FIXTURE_EVALUATION"
    assert res["sample_size_n"] == 10
    assert "route_mix_pct" in res
    assert "AUTO" in res["route_mix_pct"]
    assert "ASK" in res["route_mix_pct"]
    assert "HUMAN" in res["route_mix_pct"]
    assert res["wrong_approvals_k"] == 0
    assert res["clopper_pearson_95_upper_bound"] > 0
    assert "forgery_forensics" in res
