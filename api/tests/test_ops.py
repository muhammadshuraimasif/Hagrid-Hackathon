import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    res = await client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["prototype"] is True
    assert res.headers.get("x-amaanat-prototype") == "true"
    assert "x-request-id" in res.headers

@pytest.mark.asyncio
async def test_ready_endpoint(client: AsyncClient):
    res = await client.get("/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["db"] == "ok"
    assert data["prototype"] is True

@pytest.mark.asyncio
async def test_x_request_id_passed_and_preserved(client: AsyncClient):
    custom_req_id = "test-custom-req-id-98765"
    res = await client.get("/health", headers={"X-Request-ID": custom_req_id})
    assert res.status_code == 200
    assert res.headers.get("x-request-id") == custom_req_id

@pytest.mark.asyncio
async def test_unknown_endpoint_returns_404_envelope(client: AsyncClient):
    res = await client.get("/nonexistent-endpoint")
    assert res.status_code == 404
    envelope = res.json()
    assert envelope["code"] == "NOT_FOUND"
    assert "request_id" in envelope
    assert res.headers.get("x-amaanat-prototype") == "true"
