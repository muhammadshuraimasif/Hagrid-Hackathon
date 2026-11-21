import asyncio
import logging
from sqlalchemy import select
from api.database import AsyncSessionLocal, init_db
from api.models import Tenant, User
from api.security import hash_password

logger = logging.getLogger(__name__)

SEED_TENANTS = [
    {
        "id": "tenant-prd",
        "code": "prd",
        "name": "Provincial Relief Department",
    },
    {
        "id": "tenant-mao",
        "code": "mao",
        "name": "Municipal Aid Office",
    },
]

ROLES = ["citizen", "helper", "officer", "admin", "auditor"]
DEFAULT_PASSWORD = "Demo@12345"

async def seed_data():
    """Idempotently seed tenants and test users."""
    await init_db()
    pwd_hash = hash_password(DEFAULT_PASSWORD)

    async with AsyncSessionLocal() as session:
        # Seed Tenants
        for t_info in SEED_TENANTS:
            res = await session.execute(select(Tenant).where(Tenant.code == t_info["code"]))
            existing_tenant = res.scalars().first()
            if not existing_tenant:
                tenant = Tenant(
                    id=t_info["id"],
                    code=t_info["code"],
                    name=t_info["name"],
                    is_active=True,
                )
                session.add(tenant)
                await session.flush()
                logger.info(f"Seeded tenant: {t_info['code']}")
            else:
                t_info["id"] = existing_tenant.id

        # Seed Users
        for t_info in SEED_TENANTS:
            tenant_id = t_info["id"]
            code = t_info["code"]
            for role in ROLES:
                email = f"{role}@{code}.test"
                user_res = await session.execute(select(User).where(User.email == email))
                existing_user = user_res.scalars().first()
                if not existing_user:
                    user = User(
                        tenant_id=tenant_id,
                        email=email,
                        password_hash=pwd_hash,
                        role=role,
                        language="ur",
                        is_active=True,
                    )
                    session.add(user)
                    logger.info(f"Seeded user: {email} ({role})")

        await session.commit()
        logger.info("Database seeding completed idempotently.")

if __name__ == "__main__":
    asyncio.run(seed_data())
