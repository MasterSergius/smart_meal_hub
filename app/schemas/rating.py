import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class RatingCreate(BaseModel):
    score: int = Field(..., ge=1, le=5)
    comment: str | None = None


class RatingOut(BaseModel):
    id: uuid.UUID
    recipe_id: uuid.UUID
    score: int
    comment: str | None
    created_at: datetime
    recipe_avg_rating: float | None
    recipe_rating_count: int

    model_config = {"from_attributes": True}
