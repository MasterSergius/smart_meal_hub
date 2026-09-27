import uuid
from datetime import datetime

from pydantic import BaseModel, HttpUrl, field_validator


class IngredientItem(BaseModel):
    name: str
    amount: float
    unit: str


class RecipeCreate(BaseModel):
    title: str
    description: str | None = None
    ingredients: list[IngredientItem]
    steps: list[str]
    diet_tags: list[str] | None = None
    cuisine: str | None = None
    servings: int = 2
    prep_time_min: int | None = None
    cook_time_min: int | None = None
    image_url: str | None = None

    @field_validator("ingredients")
    @classmethod
    def at_least_one_ingredient(cls, v: list) -> list:
        if not v:
            raise ValueError("at least one ingredient is required")
        return v

    @field_validator("steps")
    @classmethod
    def at_least_one_step(cls, v: list) -> list:
        if not v:
            raise ValueError("at least one step is required")
        return v


class AuthorOut(BaseModel):
    id: uuid.UUID
    display_name: str

    model_config = {"from_attributes": True}


class RecipeOut(BaseModel):
    id: uuid.UUID
    author: AuthorOut
    title: str
    description: str | None
    ingredients: list[IngredientItem]
    steps: list[str]
    diet_tags: list[str] | None
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

    @classmethod
    def from_orm_with_total(cls, recipe: object) -> "RecipeOut":
        """Compute total_time_min from prep + cook before serialising."""
        ...


class RecipeSearchParams(BaseModel):
    q: str | None = None
    diet_tags: str | None = None   # comma-separated, AND logic
    cuisine: str | None = None
    max_total_time: int | None = None
    min_rating: float | None = None
    page: int = 1
    limit: int = 20

    @field_validator("limit")
    @classmethod
    def cap_limit(cls, v: int) -> int:
        return min(v, 100)


class RecipeSearchOut(BaseModel):
    total: int
    page: int
    limit: int
    items: list[RecipeOut]
