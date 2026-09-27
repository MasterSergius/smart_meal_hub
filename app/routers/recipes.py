import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.recipe import RecipeOut, RecipeCreate, RecipeSearchOut
from app.services import recipe as recipe_service
from app.services.recipe import _to_out

router = APIRouter()


@router.post("", response_model=RecipeOut, status_code=status.HTTP_201_CREATED)
async def add_recipe(
    data: RecipeCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecipeOut:
    recipe = await recipe_service.create_recipe(db, data, current_user)
    return _to_out(recipe)


@router.get("/search", response_model=RecipeSearchOut)
async def search_recipes(
    q: str | None = Query(None),
    diet_tags: str | None = Query(None),
    cuisine: str | None = Query(None),
    max_total_time: int | None = Query(None),
    min_rating: float | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> RecipeSearchOut:
    from app.schemas.recipe import RecipeSearchParams
    params = RecipeSearchParams(
        q=q, diet_tags=diet_tags, cuisine=cuisine,
        max_total_time=max_total_time, min_rating=min_rating,
        page=page, limit=limit,
    )
    return await recipe_service.search_recipes(db, params)


@router.get("/{recipe_id}", response_model=RecipeOut)
async def get_recipe(
    recipe_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> RecipeOut:
    recipe = await recipe_service.get_recipe(db, recipe_id)
    return _to_out(recipe)


@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recipe(
    recipe_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await recipe_service.delete_recipe(db, recipe_id, current_user)
