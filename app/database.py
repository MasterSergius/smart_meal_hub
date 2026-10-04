from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base for all ORM models; ``Base.metadata`` is what Alembic diffs against."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields one ``AsyncSession`` per request.

    The ``async with`` closes the session when the request finishes; if the request
    raised, any uncommitted transaction is rolled back. ``expire_on_commit=False``
    keeps loaded attributes readable after ``commit``, which is needed because
    reloading them lazily is not possible in async code.
    """
    async with AsyncSessionLocal() as session:
        yield session
