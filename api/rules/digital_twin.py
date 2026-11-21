"""Digital Twin Impact Simulator.

Replays candidate/draft rule sets against historical decisions to measure impact,
cost shift, and identify risk cases moving to AUTO before publishing.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from api.models import Decision, RuleSet
from api.rules.engine import evaluate_case

async def run_digital_twin(
    session: AsyncSession,
    draft_rule_set: RuleSet,
    sample_size: int = 30
) -> Dict[str, Any]:
    """Replays historical decisions under the candidate draft rule set."""
    # Query recent decisions for this tenant
    stmt = (
        select(Decision)
        .where(Decision.tenant_id == draft_rule_set.tenant_id)
        .order_by(Decision.created_at.desc())
        .limit(sample_size)
    )
    res = await session.execute(stmt)
    historical_decisions = list(res.scalars().all())

    total_count = len(historical_decisions)
    newly_auto = 0
    newly_human = 0
    newly_ineligible = 0
    risk_cases: List[str] = []
    
    total_old_cost = 0.0
    total_new_cost = 0.0

    for dec in historical_decisions:
        old_route = dec.route
        old_cost = dec.expected_cost
        total_old_cost += old_cost

        # Re-evaluate stored snapshot under draft rule set
        eval_result = evaluate_case(draft_rule_set.definition, dec.input_snapshot)
        new_route = eval_result.route
        new_cost = eval_result.expected_cost
        total_new_cost += new_cost

        # Track transitions
        if old_route != "AUTO" and new_route == "AUTO":
            newly_auto += 1
            risk_cases.append(dec.case_id)
        
        if old_route != "HUMAN" and new_route == "HUMAN":
            newly_human += 1
            if eval_result.trace.get("has_fail"):
                newly_ineligible += 1

    cost_diff = (total_new_cost - total_old_cost)
    change_per_case = round(cost_diff / total_count, 2) if total_count > 0 else 0.0

    report = {
        "content_hash": draft_rule_set.content_hash,
        "sample_size": total_count,
        "newly_auto": newly_auto,
        "newly_human": newly_human,
        "newly_ineligible": newly_ineligible,
        "change_in_expected_cost_per_case": change_per_case,
        "total_expected_cost_old": round(total_old_cost, 2),
        "total_expected_cost_new": round(total_new_cost, 2),
        "risk_cases": risk_cases,
        "run_at": datetime.now(timezone.utc).isoformat(),
    }

    draft_rule_set.twin_report = report
    await session.flush()
    return report
