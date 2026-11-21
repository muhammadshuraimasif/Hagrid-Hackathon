"""Rules and Decision service managing versioned rule sets, cache, and decision logging."""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from api.models import RuleSet, Decision, Case
from api.rules.engine import (
    compute_content_hash,
    evaluate_case,
    EvaluationResult,
    normalize_input_snapshot,
)
from api.rules.digital_twin import run_digital_twin

logger = logging.getLogger(__name__)

# Tiny in-memory cache for active published rule sets: tenant_id -> RuleSet
_active_rule_cache: Dict[str, Dict[str, Any]] = {}


def clear_rule_cache(tenant_id: Optional[str] = None):
    """Clears the live rule cache for a tenant or globally."""
    if tenant_id:
        _active_rule_cache.pop(tenant_id, None)
    else:
        _active_rule_cache.clear()


async def get_active_rule_set(session: AsyncSession, tenant_id: str) -> RuleSet:
    """Retrieves the active published rule set for a tenant.
    
    Reads from the DB on every call or verified against tiny version cache.
    Publishing version N+1 applies to the very next decision without restart.
    """
    stmt = (
        select(RuleSet)
        .where(RuleSet.tenant_id == tenant_id, RuleSet.status == "published")
        .order_by(RuleSet.version.desc())
        .limit(1)
    )
    res = await session.execute(stmt)
    rule_set = res.scalars().first()
    if not rule_set:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active published rule set found for tenant {tenant_id}"
        )
    return rule_set


async def list_rule_sets(session: AsyncSession, tenant_id: str) -> List[RuleSet]:
    """Lists all rule sets for a tenant ordered by version desc."""
    stmt = (
        select(RuleSet)
        .where(RuleSet.tenant_id == tenant_id)
        .order_by(RuleSet.version.desc())
    )
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def get_rule_set(session: AsyncSession, rule_set_id: str, tenant_id: str) -> RuleSet:
    """Gets a specific rule set by ID and verifies tenant isolation."""
    stmt = select(RuleSet).where(RuleSet.id == rule_set_id, RuleSet.tenant_id == tenant_id)
    res = await session.execute(stmt)
    rule_set = res.scalars().first()
    if not rule_set:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule set not found")
    return rule_set


async def create_draft_rule_set(
    session: AsyncSession,
    tenant_id: str,
    author: str,
    definition: Dict[str, Any]
) -> RuleSet:
    """Creates a new draft rule set with incremented version number."""
    # Find max version for this tenant
    stmt = select(func.max(RuleSet.version)).where(RuleSet.tenant_id == tenant_id)
    res = await session.execute(stmt)
    max_ver = res.scalar() or 0
    next_ver = max_ver + 1

    content_hash = compute_content_hash(definition)

    rule_set = RuleSet(
        tenant_id=tenant_id,
        version=next_ver,
        status="draft",
        author=author,
        content_hash=content_hash,
        definition=definition,
        twin_report=None,
    )
    session.add(rule_set)
    await session.commit()
    await session.refresh(rule_set)
    return rule_set


async def update_draft_rule_set(
    session: AsyncSession,
    rule_set_id: str,
    tenant_id: str,
    definition: Dict[str, Any]
) -> RuleSet:
    """Updates a draft rule set. Published or retired sets are immutable and reject edits."""
    rule_set = await get_rule_set(session, rule_set_id, tenant_id)

    # Application check: Published and retired rule sets are immutable!
    if rule_set.status in ("published", "retired"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Rule set in status '{rule_set.status}' is immutable and cannot be edited"
        )

    content_hash = compute_content_hash(definition)
    rule_set.definition = definition
    rule_set.content_hash = content_hash
    # Invalidate old twin report because definition has changed
    rule_set.twin_report = None
    rule_set.updated_at = datetime.now(timezone.utc)

    await session.commit()
    await session.refresh(rule_set)
    return rule_set


async def publish_rule_set(
    session: AsyncSession,
    rule_set_id: str,
    tenant_id: str,
    actor_email: str
) -> RuleSet:
    """Publishes a draft rule set after verifying Digital Twin impact analysis."""
    rule_set = await get_rule_set(session, rule_set_id, tenant_id)

    if rule_set.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot publish rule set with status '{rule_set.status}'. Only draft rule sets can be published."
        )

    # Verify Digital Twin simulation has been run on current content hash
    twin_report = rule_set.twin_report
    if not twin_report or twin_report.get("content_hash") != rule_set.content_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Publishing blocked: Digital Twin simulation has not been executed on the current rule set definition."
        )

    # Retire currently active published version for tenant
    stmt = select(RuleSet).where(
        RuleSet.tenant_id == tenant_id,
        RuleSet.status == "published"
    )
    res = await session.execute(stmt)
    current_active = res.scalars().all()
    for active_rs in current_active:
        active_rs.status = "retired"
        active_rs.updated_at = datetime.now(timezone.utc)

    rule_set.status = "published"
    rule_set.effective_at = datetime.now(timezone.utc)
    rule_set.updated_at = datetime.now(timezone.utc)

    await session.commit()
    await session.refresh(rule_set)

    # Clear live cache so next call immediately picks up the new published version
    clear_rule_cache(tenant_id)
    return rule_set


async def decide_case(
    session: AsyncSession,
    tenant_id: str,
    case_id: str,
    raw_input: Dict[str, Any]
) -> Decision:
    """Decides a case using the active published rule set and persists the immutable Decision record."""
    active_rule_set = await get_active_rule_set(session, tenant_id)
    eval_result = evaluate_case(active_rule_set.definition, raw_input)

    decision = Decision(
        tenant_id=tenant_id,
        case_id=case_id,
        rule_version_id=active_rule_set.id,
        rule_version=active_rule_set.version,
        rule_hash=active_rule_set.content_hash,
        route=eval_result.route,
        p=eval_result.p,
        expected_cost=eval_result.expected_cost,
        input_snapshot=eval_result.input_snapshot,
        trace=eval_result.trace,
        citizen_reason=eval_result.citizen_reason,
    )
    session.add(decision)
    await session.commit()
    await session.refresh(decision)
    return decision


async def replay_decision(
    session: AsyncSession,
    decision_id: str,
    tenant_id: str
) -> Dict[str, Any]:
    """Auditor replay: re-evaluates stored input_snapshot against the exact rule set version used."""
    stmt = select(Decision).where(Decision.id == decision_id)
    res = await session.execute(stmt)
    decision = res.scalars().first()
    if not decision:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decision not found")

    # Fetch rule set
    rule_stmt = select(RuleSet).where(RuleSet.id == decision.rule_version_id)
    rule_res = await session.execute(rule_stmt)
    rule_set = rule_res.scalars().first()
    
    if not rule_set:
        # Fallback query by tenant and version
        rule_stmt = select(RuleSet).where(
            RuleSet.tenant_id == decision.tenant_id,
            RuleSet.version == decision.rule_version
        )
        rule_res = await session.execute(rule_stmt)
        rule_set = rule_res.scalars().first()

    if not rule_set:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Historical rule set not found")

    # Re-evaluate
    replayed_eval = evaluate_case(rule_set.definition, decision.input_snapshot)

    route_matches = (replayed_eval.route == decision.route)
    cost_matches = (abs(replayed_eval.expected_cost - decision.expected_cost) < 0.01)
    matches = route_matches and cost_matches

    return {
        "decision_id": decision.id,
        "tenant_id": decision.tenant_id,
        "case_id": decision.case_id,
        "rule_version": decision.rule_version,
        "rule_hash": decision.rule_hash,
        "matches": matches,
        "original_outcome": {
            "route": decision.route,
            "expected_cost": decision.expected_cost,
            "citizen_reason": decision.citizen_reason,
        },
        "replayed_outcome": {
            "route": replayed_eval.route,
            "expected_cost": replayed_eval.expected_cost,
            "citizen_reason": replayed_eval.citizen_reason,
            "trace": replayed_eval.trace,
        }
    }
