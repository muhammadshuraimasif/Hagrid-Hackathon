import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy import event, text
from api.config import settings

logger = logging.getLogger(__name__)

# Normalize DATABASE_URL for async drivers if necessary
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif db_url.startswith("sqlite://") and not db_url.startswith("sqlite+aiosqlite://"):
    db_url = db_url.replace("sqlite://", "sqlite+aiosqlite://", 1)

is_sqlite = "sqlite" in db_url
if not is_sqlite and "prepared_statement_cache_size" not in db_url:
    db_url += ("&" if "?" in db_url else "?") + "prepared_statement_cache_size=0"

connect_args = {}
engine_kwargs = {}
if is_sqlite:
    connect_args["check_same_thread"] = False
else:
    # Supabase/pgBouncer poolers do not support asyncpg's prepared-statement cache.
    connect_args["statement_cache_size"] = 0
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_size"] = 3
    engine_kwargs["max_overflow"] = 2
    engine_kwargs["pool_recycle"] = 300

engine = create_async_engine(
    db_url,
    echo=False,
    connect_args=connect_args,
    future=True,
    **engine_kwargs,
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

SQLITE_RULESET_TRIGGERS = [
    """CREATE TRIGGER IF NOT EXISTS rule_sets_block_published_update
BEFORE UPDATE ON rule_sets
BEGIN
    SELECT CASE
        WHEN OLD.status = 'published' AND (
            NEW.status NOT IN ('published', 'retired') OR
            NEW.definition != OLD.definition OR
            NEW.content_hash != OLD.content_hash OR
            NEW.version != OLD.version
        )
        THEN RAISE(ABORT, 'Published rule sets are immutable')
        WHEN OLD.status = 'retired'
        THEN RAISE(ABORT, 'Retired rule sets are immutable')
    END;
END;""",
    """CREATE TRIGGER IF NOT EXISTS rule_sets_block_published_delete
BEFORE DELETE ON rule_sets
BEGIN
    SELECT CASE
        WHEN OLD.status IN ('published', 'retired')
        THEN RAISE(ABORT, 'Published rule sets cannot be deleted')
    END;
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

POSTGRES_RULESET_TRIGGERS = """
CREATE OR REPLACE FUNCTION block_rule_sets_modification()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status = 'published' AND (
        NEW.status NOT IN ('published', 'retired') OR
        NEW.definition::text != OLD.definition::text OR
        NEW.content_hash != OLD.content_hash OR
        NEW.version != OLD.version
    ) THEN
        RAISE EXCEPTION 'Published rule sets are immutable';
    END IF;
    IF OLD.status = 'retired' THEN
        RAISE EXCEPTION 'Retired rule sets are immutable';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION block_rule_sets_deletion()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IN ('published', 'retired') THEN
        RAISE EXCEPTION 'Published rule sets cannot be deleted';
    END IF;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS rule_sets_block_published_update ON rule_sets;
CREATE TRIGGER rule_sets_block_published_update
BEFORE UPDATE ON rule_sets
FOR EACH ROW EXECUTE FUNCTION block_rule_sets_modification();

DROP TRIGGER IF EXISTS rule_sets_block_published_delete ON rule_sets;
CREATE TRIGGER rule_sets_block_published_delete
BEFORE DELETE ON rule_sets
FOR EACH ROW EXECUTE FUNCTION block_rule_sets_deletion();
"""

async def init_db():
    """Initializes tables and WAL mode + triggers for SQLite or Postgres."""
    async with engine.begin() as conn:
        if is_sqlite:
            await conn.execute(text("PRAGMA journal_mode = WAL;"))
            await conn.execute(text("PRAGMA foreign_keys = ON;"))
        await conn.run_sync(Base.metadata.create_all)
        
        # Install triggers
        if is_sqlite:
            for trigger_stmt in SQLITE_AUDIT_TRIGGERS + SQLITE_RULESET_TRIGGERS:
                await conn.execute(text(trigger_stmt))
        else:
            await conn.execute(text(POSTGRES_AUDIT_TRIGGERS))
            await conn.execute(text(POSTGRES_RULESET_TRIGGERS))

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
