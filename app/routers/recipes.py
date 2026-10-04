import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.dependencies import CurrentUser, DbSession
from app.schemas.recipe import RecipeCreate, RecipeOut, RecipeSearchOut, RecipeSearchParams
from app.services import recipe as recipe_service

router = APIRouter()


@router.post("", response_model=RecipeOut, status_code=status.HTTP_201_CREATED)
async def add_recipe(data: RecipeCreate, current_user: CurrentUser, db: DbSession) -> RecipeOut:
    """``POST /recipes``: create a recipe owned by the authenticated user (201).

    Returns 422 if the body fails ``RecipeCreate`` validation, and 403 without a token.
    """
    recipe = await recipe_service.create_recipe(db, data, current_user)
    return recipe_service.to_recipe_out(recipe)


@router.get("/search", response_model=RecipeSearchOut)
async def search_recipes(
    params: Annotated[RecipeSearchParams, Query()], db: DbSession
) -> RecipeSearchOut:
    """``GET /recipes/search``: public search with optional filters and pagination.

    Every field of ``RecipeSearchParams`` (``q``, ``diet_tags``, ``cuisine``,
    ``max_total_time``, ``min_rating``, ``page``, ``limit``) is a query parameter and
    is validated there; out-of-range values return 422. Declared before
    ``/{recipe_id}`` so that "search" is not parsed as a recipe id.
    """
    return await recipe_service.search_recipes(db, params)


@router.get("/{recipe_id}", response_model=RecipeOut)
async def get_recipe(recipe_id: uuid.UUID, db: DbSession) -> RecipeOut:
    """``GET /recipes/{recipe_id}``: fetch one recipe (public). Returns 404 if it doesn't exist."""
    recipe = await recipe_service.get_recipe(db, recipe_id)
    return recipe_service.to_recipe_out(recipe)


@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recipe(recipe_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> None:
    """``DELETE /recipes/{recipe_id}``: delete a recipe and its ratings (author only).

    Returns 204 on success, 404 if it doesn't exist, and 403 for anyone but the author.
    """
    await recipe_service.delete_recipe(db, recipe_id, current_user)
