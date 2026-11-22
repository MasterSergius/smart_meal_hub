import uuid
from datetime import UTC, date, datetime, timedelta

from pydantic import BaseModel, Field, field_validator

from app.schemas.preferences import Diets, ExcludedIngredients, HouseholdSize, Region
from app.schemas.recipe import IngredientItem

MAX_SEED = 2**63 - 1  # fits Postgres BIGINT
START_DATE_PAST_DAYS = 7
START_DATE_FUTURE_DAYS = 365

# Alias so ``MenuSlotOut`` can have a field named ``date`` without shadowing the type.
CalendarDate = date


class MenuGenerateIn(BaseModel):
    """Request body for ``POST /menus/generate`` (spec v0.2.0 §6.5).

    Every field is optional. A missing or ``null`` field comes from the user's
    preferences, except that an explicit ``"region": null`` means "no region" (no
    seasonal scoring). Values given here apply to this menu only and are not saved
    to preferences.
    """

    start_date: date | None = None
    servings: HouseholdSize | None = None
    diets: Diets | None = None
    excluded_ingredients: ExcludedIngredients | None = None
    region: Region | None = None
    seed: int | None = Field(default=None, ge=0, le=MAX_SEED)

    @field_validator("start_date")
    @classmethod
    def start_date_in_range(cls, v: date | None) -> date | None:
        """``start_date`` must be within one week back and one year ahead of today (UTC)."""
        if v is None:
            return v
        today = datetime.now(UTC).date()
        if not today - timedelta(days=START_DATE_PAST_DAYS) <= v <= today + timedelta(
            days=START_DATE_FUTURE_DAYS
        ):
            raise ValueError(
                f"start_date must be between {START_DATE_PAST_DAYS} days ago "
                f"and {START_DATE_FUTURE_DAYS} days ahead"
            )
        return v


class MenuPatchIn(BaseModel):
    """Request body for ``PATCH /menus/{id}``: change the number of people (FR-1.3)."""

    servings: HouseholdSize


class SlotReplaceIn(BaseModel):
    """Optional body of the replace endpoint; ``recipe_id`` picks a recipe manually (MENU-6)."""

    recipe_id: uuid.UUID | None = None


class MenuRecipeOut(BaseModel):
    """The recipe in a slot, in short; the full recipe is at ``GET /recipes/{id}``."""

    id: uuid.UUID
    title: str
    cuisine: str | None
    servings: int
    total_time_min: int | None
    avg_rating: float | None
    image_url: str | None


class MenuSlotOut(BaseModel):
    """One meal of a menu with ingredients scaled to the menu's servings (SCALE-1)."""

    day: int
    date: CalendarDate
    meal_type: str
    recipe: MenuRecipeOut | None
    scaled_ingredients: list[IngredientItem]
    warnings: list[str]


class MenuOut(BaseModel):
    """A full menu: 21 slots ordered by day, then breakfast, lunch, dinner.

    ``warnings`` is computed on every read (MENU-9).
    """

    id: uuid.UUID
    start_date: date
    servings: int
    diets: list[str]
    excluded_ingredients: list[str]
    region: str | None
    seed: int
    slots: list[MenuSlotOut]
    warnings: list[str]
    created_at: datetime
    updated_at: datetime


class MenuSummaryOut(BaseModel):
    """A menu in ``GET /menus``; ``empty_slots`` counts slots without a recipe."""

    id: uuid.UUID
    start_date: date
    servings: int
    empty_slots: int
    created_at: datetime


class MenuListParams(BaseModel):
    """Query parameters of ``GET /menus`` (MENU-2)."""

    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)


class MenuListOut(BaseModel):
    """One page of the caller's menus plus ``total`` across all pages."""

    total: int
    page: int
    limit: int
    items: list[MenuSummaryOut]
