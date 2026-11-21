import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy import event, text
from api.config import settings

logger = logging.getLogger(__name__)

# Normalize DATABASE_URL for async drivers if necessary
db_url = settings.DATABASE_URL
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif db_url.startswith("sqlite://") and not db_url.startswith("sqlite+aiosqlite://"):
    db_url = db_url.replace("sqlite://", "sqlite+aiosqlite://", 1)

is_sqlite = "sqlite" in db_url

connect_args = {}
if is_sqlite:
    connect_args["check_same_thread"] = False

engine = create_async_engine(
    db_url,
    echo=False,
    connect_args=connect_args,
    future=True,
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()

SQLITE_AUDIT_TRIGGERS = [
    """CREATE TRIGGER IF NOT EXISTS audit_log_block_update
BEFORE UPDATE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log is insert-only');
END;""",
    """CREATE TRIGGER IF NOT EXISTS audit_log_block_delete
BEFORE DELETE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log is insert-only');
END;"""
]

POSTGRES_AUDIT_TRIGGERS = """
CREATE OR REPLACE FUNCTION block_audit_log_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is insert-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS audit_log_block_update ON audit_log;
CREATE TRIGGER audit_log_block_update
BEFORE UPDATE ON audit_log
FOR EACH ROW EXECUTE FUNCTION block_audit_log_modification();

DROP TRIGGER IF EXISTS audit_log_block_delete ON audit_log;
CREATE TRIGGER audit_log_block_delete
BEFORE DELETE ON audit_log
FOR EACH ROW EXECUTE FUNCTION block_audit_log_modification();
"""

async def init_db():
    """Initializes tables and WAL mode + triggers for SQLite or Postgres."""
    async with engine.begin() as conn:
        if is_sqlite:
            await conn.execute(text("PRAGMA journal_mode = WAL;"))
            await conn.execute(text("PRAGMA foreign_keys = ON;"))
        await conn.run_sync(Base.metadata.create_all)
        
        # Install audit insert-only triggers
        if is_sqlite:
            for trigger_stmt in SQLITE_AUDIT_TRIGGERS:
                await conn.execute(text(trigger_stmt))
        else:
            await conn.execute(text(POSTGRES_AUDIT_TRIGGERS))

async def get_db():
    """FastAPI DB dependency."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
