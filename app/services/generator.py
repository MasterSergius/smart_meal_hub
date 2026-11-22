"""Weekly menu generation and dish replacement (spec v0.2.0 §6, §7).

Pure logic: takes plain data, does no I/O, so every rule is unit-tested without a
database. ``app.services.menu`` loads the data and persists the result.
"""

import random
import uuid
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.constants import DAYS_IN_MENU, MEAL_TYPES
from app.services.matching import matched_terms, normalize_name, term_matches

RATING_W = 1.0  # GEN-6 weights
SEASON_W = 1.0
UNRATED_SCORE = 3.0  # GEN-7
SAME_DAY_CUISINE_FACTOR = 0.3  # GEN-11

Seasonal = Mapping[str, frozenset[int]]  # normalised produce name → months (1-12)


@dataclass(frozen=True)
class Candidate:
    """The parts of a recipe the generator needs."""

    id: uuid.UUID
    meal_types: frozenset[str]
    diet_tags: frozenset[str]
    cuisine: str | None
    ingredient_names: tuple[str, ...]
    avg_rating: float | None = None

    @classmethod
    def build(
        cls,
        id: uuid.UUID,
        meal_types: Iterable[str],
        diet_tags: Iterable[str] | None,
        cuisine: str | None,
        ingredient_names: Iterable[str],
        avg_rating: float | None = None,
    ) -> "Candidate":
        """Create a candidate with normalised tags, cuisine and ingredient names."""
        return cls(
            id=id,
            meal_types=frozenset(meal_types),
            diet_tags=frozenset(normalize_name(t) for t in diet_tags or ()),
            cuisine=normalize_name(cuisine) if cuisine else None,
            ingredient_names=tuple(normalize_name(n) for n in ingredient_names),
            avg_rating=avg_rating,
        )


@dataclass(frozen=True)
class Rules:
    """A menu's snapshot of the user's rules (§3.4)."""

    diets: tuple[str, ...] = ()
    excluded_ingredients: tuple[str, ...] = ()


@dataclass(frozen=True)
class SlotPick:
    """One generated slot; ``recipe_id`` is ``None`` for an empty slot (GEN-13)."""

    day: int
    meal_type: str
    recipe_id: uuid.UUID | None


class NoAlternativeError(Exception):
    """MENU-4: no other recipe can fill the slot."""


# ── Eligibility (GEN-3 … GEN-5) ───────────────────────────────────────────────


def satisfies_diets(diet_tags: frozenset[str], diets: Iterable[str]) -> bool:
    """GEN-4: the recipe has every required diet tag; a vegan recipe also counts as vegetarian."""
    for diet in diets:
        if diet in diet_tags:
            continue
        if diet == "vegetarian" and "vegan" in diet_tags:
            continue
        return False
    return True


def excluded_terms_in(candidate: Candidate, excluded_ingredients: Iterable[str]) -> list[str]:
    """Stop-list terms that match one of the candidate's ingredients (GEN-2)."""
    return matched_terms(excluded_ingredients, candidate.ingredient_names)


def eligible(candidates: Iterable[Candidate], rules: Rules) -> list[Candidate]:
    """GEN-4 and GEN-5 applied to every candidate, sorted by id for reproducibility (GEN-9).

    GEN-3 (meal type) is checked per slot by ``_pool_for``.
    """
    result = [
        c
        for c in candidates
        if satisfies_diets(c.diet_tags, rules.diets)
        and not excluded_terms_in(c, rules.excluded_ingredients)
    ]
    return sorted(result, key=lambda c: c.id.bytes)


# ── Scoring (GEN-6, GEN-7, GEN-11) ────────────────────────────────────────────


def produce_months(ingredient_name: str, seasonal: Seasonal) -> frozenset[int] | None:
    """Months of the first seasonal produce that matches the ingredient (GEN-2), else ``None``."""
    for produce, months in seasonal.items():
        if term_matches(produce, ingredient_name):
            return months
    return None


