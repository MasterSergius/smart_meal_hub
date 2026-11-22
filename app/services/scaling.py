"""Portion scaling (spec v0.2.0 §8, FR-1.3). Pure functions, no I/O."""

import math
from typing import Any

# SCALE-2: units counted in whole items; an empty unit means "items" too ("2 eggs" → unit "").
COUNTABLE_UNITS = frozenset(
    {
        "",
        "pc",
        "pcs",
        "piece",
        "pieces",
        "clove",
        "cloves",
        "slice",
        "slices",
        "egg",
        "eggs",
        "can",
        "cans",
        "bunch",
        "bunches",
    }
)


def scale_amount(amount: float, unit: str, factor: float) -> float:
    """Scale one amount.

    Countable units are rounded up to a whole number, at least 1 when the original
    amount is above 0 (SCALE-2); everything else is rounded to 2 decimals (SCALE-3).
    The intermediate ``round(..., 6)`` drops float noise such as ``1.0000000002`` so it
    isn't rounded up to 2.
    """
    scaled = amount * factor
    if unit.strip().lower() in COUNTABLE_UNITS:
        if amount <= 0:
            return 0
        return max(1, math.ceil(round(scaled, 6)))
    return round(scaled, 2)


def scale_ingredients(
    ingredients: list[dict[str, Any]], recipe_servings: int, servings: int
) -> list[dict[str, Any]]:
    """SCALE-1: the recipe's ingredients for ``servings`` people instead of ``recipe_servings``.

    Names and units are kept as written; unit conversion is out of scope (v0.3).
    """
    factor = servings / recipe_servings if recipe_servings > 0 else 1.0
    return [
        {
            "name": item["name"],
            "amount": scale_amount(float(item["amount"]), item["unit"], factor),
            "unit": item["unit"],
        }
        for item in ingredients
    ]
