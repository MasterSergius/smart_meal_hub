from fastapi import APIRouter

from app.dependencies import CurrentUser, DbSession
from app.schemas.preferences import PreferencesIn, PreferencesOut
from app.services import preferences as preferences_service

router = APIRouter()


@router.get("", response_model=PreferencesOut)
async def get_preferences(current_user: CurrentUser, db: DbSession) -> PreferencesOut:
    """``GET /users/me/preferences``: saved preferences, or the defaults if none (PREF-1)."""
    return await preferences_service.get_preferences(db, current_user)


@router.put("", response_model=PreferencesOut)
async def put_preferences(
    data: PreferencesIn, current_user: CurrentUser, db: DbSession
) -> PreferencesOut:
    """``PUT /users/me/preferences``: replace all preferences (PREF-5).

    Returns the stored, normalised values (lowercase ingredient names, uppercase
    region), or 422 for an unknown diet, a bad region or too many ingredients.
    """
    return await preferences_service.put_preferences(db, current_user, data)
