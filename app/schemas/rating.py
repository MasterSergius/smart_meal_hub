import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class RatingCreate(BaseModel):
    """Request body for ``POST /recipes/{id}/ratings``: a 1-5 score and optional comment."""

    score: int = Field(..., ge=1, le=5)
    comment: str | None = None


class RatingOut(BaseModel):
    """The caller's rating after the write, plus the recipe's updated aggregate.

    ``recipe_avg_rating`` / ``recipe_rating_count`` are returned so the client can
    refresh the recipe's stars without a second request.
    """

    id: uuid.UUID
    recipe_id: uuid.UUID
    score: int
    comment: str | None
    created_at: datetime
    recipe_avg_rating: float | None
    recipe_rating_count: int

    model_config = {"from_attributes": True}
