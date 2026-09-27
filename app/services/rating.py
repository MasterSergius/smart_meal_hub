import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rating import Rating
from app.models.recipe import Recipe
from app.models.user import User
from app.schemas.rating import RatingCreate, RatingOut


async def upsert_rating(
    db: AsyncSession,
    recipe_id: uuid.UUID,
    data: RatingCreate,
    current_user: User,
) -> RatingOut:
    # verify recipe exists
    result = await db.execute(select(Recipe).where(Recipe.id == recipe_id))
    recipe = result.scalar_one_or_none()
    if not recipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")

    if recipe.author_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot rate your own recipe")

    # upsert rating
    result = await db.execute(
        select(Rating).where(Rating.recipe_id == recipe_id, Rating.user_id == current_user.id)
    )
    rating = result.scalar_one_or_none()
    if rating:
        rating.score = data.score
        rating.comment = data.comment
    else:
        rating = Rating(
            recipe_id=recipe_id,
            user_id=current_user.id,
            score=data.score,
            comment=data.comment,
        )
        db.add(rating)

    await db.flush()  # write rating before recalculating

    avg, count = await _recalculate_avg(db, recipe_id)
    recipe.avg_rating = avg
    recipe.rating_count = count

    await db.commit()
    await db.refresh(rating)

    return RatingOut(
        id=rating.id,
        recipe_id=rating.recipe_id,
        score=rating.score,
        comment=rating.comment,
        created_at=rating.created_at,
        recipe_avg_rating=avg,
        recipe_rating_count=count,
    )


async def _recalculate_avg(db: AsyncSession, recipe_id: uuid.UUID) -> tuple[float, int]:
    result = await db.execute(
        select(func.avg(Rating.score), func.count(Rating.id)).where(Rating.recipe_id == recipe_id)
    )
    avg, count = result.one()
    return (float(avg) if avg is not None else 0.0), (count or 0)
