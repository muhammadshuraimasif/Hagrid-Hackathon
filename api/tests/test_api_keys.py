import pytest
from httpx import AsyncClient
from sqlalchemy import select
from api.database import AsyncSessionLocal
from api.models import AuditLog

@pytest.mark.asyncio
async def test_admin_create_and_list_api_keys(client: AsyncClient, admin_prd_token: str):
    headers = {"Authorization": f"Bearer {admin_prd_token}"}

    # 1. Create API key
    payload = {"name": "Public Portal Key", "scopes": ["case_status:read", "policy_assistant"]}
    res_create = await client.post("/api/v1/admin/api-keys", json=payload, headers=headers)
    assert res_create.status_code == 201
    created = res_create.json()
    assert "api_key" in created
    assert created["api_key"].startswith("amk_")
    assert created["key_prefix"].startswith("amk_")
    assert created["scopes"] == ["case_status:read", "policy_assistant"]
    assert created["is_active"] is True

    # 2. List API keys: secret is not in the list
    res_list = await client.get("/api/v1/admin/api-keys", headers=headers)
    assert res_list.status_code == 200
    keys = res_list.json()
    assert any(k["id"] == created["id"] for k in keys)
    for k in keys:
        assert "api_key" not in k

@pytest.mark.asyncio
async def test_api_key_public_whoami_scope_enforcement(client: AsyncClient, admin_prd_token: str):
    headers = {"Authorization": f"Bearer {admin_prd_token}"}

    # Create a key WITH case_status:read
    res1 = await client.post(
        "/api/v1/admin/api-keys",
        json={"name": "Valid Key", "scopes": ["case_status:read"]},
        headers=headers
    )
    valid_key = res1.json()["api_key"]

    # Create a key WITHOUT case_status:read
    res2 = await client.post(
        "/api/v1/admin/api-keys",
        json={"name": "Restricted Key", "scopes": ["scan_message"]},
        headers=headers
    )
    restricted_key = res2.json()["api_key"]

    # 1. Valid key can call /whoami
    res_whoami = await client.get("/api/v1/public/whoami", headers={"X-API-Key": valid_key})
    assert res_whoami.status_code == 200
    whoami_data = res_whoami.json()
    assert whoami_data["status"] == "ok"
    assert "case_status:read" in whoami_data["scopes"]

    # 2. Key missing scope gets 403 Forbidden and audit log
    res_denied = await client.get("/api/v1/public/whoami", headers={"X-API-Key": restricted_key})
    assert res_denied.status_code == 403
    envelope = res_denied.json()
    assert envelope["code"] == "FORBIDDEN"
    assert "missing required scope" in envelope["message"]

    # Verify audit record for denied scope
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AuditLog)
            .where(AuditLog.action == "rbac.denied_scope", AuditLog.actor_type == "api_key")
            .order_by(AuditLog.id.desc())
        )
        entry = result.scalars().first()
        assert entry is not None
        assert entry.tenant_id == "tenant-prd"

@pytest.mark.asyncio
async def test_admin_revoke_api_key(client: AsyncClient, admin_prd_token: str):
    headers = {"Authorization": f"Bearer {admin_prd_token}"}

    # Create key
    res_create = await client.post(
        "/api/v1/admin/api-keys",
        json={"name": "Temporary Key", "scopes": ["case_status:read"]},
        headers=headers
    )
    key_info = res_create.json()
    key_id = key_info["id"]
    raw_key = key_info["api_key"]

    # Revoke key
    res_del = await client.delete(f"/api/v1/admin/api-keys/{key_id}", headers=headers)
    assert res_del.status_code == 200

    # Calling with revoked key must fail with 401
    res_call = await client.get("/api/v1/public/whoami", headers={"X-API-Key": raw_key})
    assert res_call.status_code == 401
    assert res_call.json()["code"] == "UNAUTHORIZED"