class _Weights:
    """Computes candidate weights, caching the costly parts.

    Seasonal matching is cached per ingredient name (names repeat a lot across
    recipes) and the base weight per (recipe, month), which keeps generation fast on
    a large catalog (GEN-15).
    """

    def __init__(self, seasonal: Seasonal) -> None:
        self._seasonal = seasonal
        self._months: dict[str, frozenset[int] | None] = {}
        self._base: dict[tuple[uuid.UUID, int], float] = {}

    def months_for(self, ingredient_name: str) -> frozenset[int] | None:
        if ingredient_name not in self._months:
            self._months[ingredient_name] = produce_months(ingredient_name, self._seasonal)
        return self._months[ingredient_name]

    def season_ratio(self, candidate: Candidate, month: int) -> float:
        """GEN-6: share of the recipe's known produce that is in season in ``month``.

        Ingredients that aren't in the seasonal table are neutral; a recipe with no
        known produce scores 0.
        """
        known = in_season = 0
        for ingredient in candidate.ingredient_names:
            months = self.months_for(ingredient)
            if months is None:
                continue
            known += 1
            if month in months:
                in_season += 1
        return in_season / known if known else 0.0

    def base(self, candidate: Candidate, month: int) -> float:
        """GEN-6/GEN-7: ``1 + RATING_W * rating / 5 + SEASON_W * season_ratio``."""
        key = (candidate.id, month)
        if key not in self._base:
            rating = candidate.avg_rating if candidate.avg_rating is not None else UNRATED_SCORE
            self._base[key] = (
                1.0 + RATING_W * rating / 5 + SEASON_W * self.season_ratio(candidate, month)
            )
        return self._base[key]

    def __call__(self, candidate: Candidate, month: int, day_cuisines: set[str]) -> float:
        """Base weight, reduced when the cuisine is already served that day (GEN-11)."""
        weight = self.base(candidate, month)
        if candidate.cuisine and candidate.cuisine in day_cuisines:
            weight *= SAME_DAY_CUISINE_FACTOR
        return weight


def _pool_for(candidates: Sequence[Candidate], meal_type: str) -> list[Candidate]:
    """GEN-3: candidates that can be served as ``meal_type``."""
    return [c for c in candidates if meal_type in c.meal_types]


def _weighted_choice(
    rng: random.Random, pool: Sequence[Candidate], weights: Sequence[float]
) -> Candidate:
    return rng.choices(pool, weights=weights, k=1)[0]


# ── Generation (GEN-8 … GEN-13) ───────────────────────────────────────────────


def generate(
    candidates: Iterable[Candidate],
    rules: Rules,
    start_date: date,
    seed: int,
    seasonal: Seasonal | None = None,
) -> list[SlotPick]:
    """Fill 7 days × breakfast, lunch, dinner.

    Same inputs and seed always give the same menu (GEN-9). Never raises for lack of
    recipes: it repeats the least-used recipe (GEN-12) or leaves the slot empty (GEN-13).
    """
    rng = random.Random(seed)
    weights = _Weights(seasonal or {})
    allowed = eligible(candidates, rules)
    pools = {meal: _pool_for(allowed, meal) for meal in MEAL_TYPES}
    used: Counter[uuid.UUID] = Counter()
    picks: list[SlotPick] = []

    for day in range(1, DAYS_IN_MENU + 1):  # GEN-8
        month = (start_date + timedelta(days=day - 1)).month
        day_cuisines: set[str] = set()
        for meal in MEAL_TYPES:
            pool = pools[meal]
            unused = [c for c in pool if used[c.id] == 0]
            choice: Candidate | None
            if unused:  # GEN-9, GEN-10
                ws = [weights(c, month, day_cuisines) for c in unused]
                choice = _weighted_choice(rng, unused, ws)
            elif pool:  # GEN-12: least used, ties broken by weight
                choice = min(pool, key=lambda c: (used[c.id], -weights(c, month, day_cuisines)))
            else:  # GEN-13
                choice = None

            if choice is not None:
                used[choice.id] += 1
                if choice.cuisine:
                    day_cuisines.add(choice.cuisine)
            picks.append(SlotPick(day, meal, choice.id if choice else None))
    return picks


