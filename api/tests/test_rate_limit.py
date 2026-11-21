import pytest
from httpx import AsyncClient
from api.middleware import RateLimitMiddleware

@pytest.mark.asyncio
async def test_rate_limit_exceeded_returns_429(client: AsyncClient, citizen_prd_token: str):
    # We send requests with a custom unique IP header or many requests to /api/v1/auth/me
    headers = {"Authorization": f"Bearer {citizen_prd_token}"}
    
    # Send requests to consume allowance and exceed limit
    # The default rate limit is configured via settings
    hit_429 = False
    retry_after = None

    for _ in range(130):
        res = await client.get("/api/v1/auth/me", headers=headers)
        if res.status_code == 429:
            hit_429 = True
            retry_after = res.headers.get("retry-after")
            data = res.json()
            assert data["code"] == "RATE_LIMIT_EXCEEDED"
            assert "retry_after" in data
            assert data["retry_after"] > 0
            break

    assert hit_429, "Expected to trigger 429 Rate Limit Exceeded"
    assert retry_after is not None

@pytest.mark.asyncio
async def test_health_and_ready_exempt_from_rate_limit(client: AsyncClient):
    # Calling health and ready repeatedly should never return 429
    for _ in range(130):
        res_h = await client.get("/health")
        assert res_h.status_code == 200
        res_r = await client.get("/ready")
        assert res_r.status_code == 200
