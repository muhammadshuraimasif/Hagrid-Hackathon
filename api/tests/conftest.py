import os
os.environ["TESTING"] = "1"
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from api.config import settings
from api.database import Base, init_db, SQLITE_AUDIT_TRIGGERS
from api.seed import seed_data
from api.main import app
from api.models import User
from api.security import create_access_token
from api.middleware import _rate_limit_windows

TEST_DB_PATH = "./test_suite.db"
TEST_DB_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH}"

@pytest_asyncio.fixture(autouse=True)
async def setup_test_database():
    _rate_limit_windows.clear()
    # Remove old test db file if exists
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass

    settings.DATABASE_URL = TEST_DB_URL
    await init_db()
    await seed_data()
    yield
    # Cleanup after test suite
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

async def get_token_for(client: AsyncClient, email: str) -> str:
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": "Demo@12345"})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["access_token"]

@pytest_asyncio.fixture
async def citizen_prd_token(client: AsyncClient):
    return await get_token_for(client, "citizen@prd.test")

@pytest_asyncio.fixture
async def helper_prd_token(client: AsyncClient):
    return await get_token_for(client, "helper@prd.test")

@pytest_asyncio.fixture
async def officer_prd_token(client: AsyncClient):
    return await get_token_for(client, "officer@prd.test")

@pytest_asyncio.fixture
async def admin_prd_token(client: AsyncClient):
    return await get_token_for(client, "admin@prd.test")

@pytest_asyncio.fixture
async def auditor_prd_token(client: AsyncClient):
    return await get_token_for(client, "auditor@prd.test")

@pytest_asyncio.fixture
async def admin_mao_token(client: AsyncClient):
    return await get_token_for(client, "admin@mao.test")

@pytest_asyncio.fixture
async def auditor_mao_token(client: AsyncClient):
    return await get_token_for(client, "auditor@mao.test")
