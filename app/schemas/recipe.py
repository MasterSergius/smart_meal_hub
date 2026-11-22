import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.constants import DEFAULT_MEAL_TYPES, MEAL_TYPES, MealType
from app.services.matching import normalize_name

# Upper bounds below mirror the DB column types (String(n), SmallInteger) so bad input
# is rejected with a 422 by validation instead of failing in Postgres with a 500.
MAX_SERVINGS = 100
MAX_TIME_MIN = 10_080  # one week; also well inside SmallInteger's 32767 limit

DietTag = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


def normalize_diet_tags(tags: list[str]) -> list[str]:
    """C-1: lowercase, collapse whitespace and drop duplicates, keeping first-seen order."""
    return list(dict.fromkeys(normalize_name(t) for t in tags))


def canonical_meal_types(values: list[MealType]) -> list[MealType]:
    """Distinct meal types in breakfast, lunch, dinner order."""
    return [m for m in MEAL_TYPES if m in values]


class IngredientItem(BaseModel):
    """One ingredient line, e.g. ``{"name": "butter", "amount": 50, "unit": "g"}``.

    Stored inside the ``recipes.ingredients`` JSONB column, so there is no DB-level
    length limit; the bounds here keep the payload sane.
    """

    name: str = Field(min_length=1, max_length=200)
    amount: float = Field(ge=0)
    unit: str = Field(max_length=50)


class RecipeCreate(BaseModel):
    """Request body for ``POST /recipes``.

    Field limits match the ``recipes`` table: ``title`` is ``String(200)``, ``cuisine``
    ``String(100)``, each diet tag ``String(50)`` and the counts are ``SmallInteger``.
    """

    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    ingredients: list[IngredientItem]
    steps: list[str]
    diet_tags: list[DietTag] | None = None
    meal_types: list[MealType] = Field(default_factory=lambda: list(DEFAULT_MEAL_TYPES))  # REC-1
    cuisine: str | None = Field(default=None, max_length=100)
    servings: int = Field(default=2, ge=1, le=MAX_SERVINGS)
    prep_time_min: int | None = Field(default=None, ge=0, le=MAX_TIME_MIN)
    cook_time_min: int | None = Field(default=None, ge=0, le=MAX_TIME_MIN)
    image_url: str | None = None

    @field_validator("ingredients")
    @classmethod
    def at_least_one_ingredient(cls, v: list[IngredientItem]) -> list[IngredientItem]:
        """Reject a recipe with an empty ingredient list."""
        if not v:
            raise ValueError("at least one ingredient is required")
        return v

    @field_validator("diet_tags")
    @classmethod
    def normalize_tags(cls, v: list[str] | None) -> list[str] | None:
        """Store diet tags lowercased and de-duplicated (C-1)."""
        return normalize_diet_tags(v) if v is not None else None

    @field_validator("meal_types")
    @classmethod
    def at_least_one_meal_type(cls, v: list[MealType]) -> list[MealType]:
        """REC-1: 1-3 distinct meal types, stored in canonical order."""
        if not v:
            raise ValueError("at least one meal type is required")
        return canonical_meal_types(v)

    @field_validator("steps")
    @classmethod
    def at_least_one_step(cls, v: list[str]) -> list[str]:
        """Reject a recipe with no preparation steps."""
        if not v:
            raise ValueError("at least one step is required")
        return v


class AuthorOut(BaseModel):
    """Minimal public view of a recipe's author, embedded in ``RecipeOut``."""

    id: uuid.UUID
    display_name: str

    model_config = {"from_attributes": True}


class RecipeOut(BaseModel):
    """Full recipe as returned by the API.

    ``total_time_min`` is not a DB column: it is computed as prep + cook by
    ``app.services.recipe.to_recipe_out``.
    """

    id: uuid.UUID
    author: AuthorOut
    title: str
    description: str | None
    ingredients: list[IngredientItem]
    steps: list[str]
    diet_tags: list[str] | None
    meal_types: list[str]
    cuisine: str | None
    servings: int
    prep_time_min: int | None
    cook_time_min: int | None
    total_time_min: int | None
    image_url: str | None
    avg_rating: float | None
    rating_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RecipeSearchParams(BaseModel):
    """Query parameters of ``GET /recipes/search``, validated as one model.

    FastAPI (0.115+) maps each field to a query parameter when the model is declared
    as ``Annotated[RecipeSearchParams, Query()]``. All filters are optional and are
    combined with AND.
    """

    q: str | None = Field(default=None, max_length=200)
    diet_tags: str | None = Field(default=None, max_length=500)  # comma-separated, AND logic
    meal_type: MealType | None = None  # REC-3
    cuisine: str | None = Field(default=None, max_length=100)
    max_total_time: int | None = Field(default=None, ge=0)
    min_rating: float | None = Field(default=None, ge=0, le=5)
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)


class RecipeSearchOut(BaseModel):
    """One page of search results plus ``total``, the match count across all pages."""

    total: int
    page: int
    limit: int
    items: list[RecipeOut]
