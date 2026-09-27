import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rating import Rating
from app.models.user import User
from app.schemas.rating import RatingCreate, RatingOut


async def upsert_rating(
    db: AsyncSession,
    recipe_id: uuid.UUID,
    data: RatingCreate,
    current_user: User,
) -> RatingOut:
    """
    Insert or update the user's rating for a recipe, then recalculate
    avg_rating and rating_count on the recipe row atomically.

    Raises:
        404 if the recipe does not exist.
        403 if current_user is the recipe author.
    """
    ...


def _recalculate_avg(db: AsyncSession, recipe_id: uuid.UUID) -> tuple[float, int]:
    """
    Recompute AVG(score) and COUNT(*) from recipe_ratings.
    Called within the same transaction as the rating upsert.
    """
    ...
