"""
Test fixtures and helpers for KiranaBot tests.
Uses a real PostgreSQL test database (test_kiranadb).

Pure unit tests (test_gst.py) run without any Postgres dependency.
DB integration tests are auto-skipped when Postgres is not reachable.
"""
import os
import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import create_engine, text

# Set test env before importing app modules
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("WEBHOOK_URL", "https://test.example.com")
os.environ.setdefault("APP_ENV", "test")

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL_SYNC",
    "postgresql://kirana:kirana_pass@localhost:5432/test_kiranadb",
)
TEST_DB_URL_ASYNC = TEST_DB_URL.replace("postgresql://", "postgresql+asyncpg://")
TEST_SHOP_ID = "00000000-0000-0000-0000-000000000099"

os.environ["DATABASE_URL"] = TEST_DB_URL_ASYNC
os.environ["DATABASE_URL_SYNC"] = TEST_DB_URL
os.environ["SHOP_ID"] = TEST_SHOP_ID


def _postgres_is_available() -> bool:
    """Quick check if Postgres is reachable — used to skip DB tests gracefully."""
    try:
        engine = create_engine(TEST_DB_URL, connect_args={"connect_timeout": 2})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


# Cache so we only check once per session
_PG_AVAILABLE = _postgres_is_available()

requires_postgres = pytest.mark.skipif(
    not _PG_AVAILABLE,
    reason="PostgreSQL not reachable — skipping DB integration tests",
)


@pytest.fixture(scope="session")
def setup_test_db():
    """Create test database schema. Only runs when Postgres is available."""
    if not _PG_AVAILABLE:
        pytest.skip("PostgreSQL not available")

    from app.models import Base
    engine = create_engine(TEST_DB_URL, echo=False)
    Base.metadata.create_all(engine)
    engine.dispose()


@pytest_asyncio.fixture
async def db_session(setup_test_db):
    """Fresh async session for each test."""
    engine = create_async_engine(TEST_DB_URL_ASYNC, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        yield session
        await session.rollback()

    await engine.dispose()


@pytest.fixture(autouse=True)
def clean_db(request):
    """
    Truncate all tables before each DB integration test.
    No-op for pure unit tests (e.g. test_gst.py) and when Postgres is unavailable.

    Important: do NOT declare setup_test_db as a parameter here —
    that would force setup_test_db (and its pytest.skip call) to run
    for every test, including pure sync unit tests like test_gst.py.
    Instead, call the DB setup inside the body only when needed.
    """
    is_async = request.node.get_closest_marker("asyncio") is not None
    uses_db = "db_session" in request.fixturenames

    # Pure sync unit tests (e.g. TestComputeGSTLine) — nothing to clean
    if not (is_async or uses_db):
        return

    # DB integration tests — skip gracefully if Postgres isn't reachable
    if not _PG_AVAILABLE:
        pytest.skip("PostgreSQL not reachable — skipping DB integration tests")
        return

    from app.models import Base
    engine = create_engine(TEST_DB_URL, echo=False)
    Base.metadata.create_all(engine)
    try:
        with engine.connect() as conn:
            for table in [
                "processed_telegram_updates", "preferences", "credit_transactions",
                "bill_items", "bills", "stock_movements", "customers", "products", "shops"
            ]:
                conn.execute(text(f"DELETE FROM {table}"))
            conn.commit()

        with engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO shops (id, name, owner_name, gstin, address) "
                    "VALUES (:id, :name, :owner, :gstin, :addr)"
                ),
                {
                    "id": TEST_SHOP_ID,
                    "name": "Test Supermarket Store",
                    "owner": "Test Owner",
                    "gstin": "27AABCU9603R1ZX",
                    "addr": "123 Test Street",
                },
            )
            conn.commit()
    finally:
        engine.dispose()


async def create_test_product(
    name: str = "Tata Salt",
    brand: str = "Tata",
    unit: str = "kg",
    gst_slab: float = 5.0,
    cost_price: float = 18.0,
    sell_price: float = 22.0,
    qty_on_hand: float = 100.0,
    reorder_level: float = 10.0,
) -> dict:
    """Helper to create a test product via the tool."""
    from app.tools.inventory import add_product
    result = await add_product(
        name=name,
        brand=brand,
        unit=unit,
        gst_slab=gst_slab,
        cost_price=cost_price,
        sell_price=sell_price,
        initial_qty=qty_on_hand,
        reorder_level=reorder_level,
    )
    assert result["ok"], f"create_test_product failed: {result}"
    return result["data"]["product"]


async def create_test_customer(name: str = "Test Customer", phone: str = "9876543210") -> dict:
    """Helper to create a test customer."""
    from app.tools.credit import add_customer
    result = await add_customer(name=name, phone=phone)
    assert result["ok"], f"create_test_customer failed: {result}"
    return result["data"]["customer"]
