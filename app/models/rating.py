import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.recipe import Recipe
    from app.models.user import User


class Rating(Base):
    """One user's 1-5 score (and optional comment) for one recipe.

    ``user_id`` is the rater, not the recipe's author (that is ``Recipe.author_id``).
    The unique ``(recipe_id, user_id)`` constraint allows one rating per user per
    recipe, and the rating upsert uses that constraint as its ON CONFLICT target.
    """

    __tablename__ = "recipe_ratings"
    __table_args__ = (
        UniqueConstraint("recipe_id", "user_id", name="uq_rating_recipe_user"),
        CheckConstraint("score BETWEEN 1 AND 5", name="ck_rating_score_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    recipe_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    recipe: Mapped["Recipe"] = relationship(back_populates="ratings")
    user: Mapped["User"] = relationship(back_populates="ratings")
