"""Fixed vocabularies shared by models, schemas and the menu generator (spec v0.2.0).

Kept free of third-party imports so the pure planning modules can use them too.
"""

from typing import Literal

MealType = Literal["breakfast", "lunch", "dinner"]
MEAL_TYPES: tuple[MealType, ...] = ("breakfast", "lunch", "dinner")
DEFAULT_MEAL_TYPES: tuple[MealType, ...] = ("lunch", "dinner")  # D-6, REC-1

# PREF-2: diets a user can require. An empty selection means "balanced" (D-1).
Diet = Literal["vegetarian", "vegan", "keto", "low-calorie", "gluten-free"]
DIETS: tuple[Diet, ...] = ("vegetarian", "vegan", "keto", "low-calorie", "gluten-free")

DAYS_IN_MENU = 7
MAX_HOUSEHOLD_SIZE = 20
DEFAULT_HOUSEHOLD_SIZE = 2
MAX_EXCLUDED_INGREDIENTS = 50
MAX_EXCLUDED_INGREDIENT_LENGTH = 100
