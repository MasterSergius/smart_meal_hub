import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CHAR,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.recipe import Recipe


class Menu(Base):
    """A user's 7-day menu (spec v0.2.0 §3.4).

    ``diets``, ``excluded_ingredients`` and ``region`` are a snapshot of the rules the
    menu was generated with, so later replacements follow the same rules even if
    the user's preferences change. ``seed`` reproduces the generated menu (GEN-9).
    """

    __tablename__ = "menus"
    __table_args__ = (CheckConstraint("servings BETWEEN 1 AND 20", name="ck_menus_servings"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    servings: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    diets: Mapped[list[str]] = mapped_column(ARRAY(String(50)), nullable=False)
    excluded_ingredients: Mapped[list[str]] = mapped_column(ARRAY(String(100)), nullable=False)
    region: Mapped[str | None] = mapped_column(CHAR(2))
    seed: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    slots: Mapped[list["MenuSlot"]] = relationship(
        back_populates="menu",
        cascade="all, delete-orphan",
        order_by="MenuSlot.day",  # meal order within a day is applied when serialising
    )


class MenuSlot(Base):
    """One meal of a menu: 7 days × breakfast/lunch/dinner = 21 rows per menu (§3.5).

    ``recipe_id`` is ``NULL`` for an empty slot: nothing matched at generation time
    (GEN-13) or the recipe was deleted later (MENU-7, ``ON DELETE SET NULL``).
    """

    __tablename__ = "menu_slots"
    __table_args__ = (
        UniqueConstraint("menu_id", "day", "meal_type", name="uq_menu_slots_menu_day_meal"),
        CheckConstraint("day BETWEEN 1 AND 7", name="ck_menu_slots_day"),
        CheckConstraint(
            "meal_type IN ('breakfast', 'lunch', 'dinner')", name="ck_menu_slots_meal_type"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    menu_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("menus.id", ondelete="CASCADE"), nullable=False
    )
    day: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    meal_type: Mapped[str] = mapped_column(String(10), nullable=False)
    recipe_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recipes.id", ondelete="SET NULL")
    )

    menu: Mapped[Menu] = relationship(back_populates="slots")
    recipe: Mapped["Recipe | None"] = relationship()
