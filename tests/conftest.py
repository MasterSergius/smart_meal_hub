import asyncio
import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://smarthub:smarthub@localhost:5432/smarthub_test"
)
os.environ.setdefault("JWT_SECRET", "test-secret-key-not-for-production")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = os.environ["DATABASE_URL"]
test_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


def pytest_configure(config: pytest.Config) -> None:
    """Drop and recreate all tables once before the test run (sync hook, no event loop issues)."""

    async def _setup() -> None:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_setup())


@pytest.fixture
async def db() -> AsyncSession:
    """A DB session for one test, shared by every request that test makes via ``client``."""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db: AsyncSession) -> AsyncClient:
    """HTTP client that calls the app in-process (no server) with ``get_db`` overridden.

    Every request in the test gets the same ``db`` session, so data created by one
    request is visible to the next.
    """

    async def override_get_db() -> AsyncSession:
        """Yield the test's session instead of opening a new one per request."""
        yield db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
