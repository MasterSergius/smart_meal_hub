import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.rating import RatingCreate, RatingOut
from app.services import rating as rating_service

router = APIRouter()


@router.post("/{recipe_id}/ratings", response_model=RatingOut, status_code=status.HTTP_200_OK)
async def rate_recipe(
    recipe_id: uuid.UUID,
    data: RatingCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RatingOut:
    return await rating_service.upsert_rating(db, recipe_id, data, current_user)
