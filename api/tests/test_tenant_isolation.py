import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_admin_users_tenant_isolated(client: AsyncClient, admin_prd_token: str, admin_mao_token: str):
    # PRD Admin gets PRD users
    res_prd = await client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {admin_prd_token}"})
    assert res_prd.status_code == 200
    prd_users = res_prd.json()
    assert len(prd_users) > 0
    assert all(u["tenant_id"] == "tenant-prd" for u in prd_users)
    assert not any(u["tenant_id"] == "tenant-mao" for u in prd_users)

    # MAO Admin gets MAO users
    res_mao = await client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {admin_mao_token}"})
    assert res_mao.status_code == 200
    mao_users = res_mao.json()
    assert len(mao_users) > 0
    assert all(u["tenant_id"] == "tenant-mao" for u in mao_users)
    assert not any(u["tenant_id"] == "tenant-prd" for u in mao_users)

@pytest.mark.asyncio
async def test_admin_api_keys_cross_tenant_isolation(client: AsyncClient, admin_prd_token: str, admin_mao_token: str):
    # PRD Admin creates a key
    res_create = await client.post(
        "/api/v1/admin/api-keys",
        json={"name": "PRD Specific Key", "scopes": ["case_status:read"]},
        headers={"Authorization": f"Bearer {admin_prd_token}"}
    )
    prd_key_id = res_create.json()["id"]

    # MAO Admin lists keys - must NOT see PRD key
    res_mao_list = await client.get(
        "/api/v1/admin/api-keys",
        headers={"Authorization": f"Bearer {admin_mao_token}"}
    )
    mao_keys = res_mao_list.json()
    assert not any(k["id"] == prd_key_id for k in mao_keys)

    # MAO Admin attempts to revoke PRD key - must return 404 (another tenant's key looks like 404)
    res_cross_delete = await client.delete(
        f"/api/v1/admin/api-keys/{prd_key_id}",
        headers={"Authorization": f"Bearer {admin_mao_token}"}
    )
    assert res_cross_delete.status_code == 404
    assert res_cross_delete.json()["code"] == "NOT_FOUND"

@pytest.mark.asyncio
async def test_audit_logs_cross_tenant_isolation(client: AsyncClient, auditor_prd_token: str, auditor_mao_token: str):
    # PRD Auditor lists logs
    res_prd = await client.get("/api/v1/audit", headers={"Authorization": f"Bearer {auditor_prd_token}"})
    assert res_prd.status_code == 200
    prd_logs = res_prd.json()
    if prd_logs:
        assert all(log["tenant_id"] == "tenant-prd" for log in prd_logs)

    # MAO Auditor lists logs
    res_mao = await client.get("/api/v1/audit", headers={"Authorization": f"Bearer {auditor_mao_token}"})
    assert res_mao.status_code == 200
    mao_logs = res_mao.json()
    if mao_logs:
        assert all(log["tenant_id"] == "tenant-mao" for log in mao_logs)
