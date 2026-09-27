# Import all models here so Alembic autogenerate picks them up.
from app.models.rating import Rating
from app.models.recipe import Recipe
from app.models.user import User

__all__ = ["User", "Recipe", "Rating"]
