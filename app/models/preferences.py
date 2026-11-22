import uuid
from datetime import datetime

from sqlalchemy import CHAR, CheckConstraint, DateTime, ForeignKey, SmallInteger, String, func, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.constants import DEFAULT_HOUSEHOLD_SIZE
from app.database import Base


class UserPreferences(Base):
    """A user's planning preferences (spec v0.2.0 §3.2); at most one row per user.

    The row is created on the first ``PUT /users/me/preferences``; until then the
    defaults from PREF-1 apply. Values are stored normalised (lowercase names,
    uppercase region) by the request schema.
    """

    __tablename__ = "user_preferences"
    __table_args__ = (
        CheckConstraint("household_size BETWEEN 1 AND 20", name="ck_user_preferences_household"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    diets: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)), nullable=False, server_default=text("'{}'")
    )
    excluded_ingredients: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), nullable=False, server_default=text("'{}'")
    )
    household_size: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=DEFAULT_HOUSEHOLD_SIZE, server_default=text("2")
    )
    region: Mapped[str | None] = mapped_column(CHAR(2))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
