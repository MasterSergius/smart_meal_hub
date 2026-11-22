# Import all models here so Alembic autogenerate picks them up.
from app.models.menu import Menu, MenuSlot
from app.models.preferences import UserPreferences
from app.models.rating import Rating
from app.models.recipe import Recipe
from app.models.seasonal import SeasonalProduce
from app.models.user import User

__all__ = ["User", "Recipe", "Rating", "UserPreferences", "SeasonalProduce", "Menu", "MenuSlot"]