def pick_replacement(
    candidates: Iterable[Candidate],
    rules: Rules,
    meal_type: str,
    slot_date: date,
    current_id: uuid.UUID | None,
    menu_recipe_ids: Iterable[uuid.UUID],
    day_cuisines: Iterable[str] = (),
    seasonal: Seasonal | None = None,
    rng: random.Random | None = None,
) -> uuid.UUID:
    """MENU-4: a new recipe for one slot, under the menu's rules.

    Prefers recipes not yet in the menu; falls back to ones used elsewhere in the
    menu, never the slot's current recipe. ``rng`` defaults to a fresh, unseeded
    generator so repeated clicks give different dishes (MENU-5).

    Raises:
        NoAlternativeError: nothing but the current recipe fits the slot.
    """
    rng = rng or random.Random()
    weights = _Weights(seasonal or {})
    cuisines = {normalize_name(c) for c in day_cuisines}
    in_menu = set(menu_recipe_ids)
    pool = [c for c in _pool_for(eligible(candidates, rules), meal_type) if c.id != current_id]
    fresh = [c for c in pool if c.id not in in_menu]
    pool = fresh or pool
    if not pool:
        raise NoAlternativeError("No alternative recipe available")
    ws = [weights(c, slot_date.month, cuisines) for c in pool]
    return _weighted_choice(rng, pool, ws).id


# ── Warnings (MENU-9) ─────────────────────────────────────────────────────────


def slot_order(day: int, meal_type: str) -> tuple[int, int]:
    """Sort key: by day, then breakfast, lunch, dinner."""
    return day, MEAL_TYPES.index(meal_type)  # type: ignore[arg-type]


@dataclass(frozen=True)
class SlotState:
    """A stored slot as seen when reading a menu; ``recipe_id`` ``None`` = empty."""

    day: int
    meal_type: str
    recipe_id: uuid.UUID | None
    ingredient_names: tuple[str, ...] = ()


@dataclass
class MenuWarnings:
    """``slot`` maps (day, meal_type) to that slot's warnings; ``menu`` is the full list."""

    slot: dict[tuple[int, str], list[str]] = field(default_factory=dict)
    menu: list[str] = field(default_factory=list)


def compute_warnings(
    slots: Sequence[SlotState], excluded_ingredients: Sequence[str]
) -> MenuWarnings:
    """MENU-9: warnings derived from the current slots, never stored.

    - slot: one ``Contains excluded ingredient: <term>`` per matched stop-list term;
    - menu: each slot warning prefixed with ``Day <n> <meal>: ``, then one line per
      meal type whose dishes repeat (GEN-12), then one line per empty slot (GEN-13).
    """
    result = MenuWarnings()
    ordered = sorted(slots, key=lambda s: slot_order(s.day, s.meal_type))

    for s in ordered:
        if s.recipe_id is None:
            continue
        terms = matched_terms(excluded_ingredients, s.ingredient_names)
        if terms:
            msgs = [f"Contains excluded ingredient: {t}" for t in terms]
            result.slot[(s.day, s.meal_type)] = msgs
            result.menu.extend(f"Day {s.day} {s.meal_type}: {m}" for m in msgs)

    seen: set[uuid.UUID] = set()
    repeating_meals: list[str] = []
    for s in ordered:
        if s.recipe_id is None:
            continue
        if s.recipe_id in seen and s.meal_type not in repeating_meals:
            repeating_meals.append(s.meal_type)
        seen.add(s.recipe_id)
    for meal in MEAL_TYPES:
        if meal in repeating_meals:
            result.menu.append(f"Some {meal} dishes repeat during the week")

    empty = (s for s in ordered if s.recipe_id is None)
    result.menu.extend(f"Day {s.day} {s.meal_type}: no dish" for s in empty)
    return result
