from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import DEFAULT_HOUSEHOLD_SIZE
from app.models.preferences import UserPreferences
from app.models.user import User
from app.schemas.preferences import PreferencesIn, PreferencesOut


async def get_preferences(db: AsyncSession, user: User) -> PreferencesOut:
    """Return the user's saved preferences, or the PREF-1 defaults if there are none."""
    prefs = await db.get(UserPreferences, user.id)
    if prefs is None:
        return PreferencesOut(
            diets=[],
            excluded_ingredients=[],
            household_size=DEFAULT_HOUSEHOLD_SIZE,
            region=None,
            updated_at=None,
        )
    return PreferencesOut.model_validate(prefs)


async def put_preferences(db: AsyncSession, user: User, data: PreferencesIn) -> PreferencesOut:
    """Replace the user's preferences (PREF-5) with an atomic upsert.

    ``INSERT ... ON CONFLICT DO UPDATE`` avoids a race between two first saves of
    the same user. Values are already normalised by ``PreferencesIn``.
    """
    values = {
        "diets": list(data.diets),
        "excluded_ingredients": list(data.excluded_ingredients),
        "household_size": data.household_size,
        "region": data.region,
    }
    stmt = insert(UserPreferences).values(user_id=user.id, **values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[UserPreferences.user_id],
        set_={**values, "updated_at": func.now()},
    )
    await db.execute(stmt)
    await db.commit()
    result = await db.execute(
        select(UserPreferences)
        .where(UserPreferences.user_id == user.id)
        .execution_options(populate_existing=True)
    )
    return PreferencesOut.model_validate(result.scalar_one())
