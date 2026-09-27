import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recipe import Recipe
from app.models.user import User
from app.schemas.recipe import RecipeCreate, RecipeSearchOut, RecipeSearchParams


async def create_recipe(db: AsyncSession, data: RecipeCreate, author: User) -> Recipe:
    """Persist a new recipe and return it."""
    ...


async def get_recipe(db: AsyncSession, recipe_id: uuid.UUID) -> Recipe:
    """Return a recipe by ID with author eagerly loaded. Raises 404 if not found."""
    ...


async def delete_recipe(db: AsyncSession, recipe_id: uuid.UUID, current_user: User) -> None:
    """Delete a recipe. Raises 403 if current_user is not the author, 404 if not found."""
    ...


async def search_recipes(db: AsyncSession, params: RecipeSearchParams) -> RecipeSearchOut:
    """
    Filter and paginate recipes.

    Filtering logic:
    - q: full-text ILIKE match against title + description
    - diet_tags: recipe must contain ALL requested tags (AND semantics)
    - cuisine: case-insensitive equality
    - max_total_time: prep_time_min + cook_time_min <= value
    - min_rating: avg_rating >= value

    Ordering: avg_rating DESC NULLS LAST, created_at DESC
    """
    ...
