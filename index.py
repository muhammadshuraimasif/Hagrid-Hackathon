"""
Vercel serverless entrypoint for the Amaanat FastAPI backend (PROTOTYPE ONLY).

- The mock NADRA / Raast / Telco rails run in-process (MOCKS_INPROCESS=true), so no
  second server is needed.
- DB init + seeding runs on the first request of each cold instance, guarded by a lock,
  in case the platform does not deliver ASGI lifespan events.
"""
import asyncio
import logging
import os

os.environ.setdefault("MOCKS_INPROCESS", "true")

from api.main import app as fastapi_app  # noqa: E402
from api.config import settings  # noqa: E402
from api.database import init_db  # noqa: E402
from api.seed import seed_data  # noqa: E402

logger = logging.getLogger("amaanat-vercel")

_ready = False
_lock = asyncio.Lock()


async def _ensure_ready():
    global _ready
    if _ready:
        return
    async with _lock:
        if _ready:
            return
        settings.validate_production_secrets()
        await init_db()
        try:
            await seed_data()
        except Exception as exc:
            logger.warning(f"Seeding skipped (likely already seeded): {exc}")
        _ready = True


async def app(scope, receive, send):
    if scope["type"] == "lifespan":
        # Delegate lifespan to FastAPI (it also runs init/seed idempotently)
        await fastapi_app(scope, receive, send)
        return
    if scope["type"] in ("http", "websocket"):
        await _ensure_ready()
    await fastapi_app(scope, receive, send)
