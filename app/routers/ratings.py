import uuid

from fastapi import APIRouter, status

from app.dependencies import CurrentUser, DbSession
from app.schemas.rating import RatingCreate, RatingOut
from app.services import rating as rating_service

router = APIRouter()


@router.post("/{recipe_id}/ratings", response_model=RatingOut, status_code=status.HTTP_200_OK)
async def rate_recipe(
    recipe_id: uuid.UUID, data: RatingCreate, current_user: CurrentUser, db: DbSession
) -> RatingOut:
    """``POST /recipes/{recipe_id}/ratings``: rate a recipe 1-5, or update your rating.

    The operation is an upsert, so it is idempotent per user and always returns 200
    with the recipe's new average and count. Returns 404 for an unknown recipe and 403
    when the author tries to rate their own recipe.
    """
    return await rating_service.upsert_rating(db, recipe_id, data, current_user)
