import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.rating import Rating
    from app.models.user import User


class Recipe(Base):
    """A recipe authored by one ``User``.

    ``ingredients`` and ``steps`` are JSONB, ``diet_tags`` is a Postgres text array.
    ``avg_rating`` / ``rating_count`` are a denormalised cache of ``recipe_ratings``,
    kept in sync by ``app.services.rating.upsert_rating`` so search can filter and sort
    on them without aggregating.
    """

    __tablename__ = "recipes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    ingredients: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    # [{"name": str, "amount": float, "unit": str}, ...]
    steps: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    # ["Step 1 text", "Step 2 text", ...]
    diet_tags: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)))
    cuisine: Mapped[str | None] = mapped_column(String(100))
    servings: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=2)
    prep_time_min: Mapped[int | None] = mapped_column(SmallInteger)
    cook_time_min: Mapped[int | None] = mapped_column(SmallInteger)
    image_url: Mapped[str | None] = mapped_column(Text)

    avg_rating: Mapped[float | None] = mapped_column(Numeric(3, 2))
    rating_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    author: Mapped["User"] = relationship(back_populates="recipes")
    ratings: Mapped[list["Rating"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan"
    )
