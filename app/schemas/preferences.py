from datetime import datetime
from typing import Annotated

from annotated_types import Interval, MaxLen
from pydantic import AfterValidator, BaseModel, Field, StringConstraints

from app.constants import (
    DEFAULT_HOUSEHOLD_SIZE,
    MAX_EXCLUDED_INGREDIENT_LENGTH,
    MAX_EXCLUDED_INGREDIENTS,
    MAX_HOUSEHOLD_SIZE,
    Diet,
)
from app.services.matching import normalize_name


def _dedupe(values: list[Diet]) -> list[Diet]:
    """PREF-2: drop duplicate diets, keeping first-seen order."""
    return list(dict.fromkeys(values))


def _clean_excluded(values: list[str]) -> list[str]:
    """PREF-3: normalise each name, drop empty ones and duplicates, then check the limits."""
    items = list(dict.fromkeys(n for n in (normalize_name(v) for v in values) if n))
    if len(items) > MAX_EXCLUDED_INGREDIENTS:
        raise ValueError(f"at most {MAX_EXCLUDED_INGREDIENTS} excluded ingredients are allowed")
    too_long = [i for i in items if len(i) > MAX_EXCLUDED_INGREDIENT_LENGTH]
    if too_long:
        raise ValueError(
            f"excluded ingredient longer than {MAX_EXCLUDED_INGREDIENT_LENGTH} characters"
        )
    return items


# Reusable field types: preferences and menu generation validate these the same way.
# annotated_types constraints (not Field) so they also apply inside ``X | None``.
Diets = Annotated[list[Diet], AfterValidator(_dedupe)]
ExcludedIngredients = Annotated[
    # the raw list may hold blanks and duplicates, so its cap is looser than the cleaned one
    list[Annotated[str, StringConstraints(max_length=500)]],
    MaxLen(4 * MAX_EXCLUDED_INGREDIENTS),
    AfterValidator(_clean_excluded),
]
Region = Annotated[
    str, StringConstraints(pattern=r"^[A-Za-z]{2}$"), AfterValidator(str.upper)
]  # PREF-4: ISO 3166-1 alpha-2, stored uppercase
HouseholdSize = Annotated[int, Interval(ge=1, le=MAX_HOUSEHOLD_SIZE)]


class PreferencesIn(BaseModel):
    """Request body for ``PUT /users/me/preferences``.

    Replaces the whole object: a missing field is reset to its default (PREF-5).
    """

    diets: Diets = Field(default_factory=list)
    excluded_ingredients: ExcludedIngredients = Field(default_factory=list)
    household_size: HouseholdSize = DEFAULT_HOUSEHOLD_SIZE
    region: Region | None = None


class PreferencesOut(BaseModel):
    """A user's preferences; ``updated_at`` is ``None`` until they are first saved (PREF-1)."""

    diets: list[str]
    excluded_ingredients: list[str]
    household_size: int
    region: str | None
    updated_at: datetime | None

    model_config = {"from_attributes": True}
