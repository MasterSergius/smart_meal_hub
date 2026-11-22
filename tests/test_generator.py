"""Menu generation rules on in-memory recipes — spec v0.2.0 §6, §7 (no database)."""

import random
import time
import uuid
from datetime import date

import pytest

from app.services.generator import (
    Candidate,
    NoAlternativeError,
    Rules,
    SlotState,
    compute_warnings,
    generate,
    pick_replacement,
)

START = date(2026, 11, 23)  # a Monday in November
_ids = iter(range(1, 1_000_000))


def recipe(
    meal_types: tuple[str, ...] = ("breakfast", "lunch", "dinner"),
    diet_tags: tuple[str, ...] = (),
    ingredients: tuple[str, ...] = ("rice",),
    cuisine: str | None = None,
    rating: float | None = None,
) -> Candidate:
    return Candidate.build(
        id=uuid.UUID(int=next(_ids)),
        meal_types=meal_types,
        diet_tags=diet_tags,
        cuisine=cuisine,
        ingredient_names=ingredients,
        avg_rating=rating,
    )


def week_catalog() -> list[Candidate]:
    """7 breakfasts, 7 lunches, 7 dinners: exactly enough for a menu without repeats."""
    return [recipe(meal_types=(m,)) for m in ("breakfast", "lunch", "dinner") for _ in range(7)]


def by_id(candidates: list[Candidate]) -> dict[uuid.UUID, Candidate]:
    return {c.id: c for c in candidates}


def test_gen8_fills_21_slots_in_order() -> None:
    picks = generate(week_catalog(), Rules(), START, seed=1)
    assert [(p.day, p.meal_type) for p in picks] == [
        (d, m) for d in range(1, 8) for m in ("breakfast", "lunch", "dinner")
    ]
    assert all(p.recipe_id is not None for p in picks)


def test_gen3_meal_type_respected() -> None:
    catalog = week_catalog()
    recipes = by_id(catalog)
    for p in generate(catalog, Rules(), START, seed=2):
        assert p.meal_type in recipes[p.recipe_id].meal_types  # type: ignore[index]


def test_gen4_diets_required_and_vegan_counts_as_vegetarian() -> None:
    vegan = [recipe(diet_tags=("vegan",)) for _ in range(30)]
    meat = [recipe() for _ in range(30)]
    keto_only = [recipe(diet_tags=("keto",)) for _ in range(30)]
    picks = generate(vegan + meat + keto_only, Rules(diets=("vegetarian",)), START, seed=3)
    allowed = {c.id for c in vegan}
    assert {p.recipe_id for p in picks} <= allowed


def test_gen4_multiple_diets_all_required() -> None:
    both = [recipe(diet_tags=("vegetarian", "gluten-free")) for _ in range(30)]
    one = [recipe(diet_tags=("vegetarian",)) for _ in range(30)]
    picks = generate(both + one, Rules(diets=("vegetarian", "gluten-free")), START, seed=4)
    assert {p.recipe_id for p in picks} <= {c.id for c in both}


def test_gen5_stop_list_never_picked() -> None:
    nutty = [recipe(ingredients=("rice", "roasted peanuts")) for _ in range(50)]
    safe = week_catalog()
    picks = generate(nutty + safe, Rules(excluded_ingredients=("peanut",)), START, seed=5)
    assert {p.recipe_id for p in picks} <= {c.id for c in safe}


def test_gen9_same_seed_same_menu_regardless_of_input_order() -> None:
    catalog = [recipe(cuisine=random.choice(["a", "b", None])) for _ in range(100)]
    first = generate(catalog, Rules(), START, seed=42)
    second = generate(list(reversed(catalog)), Rules(), START, seed=42)
    assert first == second


def test_gen9_different_seed_different_menu() -> None:
    catalog = [recipe() for _ in range(100)]
    assert generate(catalog, Rules(), START, seed=1) != generate(catalog, Rules(), START, seed=2)


def test_gen10_no_repeats_when_enough_recipes() -> None:
    picks = generate(week_catalog(), Rules(), START, seed=6)
    ids = [p.recipe_id for p in picks]
    assert len(set(ids)) == 21


def test_gen11_same_cuisine_same_day_is_less_likely() -> None:
    # Breakfast is always Italian; lunch can be Italian or Thai with equal base weight.
    breakfast = [recipe(meal_types=("breakfast",), cuisine="Italian") for _ in range(7)]
    italian = [recipe(meal_types=("lunch",), cuisine="Italian") for _ in range(50)]
    thai = [recipe(meal_types=("lunch",), cuisine="Thai") for _ in range(50)]
    thai_ids = {c.id for c in thai}
    thai_lunches = 0
    for seed in range(200):
        picks = generate(breakfast + italian + thai, Rules(), START, seed=seed)
        thai_lunches += sum(p.recipe_id in thai_ids for p in picks if p.meal_type == "lunch")
    share = thai_lunches / (200 * 7)
    assert share > 0.65  # 1 / (1 + 0.3) ≈ 0.77 expected; 0.5 without GEN-11


