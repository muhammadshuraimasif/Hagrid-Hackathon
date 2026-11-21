import pytest
from httpx import AsyncClient
from sqlalchemy import text, select
from api.database import AsyncSessionLocal
from api.models import AuditLog

from api.audit import record_audit_event

@pytest.mark.asyncio
async def test_database_blocks_update_on_audit_log():
    # Ensure at least one record exists
    await record_audit_event(
        actor_type="system",
        action="test.initial_seed",
        entity_type="system",
        tenant_id="tenant-prd"
    )
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(AuditLog).limit(1))
        row = res.scalars().first()
        assert row is not None

        # Attempting direct SQL UPDATE must be rejected by the trigger
        with pytest.raises(Exception) as exc_info:
            await session.execute(
                text(f"UPDATE audit_log SET action = 'tampered_action' WHERE id = {row.id};")
            )
            await session.commit()
        assert "audit_log is insert-only" in str(exc_info.value).lower()

@pytest.mark.asyncio
async def test_database_blocks_delete_on_audit_log():
    # Ensure at least one record exists
    await record_audit_event(
        actor_type="system",
        action="test.initial_seed_del",
        entity_type="system",
        tenant_id="tenant-prd"
    )
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(AuditLog).limit(1))
        row = res.scalars().first()
        assert row is not None

        # Attempting direct SQL DELETE must be rejected by the trigger
        with pytest.raises(Exception) as exc_info:
            await session.execute(
                text(f"DELETE FROM audit_log WHERE id = {row.id};")
            )
            await session.commit()
        assert "audit_log is insert-only" in str(exc_info.value).lower()

@pytest.mark.asyncio
async def test_tampering_detected_by_verify_endpoint(client: AsyncClient, auditor_prd_token: str):
    headers = {"Authorization": f"Bearer {auditor_prd_token}"}

    # 1. First, verification should be healthy
    res_initial = await client.get("/api/v1/audit/verify", headers=headers)
    assert res_initial.status_code == 200
    initial_data = res_initial.json()
    assert initial_data["ok"] is True
    assert initial_data["checked"] > 0
    assert initial_data["broken_at_id"] is None

    # 2. Add a test row to tamper with
    test_entry = await record_audit_event(
        actor_type="test",
        action="test.tamper_target",
        entity_type="test",
        tenant_id="tenant-prd"
    )
    tampered_id = test_entry.id
    original_hash = test_entry.hash

    # 3. Simulate attacker tampering: drop SQLite trigger, modify the row, recreate trigger
    async with AsyncSessionLocal() as session:
        await session.execute(text("DROP TRIGGER IF EXISTS audit_log_block_update;"))
        await session.execute(
            text(f"UPDATE audit_log SET hash = 'tampered_invalid_sha256_hash_value' WHERE id = {tampered_id};")
        )
        await session.commit()

        # Reinstall trigger
        await session.execute(text("""
        CREATE TRIGGER IF NOT EXISTS audit_log_block_update
        BEFORE UPDATE ON audit_log
        BEGIN
            SELECT RAISE(ABORT, 'audit_log is insert-only');
        END;
        """))
        await session.commit()

    # 4. Call verify endpoint: must report broken chain at tampered_id
    res_tampered = await client.get("/api/v1/audit/verify", headers=headers)
    assert res_tampered.status_code == 200
    tampered_data = res_tampered.json()
    assert tampered_data["ok"] is False
    assert tampered_data["broken_at_id"] == tampered_id

    # 5. Restore original hash so database chain remains clean for other tests
    async with AsyncSessionLocal() as session:
        await session.execute(text("DROP TRIGGER IF EXISTS audit_log_block_update;"))
        await session.execute(
            text(f"UPDATE audit_log SET hash = '{original_hash}' WHERE id = {tampered_id};")
        )
        await session.commit()
        await session.execute(text("""
        CREATE TRIGGER IF NOT EXISTS audit_log_block_update
        BEFORE UPDATE ON audit_log
        BEGIN
            SELECT RAISE(ABORT, 'audit_log is insert-only');
        END;
        """))
        await session.commit()

@pytest.mark.asyncio
async def test_audit_list_pagination(client: AsyncClient, auditor_prd_token: str):
    headers = {"Authorization": f"Bearer {auditor_prd_token}"}
    res = await client.get("/api/v1/audit?limit=5&offset=0", headers=headers)
    assert res.status_code == 200
    logs = res.json()
    assert isinstance(logs, list)
    assert len(logs) <= 5
    if logs:
        assert "prev_hash" in logs[0]
        assert "hash" in logs[0]
        assert logs[0]["tenant_id"] == "tenant-prd"
