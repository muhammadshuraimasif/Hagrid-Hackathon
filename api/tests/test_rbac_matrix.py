import pytest
from httpx import AsyncClient
from sqlalchemy import select
from api.database import AsyncSessionLocal
from api.models import AuditLog

# Matrix configuration: (endpoint, method, allowed_roles)
ENDPOINTS = [
    ("/api/v1/admin/users", "GET", ["admin"]),
    ("/api/v1/admin/api-keys", "GET", ["admin"]),
    ("/api/v1/audit", "GET", ["auditor"]),
    ("/api/v1/audit/verify", "GET", ["auditor"]),
]

ALL_ROLES = ["citizen", "helper", "officer", "admin", "auditor"]

@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint,method,allowed_roles", ENDPOINTS)
@pytest.mark.parametrize("role", ALL_ROLES)
async def test_rbac_matrix(
    client: AsyncClient,
    citizen_prd_token: str,
    helper_prd_token: str,
    officer_prd_token: str,
    admin_prd_token: str,
    auditor_prd_token: str,
    endpoint: str,
    method: str,
    allowed_roles: list[str],
    role: str
):
    tokens = {
        "citizen": citizen_prd_token,
        "helper": helper_prd_token,
        "officer": officer_prd_token,
        "admin": admin_prd_token,
        "auditor": auditor_prd_token,
    }
    token = tokens[role]
    headers = {"Authorization": f"Bearer {token}"}

    if method == "GET":
        res = await client.get(endpoint, headers=headers)
    elif method == "POST":
        res = await client.post(endpoint, headers=headers, json={})
    else:
        raise ValueError(f"Unsupported method {method}")

    if role in allowed_roles:
        assert res.status_code in [200, 201], f"Expected {role} to access {endpoint}, got {res.status_code}: {res.text}"
    else:
        assert res.status_code == 403, f"Expected {role} to be FORBIDDEN on {endpoint}, got {res.status_code}"
        envelope = res.json()
        assert envelope["code"] == "FORBIDDEN"
        assert "request_id" in envelope

@pytest.mark.asyncio
async def test_rbac_denial_is_audited(client: AsyncClient, citizen_prd_token: str):
    # Citizen attempts to call admin endpoint
    res = await client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {citizen_prd_token}"})
    assert res.status_code == 403

    # Check database audit log directly for rbac.denied
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AuditLog)
            .where(AuditLog.action == "rbac.denied", AuditLog.entity_id == "/api/v1/admin/users")
            .order_by(AuditLog.id.desc())
        )
        entry = result.scalars().first()
        assert entry is not None
        assert entry.actor_type == "user"
        assert entry.tenant_id == "tenant-prd"