def test_gen6_seasonal_recipes_preferred() -> None:
    seasonal = {"pumpkin": frozenset({9, 10, 11}), "strawberry": frozenset({5, 6, 7})}
    in_season = [recipe(meal_types=("lunch",), ingredients=("pumpkin",)) for _ in range(50)]
    off_season = [recipe(meal_types=("lunch",), ingredients=("strawberry",)) for _ in range(50)]
    in_ids = {c.id for c in in_season}
    count = 0
    for seed in range(100):
        picks = generate(in_season + off_season, Rules(), START, seed=seed, seasonal=seasonal)
        count += sum(p.recipe_id in in_ids for p in picks if p.meal_type == "lunch")
    # weights 1 + 0.6 + 1 vs 1 + 0.6 + 0 → expected share ≈ 0.62
    assert count / (100 * 7) > 0.55


def test_gen7_unrated_recipes_still_picked() -> None:
    rated = [recipe(meal_types=("lunch",), rating=5.0) for _ in range(50)]
    unrated = [recipe(meal_types=("lunch",)) for _ in range(50)]
    unrated_ids = {c.id for c in unrated}
    picks = [p for s in range(20) for p in generate(rated + unrated, Rules(), START, seed=s)]
    assert any(p.recipe_id in unrated_ids for p in picks)


def test_gen12_repeats_least_used_when_not_enough() -> None:
    only = [recipe(meal_types=("breakfast",)) for _ in range(3)]
    picks = [p for p in generate(only, Rules(), START, seed=7) if p.meal_type == "breakfast"]
    counts = {c.id: sum(p.recipe_id == c.id for p in picks) for c in only}
    assert sorted(counts.values()) == [2, 2, 3]


def test_gen13_empty_slot_when_no_candidate() -> None:
    picks = generate([recipe(meal_types=("breakfast",))], Rules(), START, seed=8)
    assert all(p.recipe_id is None for p in picks if p.meal_type != "breakfast")


def test_gen15_ten_thousand_recipes_under_two_seconds() -> None:
    rng = random.Random(0)
    names = ["rice", "tomato", "egg", "peanut butter", "milk", "carrot", "potato"]
    names += [f"spice {i}" for i in range(300)]
    seasonal = {n: frozenset({7, 8, 9}) for n in ["tomato", "carrot", "potato"]}
    catalog = [
        recipe(
            meal_types=tuple(rng.sample(["breakfast", "lunch", "dinner"], rng.randint(1, 3))),
            diet_tags=tuple(rng.sample(["vegetarian", "vegan", "keto"], rng.randint(0, 2))),
            ingredients=tuple(rng.sample(names, 8)),
            cuisine=rng.choice(["Italian", "Asian", None]),
            rating=rng.choice([None, 3.5, 4.8]),
        )
        for _ in range(10_000)
    ]
    rules = Rules(diets=("vegetarian",), excluded_ingredients=("peanut", "egg", "milk"))
    start = time.perf_counter()
    generate(catalog, rules, START, seed=1, seasonal=seasonal)
    assert time.perf_counter() - start < 2.0


# ── Replacement (MENU-4, MENU-5) ──────────────────────────────────────────────


def test_menu4_replacement_prefers_recipes_not_in_menu() -> None:
    a, b, c = (recipe(meal_types=("lunch",)) for _ in range(3))
    for _ in range(20):
        new = pick_replacement([a, b, c], Rules(), "lunch", START, a.id, [a.id, b.id])
        assert new == c.id


def test_menu4_replacement_falls_back_to_recipes_in_menu() -> None:
    a, b = (recipe(meal_types=("lunch",)) for _ in range(2))
    assert pick_replacement([a, b], Rules(), "lunch", START, a.id, [a.id, b.id]) == b.id


def test_menu4_replacement_follows_rules() -> None:
    current = recipe(meal_types=("lunch",))
    nutty = recipe(meal_types=("lunch",), ingredients=("peanut",))
    wrong_meal = recipe(meal_types=("dinner",))
    with pytest.raises(NoAlternativeError):
        pick_replacement(
            [current, nutty, wrong_meal],
            Rules(excluded_ingredients=("peanut",)),
            "lunch",
            START,
            current.id,
            [current.id],
        )


def test_menu5_replacement_is_not_fixed_by_seed() -> None:
    catalog = [recipe(meal_types=("lunch",)) for _ in range(50)]
    results = {pick_replacement(catalog, Rules(), "lunch", START, None, []) for _ in range(20)}
    assert len(results) > 1


# ── Warnings (MENU-9) ─────────────────────────────────────────────────────────


def test_menu9_warnings() -> None:
    r1, r2 = uuid.uuid4(), uuid.uuid4()
    slots = [
        SlotState(1, "breakfast", r1, ("eggs",)),
        SlotState(1, "lunch", r2, ("peanut butter", "bread")),
        SlotState(1, "dinner", None),
        SlotState(2, "breakfast", r1, ("eggs",)),
    ]
    w = compute_warnings(slots, ["peanut", "soy"])
    assert w.slot == {(1, "lunch"): ["Contains excluded ingredient: peanut"]}
    assert w.menu == [
        "Day 1 lunch: Contains excluded ingredient: peanut",
        "Some breakfast dishes repeat during the week",
        "Day 1 dinner: no dish",
    ]


def test_menu9_no_warnings_for_clean_menu() -> None:
    slots = [SlotState(1, "breakfast", uuid.uuid4(), ("oats",))]
    w = compute_warnings(slots, ["peanut"])
    assert w.slot == {} and w.menu == []
