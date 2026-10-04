import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ForbiddenError, NotFoundError
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
    """Create or replace ``current_user``'s rating of a recipe and refresh its aggregate.

    Each user has at most one rating per recipe (unique ``recipe_id, user_id``); rating
    again overwrites the score and comment. Two steps make this safe under concurrent
    requests:

    1. **Row lock on the recipe** (``SELECT ... FOR UPDATE``). Every rating write for
       the same recipe waits here until the previous transaction commits. Without it,
       two users rating at the same moment would each recompute the average without
       seeing the other's uncommitted rating, and the last commit would store a stale
       ``avg_rating`` / ``rating_count``.
    2. **Atomic upsert** (``INSERT ... ON CONFLICT DO UPDATE``). The database decides
       between insert and update in one statement, so a double-submitted first rating
       cannot fail the unique constraint, as the old SELECT-then-INSERT could.

    The lock is held until ``commit``, so the aggregate is computed from a consistent
    set of ratings.

    Raises:
        NotFoundError: no recipe with that id.
        ForbiddenError: the caller is the recipe's author.
    """
    recipe = await db.scalar(
        select(Recipe)
        .where(Recipe.id == recipe_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if recipe is None:
        raise NotFoundError("Recipe not found")

    if recipe.author_id == current_user.id:
        raise ForbiddenError("Cannot rate your own recipe")

    insert_stmt = pg_insert(Rating).values(
        recipe_id=recipe_id,
        user_id=current_user.id,
        score=data.score,
        comment=data.comment,
    )
    upsert_stmt = insert_stmt.on_conflict_do_update(
        constraint="uq_rating_recipe_user",
        set_={"score": insert_stmt.excluded.score, "comment": insert_stmt.excluded.comment},
    ).returning(Rating)
    # populate_existing: if this rating is already in the session (an earlier
    # request on the same session), overwrite it with the row RETURNING gives back.
    rating = await db.scalar(upsert_stmt, execution_options={"populate_existing": True})
    assert rating is not None  # RETURNING always yields the inserted/updated row

    avg, count = await _recalculate_avg(db, recipe_id)
    recipe.avg_rating = avg
    recipe.rating_count = count

    await db.commit()

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
    """Compute the average score and number of ratings for a recipe.

    Runs ``SELECT avg(score), count(id)`` inside the caller's transaction, so it sees
    the rating that was just written. The average is rounded to 2 decimals to match
    the ``NUMERIC(3, 2)`` column, so the API returns exactly what is stored. A recipe
    with no ratings gives ``(0.0, 0)``.
    """
    result = await db.execute(
        select(func.avg(Rating.score), func.count(Rating.id)).where(Rating.recipe_id == recipe_id)
    )
    avg, count = result.one()
    return (round(float(avg), 2) if avg is not None else 0.0), (count or 0)
