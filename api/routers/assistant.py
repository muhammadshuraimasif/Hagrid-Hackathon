"""Policy Assistant Router for Citizen and Officer Inquiries.

Provides grounded RAG QA strictly derived from official guidelines with citations.
Enforces fail-closed human handoff on low-confidence queries.
"""
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.dependencies import get_current_user
from api.models import User
from api.ai.assistant_rag import policy_assistant

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


class AskRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=1000)


@router.post("/ask")
async def ask_policy_assistant(
    payload: AskRequest,
    current_user: User = Depends(get_current_user)
):
    """Answers citizen and helper policy inquiries with mandatory citations."""
    response = policy_assistant.answer_query(payload.query)
    return {
        "prototype": True,
        **response
    }
