import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    res = await client.post("/api/v1/auth/login", json={"email": "officer@prd.test", "password": "Demo@12345"})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 900
    assert res.headers.get("x-amaanat-prototype") == "true"

@pytest.mark.asyncio
async def test_login_wrong_password_envelope(client: AsyncClient):
    res = await client.post("/api/v1/auth/login", json={"email": "officer@prd.test", "password": "WrongPassword"})
    assert res.status_code == 401
    data = res.json()
    assert data["code"] == "UNAUTHORIZED"
    assert "Invalid credentials" in data["message"]
    assert "request_id" in data

@pytest.mark.asyncio
async def test_login_nonexistent_email_does_not_leak(client: AsyncClient):
    res = await client.post("/api/v1/auth/login", json={"email": "nonexistent@prd.test", "password": "SomePassword"})
    assert res.status_code == 401
    data = res.json()
    assert data["code"] == "UNAUTHORIZED"
    assert "Invalid credentials" in data["message"]
    assert "request_id" in data

@pytest.mark.asyncio
async def test_lockout_after_5_failures(client: AsyncClient):
    from sqlalchemy import update
    from api.database import AsyncSessionLocal
    from api.models import User

    # Use citizen@mao.test to test lockout - reset first
    email = "citizen@mao.test"
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(User).where(User.email == email).values(failed_attempts=0, locked_until=None)
        )
        await session.commit()

    # Attempt 4 failed logins
    for i in range(4):
        res = await client.post("/api/v1/auth/login", json={"email": email, "password": "WrongPassword"})
        assert res.status_code == 401
    
    # 5th failed attempt must trigger 423 Locked
    res5 = await client.post("/api/v1/auth/login", json={"email": email, "password": "WrongPassword"})
    assert res5.status_code == 423
    data = res5.json()
    assert data["code"] == "LOCKED"
    assert "locked" in data["message"].lower()

    # Even with correct password, login must be blocked while locked
    res_blocked = await client.post("/api/v1/auth/login", json={"email": email, "password": "Demo@12345"})
    assert res_blocked.status_code == 423
    assert res_blocked.json()["code"] == "LOCKED"

    # Reset lockout state so subsequent tests can use this user
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(User).where(User.email == email).values(failed_attempts=0, locked_until=None)
        )
        await session.commit()

@pytest.mark.asyncio
async def test_refresh_token_rotation_success(client: AsyncClient):
    # Login
    res_login = await client.post("/api/v1/auth/login", json={"email": "helper@prd.test", "password": "Demo@12345"})
    tokens = res_login.json()
    old_refresh = tokens["refresh_token"]

    # Rotate
    res_refresh = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert res_refresh.status_code == 200
    new_tokens = res_refresh.json()
    assert new_tokens["access_token"] != tokens["access_token"]
    assert new_tokens["refresh_token"] != old_refresh

@pytest.mark.asyncio
async def test_refresh_token_reuse_detection_revokes_all(client: AsyncClient):
    # Login
    res_login = await client.post("/api/v1/auth/login", json={"email": "admin@prd.test", "password": "Demo@12345"})
    tokens = res_login.json()
    original_refresh = tokens["refresh_token"]

    # Rotate once legally
    res_rotate = await client.post("/api/v1/auth/refresh", json={"refresh_token": original_refresh})
    assert res_rotate.status_code == 200
    rotated_refresh = res_rotate.json()["refresh_token"]

    # Now attacker replays original_refresh which was already rotated
    res_replay = await client.post("/api/v1/auth/refresh", json={"refresh_token": original_refresh})
    assert res_replay.status_code == 401
    data = res_replay.json()
    assert data["code"] == "UNAUTHORIZED"

    # Now verify that even the rotated_refresh is revoked due to reuse detection
    res_check = await client.post("/api/v1/auth/refresh", json={"refresh_token": rotated_refresh})
    assert res_check.status_code == 401

@pytest.mark.asyncio
async def test_refresh_invalid_token(client: AsyncClient):
    res = await client.post("/api/v1/auth/refresh", json={"refresh_token": "art_completely_fake_token_12345"})
    assert res.status_code == 401
    assert res.json()["code"] == "UNAUTHORIZED"

@pytest.mark.asyncio
async def test_auth_me(client: AsyncClient, officer_prd_token: str):
    res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {officer_prd_token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == "officer@prd.test"
    assert data["role"] == "officer"
    assert data["tenant_id"] == "tenant-prd"

@pytest.mark.asyncio
async def test_auth_logout(client: AsyncClient):
    res_login = await client.post("/api/v1/auth/login", json={"email": "auditor@mao.test", "password": "Demo@12345"})
    access_token = res_login.json()["access_token"]
    refresh_token = res_login.json()["refresh_token"]

    res_logout = await client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {access_token}"})
    assert res_logout.status_code == 200

    # Refresh should fail now
    res_refresh = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert res_refresh.status_code == 401
