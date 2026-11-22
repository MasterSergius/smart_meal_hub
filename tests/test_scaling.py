"""Portion scaling — spec v0.2.0 §8 (SCALE-1 … SCALE-3)."""

from app.services.scaling import scale_amount, scale_ingredients


def test_scale1_spec_example() -> None:
    ingredients = [
        {"name": "garlic", "amount": 3, "unit": "cloves"},
        {"name": "chicken breast", "amount": 500, "unit": "g"},
    ]
    assert scale_ingredients(ingredients, recipe_servings=2, servings=3) == [
        {"name": "garlic", "amount": 5, "unit": "cloves"},
        {"name": "chicken breast", "amount": 750, "unit": "g"},
    ]


def test_scale2_countable_units_round_up() -> None:
    assert scale_amount(1, "pcs", 1.5) == 2
    assert scale_amount(2, "Slices", 0.25) == 1  # 0.5 → at least 1
    assert scale_amount(2, "", 1.5) == 3  # empty unit counts as items


def test_scale2_no_rounding_up_on_float_noise() -> None:
    # 3 × (1/3) is 1.0000000000000002 in floating point
    assert scale_amount(3, "pcs", 1 / 3) == 1


def test_scale2_zero_amount_stays_zero() -> None:
    assert scale_amount(0, "pcs", 2) == 0


def test_scale3_other_units_round_to_two_decimals() -> None:
    assert scale_amount(500, "g", 1 / 3) == 166.67
    assert scale_amount(1, "tbsp", 1.5) == 1.5


def test_scale1_same_servings_is_unchanged() -> None:
    items = [{"name": "rice", "amount": 200, "unit": "g"}]
    assert scale_ingredients(items, 2, 2) == items
