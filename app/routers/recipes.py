import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.recipe import Recipe
from app.models.user import User
from app.schemas.recipe import RecipeCreate, RecipeOut, RecipeSearchOut, RecipeSearchParams
from app.services import recipe as recipe_service

router = APIRouter()


@router.post("", response_model=RecipeOut, status_code=status.HTTP_201_CREATED)
async def add_recipe(
    data: RecipeCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Recipe:
    ...


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
    ...


@router.get("/{recipe_id}", response_model=RecipeOut)
async def get_recipe(
    recipe_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Recipe:
    ...


@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recipe(
    recipe_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    ...
