from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models import User, Case, CaseEvent
from api.schemas import SyncPushRequest, SyncPushResponse, SyncPullResponse, CaseEventOut
from api.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/sync", tags=["Sync"])

@router.post("/push", response_model=SyncPushResponse)
async def push_sync_events(
    payload: SyncPushRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    processed = 0
    ignored_duplicates = 0

    for ev_in in payload.events:
        # Check if case exists and belongs to user's tenant
        case_res = await db.execute(
            select(Case).where(Case.id == ev_in.case_id, Case.tenant_id == current_user.tenant_id)
        )
        case = case_res.scalars().first()
        if not case:
            continue

        # Check deduplication by (case_id, client_uuid)
        existing_res = await db.execute(
            select(CaseEvent).where(
                CaseEvent.case_id == ev_in.case_id,
                CaseEvent.client_uuid == ev_in.client_uuid
            )
        )
        if existing_res.scalars().first() is not None:
            ignored_duplicates += 1
            continue

        # Insert event
        new_event = CaseEvent(
            case_id=ev_in.case_id,
            tenant_id=current_user.tenant_id,
            client_uuid=ev_in.client_uuid,
            event_type=ev_in.event_type,
            payload=ev_in.payload or {},
        )
        db.add(new_event)
        processed += 1

    await db.commit()
    return SyncPushResponse(status="ok", processed=processed, ignored_duplicates=ignored_duplicates)

@router.get("/pull", response_model=SyncPullResponse)
async def pull_sync_events(
    cursor: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Pull events for user's tenant
    query = (
        select(CaseEvent)
        .where(CaseEvent.tenant_id == current_user.tenant_id, CaseEvent.id > cursor)
        .order_by(CaseEvent.id.asc())
        .limit(limit)
    )
    result = await db.execute(query)
    events = result.scalars().all()

    next_cursor = events[-1].id if events else cursor
    return SyncPullResponse(
        events=events,
        next_cursor=next_cursor
    )
