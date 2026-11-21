import asyncio
import hashlib
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import select, text
from api.database import AsyncSessionLocal, is_sqlite
from api.models import AuditLog

GENESIS_HASH = "0" * 64

# Async process-level lock to ensure strict append-only serialization
_audit_write_lock = asyncio.Lock()

def compute_canonical_json(data: Dict[str, Any]) -> str:
    """Produces deterministic canonical JSON (sorted keys, compact separators)."""
    return json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True)

def compute_entry_hash(prev_hash: str, canonical_payload: str) -> str:
    """Computes SHA-256 hash chaining previous hash and canonical payload."""
    combined = (prev_hash + canonical_payload).encode("utf-8")
    return hashlib.sha256(combined).hexdigest()

async def record_audit_event(
    actor_type: str,
    action: str,
    entity_type: str,
    actor_id: Optional[str] = None,
    entity_id: Optional[str] = None,
    acting_as: Optional[str] = None,
    request_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> AuditLog:
    """
    Writes an append-only, hash-chained audit record in an isolated short transaction
    AFTER the primary request commit has completed.
    Uses process lock (and Postgres advisory lock when running on Postgres).
    """
    created_at = datetime.now(timezone.utc)
    created_at_iso = created_at.isoformat()

    payload_data = {
        "action": action,
        "actor_id": actor_id or "",
        "actor_type": actor_type,
        "created_at": created_at_iso,
        "entity_id": entity_id or "",
        "entity_type": entity_type,
        "request_id": request_id or "",
        "tenant_id": tenant_id or "",
    }
    canonical_payload = compute_canonical_json(payload_data)

    async with _audit_write_lock:
        async with AsyncSessionLocal() as session:
            try:
                # If running on Postgres, acquire advisory lock for strict ordering
                if not is_sqlite:
                    await session.execute(text("SELECT pg_advisory_xact_lock(hashtext('audit_log_lock'));"))

                # Find the previous entry for this tenant to maintain tenant chain integrity
                query = select(AuditLog)
                if tenant_id:
                    query = query.where(AuditLog.tenant_id == tenant_id)
                else:
                    query = query.where(AuditLog.tenant_id.is_(None))
                
                query = query.order_by(AuditLog.id.desc()).limit(1)
                result = await session.execute(query)
                last_entry = result.scalars().first()

                prev_hash = last_entry.hash if last_entry else GENESIS_HASH
                entry_hash = compute_entry_hash(prev_hash, canonical_payload)

                log_entry = AuditLog(
                    tenant_id=tenant_id,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    action=action,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    acting_as=acting_as,
                    request_id=request_id,
                    prev_hash=prev_hash,
                    hash=entry_hash,
                    canonical_payload=canonical_payload,
                    created_at=created_at,
                )
                session.add(log_entry)
                await session.commit()
                await session.refresh(log_entry)
                return log_entry
            except Exception:
                await session.rollback()
                raise

async def verify_audit_chain(session, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Recomputes the cryptographic hash chain for the given tenant.
    Returns: {"ok": bool, "checked": int, "broken_at_id": Optional[int]}
    """
    query = select(AuditLog)
    if tenant_id:
        query = query.where(AuditLog.tenant_id == tenant_id)
    else:
        query = query.where(AuditLog.tenant_id.is_(None))
    query = query.order_by(AuditLog.id.asc())

    result = await session.execute(query)
    entries = result.scalars().all()

    expected_prev = GENESIS_HASH
    checked_count = 0

    for entry in entries:
        if entry.prev_hash != expected_prev:
            return {"ok": False, "checked": checked_count, "broken_at_id": entry.id}
        
        recomputed_hash = compute_entry_hash(expected_prev, entry.canonical_payload)
        if entry.hash != recomputed_hash:
            return {"ok": False, "checked": checked_count, "broken_at_id": entry.id}
        
        expected_prev = entry.hash
        checked_count += 1

    return {"ok": True, "checked": checked_count, "broken_at_id": None}
