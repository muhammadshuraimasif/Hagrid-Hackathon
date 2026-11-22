"""Evaluation router for Project Amaanat.

Provides API endpoints for retrieving benchmark evaluation metrics and executing
evaluation harness runs.
Enforces AGENTS.md rule 6: Zero Metric Invention.
All metrics originate strictly from harness runs.
"""
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.dependencies import require_roles
from api.models import User, EvalRun
from api.audit import record_audit_event
from eval.harness import run_evaluation_harness
from eval.real_pipeline_eval import run_real_pipeline_evaluation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/eval", tags=["evaluation"])


class EvalRunRequest(BaseModel):
    seed: Optional[int] = 42


@router.get("/latest")
async def get_latest_eval_run(
    current_user: User = Depends(require_roles("admin", "auditor")),
    db: AsyncSession = Depends(get_db)
):
    """Returns the latest evaluation benchmark run and verified metrics."""
    res = await db.execute(
        select(EvalRun).where(EvalRun.is_latest == True).order_by(EvalRun.created_at.desc())
    )
    run = res.scalars().first()

    if not run:
        # If no run stored yet, execute deterministic benchmark with default seed 42
        results = run_evaluation_harness(seed=42)
        run = EvalRun(
            seed=results["seed"],
            total_cases=results["dataset_summary"]["total_cases"],
            split_counts=results["dataset_summary"],
            tau_chosen=results["optimal_tau"],
            clopper_pearson_upper=results["test_evaluation"]["clopper_pearson_95_upper_bound"],
            wrong_approval_rate=results["test_evaluation"]["measured_wrong_approval_rate"],
            test_metrics={
                "route_mix": results["test_evaluation"]["route_mix"],
                "expected_cost_per_case_sweep": results["test_evaluation"]["expected_cost_per_case_sweep"],
                "expected_calibration_error": results["test_evaluation"]["expected_calibration_error"],
                "reliability_curve": results["test_evaluation"]["reliability_curve"],
                "fairness_analysis": results["fairness_analysis"],
                "sample_size_n": results["test_evaluation"]["sample_size_n"],
                "k_wrong_approvals": results["test_evaluation"]["k_wrong_approvals"],
                "bound_le_1pct": results["test_evaluation"]["bound_le_1pct"],
            },
            is_latest=True,
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)

    return {
        "id": run.id,
        "seed": run.seed,
        "total_cases": run.total_cases,
        "split_counts": run.split_counts,
        "tau_chosen": run.tau_chosen,
        "clopper_pearson_upper": run.clopper_pearson_upper,
        "wrong_approval_rate": run.wrong_approval_rate,
        "test_metrics": run.test_metrics,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


@router.get("/real-pipeline")
async def get_real_pipeline_metrics(
    current_user: User = Depends(require_roles("admin", "auditor")),
):
    """Returns the real-pipeline 200-case evaluation on actual card image fixtures and AI models."""
    return run_real_pipeline_evaluation(n_samples=200, seed=42)


@router.post("/run")
async def trigger_eval_run(
    payload: EvalRunRequest,
    request: Request,
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db)
):
    """Triggers an evaluation benchmark run and stores verified metrics."""
    request_id = getattr(request.state, "request_id", None)
    seed = payload.seed if payload.seed is not None else 42
    results = run_evaluation_harness(seed=seed)

    # De-mark previous runs
    await db.execute(update(EvalRun).values(is_latest=False))

    test_info = results["test_evaluation"]
    run = EvalRun(
        seed=results["seed"],
        total_cases=results["dataset_summary"]["total_cases"],
        split_counts=results["dataset_summary"],
        tau_chosen=results["optimal_tau"],
        clopper_pearson_upper=test_info["clopper_pearson_95_upper_bound"],
        wrong_approval_rate=test_info["measured_wrong_approval_rate"],
        test_metrics={
            "route_mix": test_info["route_mix"],
            "expected_cost_per_case_sweep": test_info["expected_cost_per_case_sweep"],
            "expected_calibration_error": test_info["expected_calibration_error"],
            "reliability_curve": test_info["reliability_curve"],
            "fairness_analysis": results["fairness_analysis"],
            "sample_size_n": test_info["sample_size_n"],
            "k_wrong_approvals": test_info["k_wrong_approvals"],
            "bound_le_1pct": test_info["bound_le_1pct"],
        },
        is_latest=True,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    await record_audit_event(
        tenant_id=current_user.tenant_id,
        actor_type="user",
        actor_id=current_user.id,
        action="EVAL_HARNESS_EXECUTED",
        entity_type="eval_run",
        entity_id=run.id,
        request_id=request_id,
    )

    return {
        "id": run.id,
        "seed": run.seed,
        "total_cases": run.total_cases,
        "split_counts": run.split_counts,
        "tau_chosen": run.tau_chosen,
        "clopper_pearson_upper": run.clopper_pearson_upper,
        "wrong_approval_rate": run.wrong_approval_rate,
        "test_metrics": run.test_metrics,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }
