"""Scam Shield Router for Citizen and API Security.

Endpoints for scanning suspicious messages, validating official Amaanat codes,
collecting community feedback, and inspecting held-out eval benchmarks.
"""
import hashlib
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.dependencies import get_current_user, require_roles
from api.models import User, ScamScan, ScamVerification
from api.ai.scam_shield import scam_shield, ScamScanResult, verify_trust_code

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/scam", tags=["scam-shield"])


class ScanRequest(BaseModel):
    message: str = Field(..., min_length=3, max_length=2000)
    code: Optional[str] = None
    case_id: Optional[str] = None
    phone: Optional[str] = None


class VerifyCodeRequest(BaseModel):
    code: str
    case_id: str
    phone: str


class FeedbackRequest(BaseModel):
    scan_id: str
    feedback: str = Field(..., pattern="^(helpful|false_positive|false_negative)$")


@router.post("/scan", response_model=ScamScanResult)
async def scan_message_endpoint(
    payload: ScanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Scans an incoming message for phishing, fee scam, or spoofing patterns."""
    result = await scam_shield.scan_message(
        message_text=payload.message,
        verification_code=payload.code,
        case_id=payload.case_id,
        recipient_phone=payload.phone,
        db=db,
        tenant_id=current_user.tenant_id if current_user else None
    )

    # Persist redacted scan in DB
    msg_hash = hashlib.sha256(payload.message.encode("utf-8")).hexdigest()
    try:
        scan_record = ScamScan(
            tenant_id=current_user.tenant_id if current_user else None,
            user_id=current_user.id if current_user else None,
            message_hash=msg_hash,
            redacted_text=result.redacted_message,
            verdict=result.verdict,
            confidence=result.confidence,
            red_flags=result.red_flags,
            voter_breakdown=result.voter_breakdown
        )
        db.add(scan_record)
        await db.commit()
    except Exception as e:
        logger.warning(f"Could not persist scam scan: {e}")

    return result


@router.post("/verify-code")
async def verify_code_endpoint(
    payload: VerifyCodeRequest,
    current_user: User = Depends(get_current_user)
):
    """Verifies whether an SMS/WhatsApp verification code is authentic."""
    is_valid = verify_trust_code(payload.code, payload.case_id, payload.phone)
    return {
        "code": payload.code,
        "is_valid": is_valid,
        "message": "Official Amaanat communication verified authentic." if is_valid else "Invalid or untrusted verification code."
    }


@router.post("/feedback")
async def submit_feedback_endpoint(
    payload: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Collects citizen feedback on scan accuracy."""
    res = await db.execute(select(ScamScan).where(ScamScan.id == payload.scan_id))
    scan = res.scalars().first()
    if not scan:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Scan record not found"})

    scan.feedback = payload.feedback
    await db.commit()
    return {"status": "SUCCESS", "message": "Feedback recorded."}


@router.get("/metrics")
async def get_scam_metrics_endpoint(
    current_user: User = Depends(require_roles("admin", "auditor"))
):
    """Returns held-out test set performance metrics for Scam Shield."""
    from eval.hard_scam_benchmark import evaluate_hard_benchmark
    hard_metrics = evaluate_hard_benchmark(scam_shield)
    return {
        "prototype": True,
        "templated_metrics": scam_shield.eval_metrics,
        "hard_non_templated_metrics": hard_metrics
    }
