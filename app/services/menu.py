"""Menus: generation, storage, replacement and serialisation (spec v0.2.0 §6-§8).

The planning rules live in the pure ``generator`` module; this module loads its
inputs from the database (GEN-14: one query for candidates, one for seasonal
produce) and persists the results.
"""

import random
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import ConflictError, NotFoundError
from app.models.menu import Menu, MenuSlot
from app.models.recipe import Recipe
from app.models.seasonal import SeasonalProduce
from app.models.user import User
from app.schemas.menu import (
    MenuGenerateIn,
    MenuListOut,
    MenuListParams,
    MenuOut,
    MenuRecipeOut,
    MenuSlotOut,
    MenuSummaryOut,
)
from app.services import generator
from app.services import preferences as preferences_service
from app.services.matching import normalize_name
from app.services.scaling import scale_ingredients

# ── Loading generator inputs (GEN-14) ─────────────────────────────────────────


async def load_candidates(db: AsyncSession, diets: list[str]) -> list[generator.Candidate]:
    """All recipes that satisfy the diets (GEN-4, in SQL), as generator candidates.

    Only the columns the generator needs are loaded. The stop-list (GEN-5) and meal
    types (GEN-3) are applied by the generator.
    """
    query = select(
        Recipe.id,
        Recipe.meal_types,
        Recipe.diet_tags,
        Recipe.cuisine,
        Recipe.ingredients,
        Recipe.avg_rating,
    )
    required = set(diets)
    if "vegetarian" in required:  # a vegan recipe also counts as vegetarian
        required.discard("vegetarian")
        query = query.where(Recipe.diet_tags.overlap(["vegetarian", "vegan"]))
    if required:
        query = query.where(Recipe.diet_tags.contains(sorted(required)))

    rows = (await db.execute(query)).all()
    return [
        generator.Candidate.build(
            id=row.id,
            meal_types=row.meal_types,
            diet_tags=row.diet_tags,
            cuisine=row.cuisine,
            ingredient_names=[item["name"] for item in row.ingredients],
            avg_rating=float(row.avg_rating) if row.avg_rating is not None else None,
        )
        for row in rows
    ]


async def load_seasonal(db: AsyncSession, region: str | None) -> generator.Seasonal:
    """Seasonal produce of ``region`` as ``{name: months}``; empty without a region (D-4)."""
    if region is None:
        return {}
    rows = await db.execute(
        select(SeasonalProduce.name, SeasonalProduce.months).where(SeasonalProduce.region == region)
    )
    return {normalize_name(name): frozenset(months) for name, months in rows.all()}


def _rules(menu: Menu) -> generator.Rules:
    """The menu's snapshot rules (§3.4)."""
    return generator.Rules(
        diets=tuple(menu.diets), excluded_ingredients=tuple(menu.excluded_ingredients)
    )


# ── Generation ────────────────────────────────────────────────────────────────


async def generate_menu(db: AsyncSession, user: User, data: MenuGenerateIn) -> MenuOut:
    """FR-1.1: build and store a 7-day menu; returns it with warnings (D-2).

    Missing request fields come from the user's preferences (§6.5). The rules used
    are stored on the menu as a snapshot.
    """
    prefs = await preferences_service.get_preferences(db, user)
    diets = data.diets if data.diets is not None else prefs.diets
    excluded = (
        data.excluded_ingredients
        if data.excluded_ingredients is not None
        else prefs.excluded_ingredients
    )
    region = data.region if "region" in data.model_fields_set else prefs.region
    servings = data.servings if data.servings is not None else prefs.household_size
    start_date = data.start_date or datetime.now(UTC).date()
    seed = data.seed if data.seed is not None else random.SystemRandom().getrandbits(63)

    candidates = await load_candidates(db, diets)
    seasonal = await load_seasonal(db, region)
    picks = generator.generate(
        candidates,
        generator.Rules(diets=tuple(diets), excluded_ingredients=tuple(excluded)),
        start_date,
        seed,
        seasonal,
    )

    menu = Menu(
        user_id=user.id,
        start_date=start_date,
        servings=servings,
        diets=list(diets),
        excluded_ingredients=list(excluded),
        region=region,
        seed=seed,
        slots=[MenuSlot(day=p.day, meal_type=p.meal_type, recipe_id=p.recipe_id) for p in picks],
    )
    db.add(menu)
    await db.commit()
    return to_menu_out(await _get_owned_menu(db, user, menu.id))


# ── Reading, changing, deleting ───────────────────────────────────────────────


async def _get_owned_menu(db: AsyncSession, user: User, menu_id: uuid.UUID) -> Menu:
    """Load a menu with its slots and their recipes, if ``user`` owns it.

    Raises:
        NotFoundError: no such menu, or it belongs to someone else (MENU-1, D-5).
    """
    result = await db.execute(
        select(Menu)
        .options(selectinload(Menu.slots).selectinload(MenuSlot.recipe))
        .where(Menu.id == menu_id, Menu.user_id == user.id)
        .execution_options(populate_existing=True)
    )
    menu = result.scalar_one_or_none()
    if menu is None:
        raise NotFoundError("Menu not found")
    return menu


async def get_menu(db: AsyncSession, user: User, menu_id: uuid.UUID) -> MenuOut:
    """``GET /menus/{id}`` for the owner (MENU-1)."""
    return to_menu_out(await _get_owned_menu(db, user, menu_id))


async def list_menus(db: AsyncSession, user: User, params: MenuListParams) -> MenuListOut:
    """MENU-2: the user's menus, newest ``start_date`` first, with empty-slot counts."""
    total = (
        await db.execute(select(func.count()).select_from(Menu).where(Menu.user_id == user.id))
    ).scalar_one()

    empty_slots = func.count(MenuSlot.id).filter(MenuSlot.recipe_id.is_(None))
    rows = await db.execute(
        select(Menu, empty_slots)
        .outerjoin(MenuSlot, MenuSlot.menu_id == Menu.id)
        .where(Menu.user_id == user.id)
        .group_by(Menu.id)
        .order_by(Menu.start_date.desc(), Menu.created_at.desc())
        .offset((params.page - 1) * params.limit)
        .limit(params.limit)
    )
    items = [
        MenuSummaryOut(
            id=menu.id,
            start_date=menu.start_date,
            servings=menu.servings,
            empty_slots=empty,
            created_at=menu.created_at,
        )
        for menu, empty in rows.all()
    ]
    return MenuListOut(total=total, page=params.page, limit=params.limit, items=items)


async def update_servings(
    db: AsyncSession, user: User, menu_id: uuid.UUID, servings: int
) -> MenuOut:
    """FR-1.3: change the number of people; amounts are rescaled on read (SCALE-4)."""
    menu = await _get_owned_menu(db, user, menu_id)
    menu.servings = servings
    await db.commit()
    return to_menu_out(await _get_owned_menu(db, user, menu_id))


async def delete_menu(db: AsyncSession, user: User, menu_id: uuid.UUID) -> None:
    """MENU-3: delete the menu; its slots go with it (``ON DELETE CASCADE``)."""
    menu = await _get_owned_menu(db, user, menu_id)
    await db.delete(menu)
    await db.commit()


async def replace_slot(
    db: AsyncSession,
    user: User,
    menu_id: uuid.UUID,
    day: int,
    meal_type: str,
    recipe_id: uuid.UUID | None,
) -> MenuSlotOut:
    """FR-1.2: put another recipe in one slot.

    With ``recipe_id`` the user's choice is stored as is; an excluded ingredient only
    produces a warning (MENU-6, D-3). Without it a recipe is picked under the menu's
    rules (MENU-4) with a fresh random choice (MENU-5).

    Raises:
        NotFoundError: unknown menu (or not the owner), or unknown ``recipe_id``.
        ConflictError: no alternative recipe is available (MENU-4).
    """
    menu = await _get_owned_menu(db, user, menu_id)
    slot = next((s for s in menu.slots if s.day == day and s.meal_type == meal_type), None)
    if slot is None:  # every menu has all 21 slots; only reachable with corrupted data
        raise NotFoundError("Menu slot not found")

    if recipe_id is not None:
        if await db.get(Recipe, recipe_id) is None:
            raise NotFoundError("Recipe not found")
        new_recipe_id = recipe_id
    else:
        day_cuisines = [
            s.recipe.cuisine
            for s in menu.slots
            if s.day == day and s is not slot and s.recipe is not None and s.recipe.cuisine
        ]
        try:
            new_recipe_id = generator.pick_replacement(
                await load_candidates(db, menu.diets),
                _rules(menu),
                meal_type,
                menu.start_date + timedelta(days=day - 1),
                current_id=slot.recipe_id,
                menu_recipe_ids=[s.recipe_id for s in menu.slots if s.recipe_id is not None],
                day_cuisines=day_cuisines,
                seasonal=await load_seasonal(db, menu.region),
            )
        except generator.NoAlternativeError as exc:
            raise ConflictError(str(exc)) from None

    slot.recipe_id = new_recipe_id
    menu.updated_at = func.now()  # MENU-8: only a child row changed, so bump it by hand
    await db.commit()

    out = to_menu_out(await _get_owned_menu(db, user, menu_id))
    return next(s for s in out.slots if s.day == day and s.meal_type == meal_type)


# ── Serialisation ─────────────────────────────────────────────────────────────


def _recipe_summary(recipe: Recipe) -> MenuRecipeOut:
    total = (recipe.prep_time_min or 0) + (recipe.cook_time_min or 0)
    return MenuRecipeOut(
        id=recipe.id,
        title=recipe.title,
        cuisine=recipe.cuisine,
        servings=recipe.servings,
        total_time_min=total or None,
        avg_rating=float(recipe.avg_rating) if recipe.avg_rating is not None else None,
        image_url=recipe.image_url,
    )


def to_menu_out(menu: Menu) -> MenuOut:
    """Build ``MenuOut``: ordered slots, scaled ingredients (SCALE-1), warnings (MENU-9).

    ``menu`` must have ``slots`` and each slot's ``recipe`` loaded.
    """
    slots = sorted(menu.slots, key=lambda s: generator.slot_order(s.day, s.meal_type))
    warnings = generator.compute_warnings(
        [
            generator.SlotState(
                day=s.day,
                meal_type=s.meal_type,
                recipe_id=s.recipe.id if s.recipe else None,
                ingredient_names=tuple(i["name"] for i in s.recipe.ingredients) if s.recipe else (),
            )
            for s in slots
        ],
        menu.excluded_ingredients,
    )
    slot_outs = [
        MenuSlotOut(
            day=s.day,
            date=menu.start_date + timedelta(days=s.day - 1),
            meal_type=s.meal_type,
            recipe=_recipe_summary(s.recipe) if s.recipe else None,
            scaled_ingredients=(
                scale_ingredients(s.recipe.ingredients, s.recipe.servings, menu.servings)
                if s.recipe
                else []
            ),
            warnings=warnings.slot.get((s.day, s.meal_type), []),
        )
        for s in slots
    ]
    return MenuOut(
        id=menu.id,
        start_date=menu.start_date,
        servings=menu.servings,
        diets=menu.diets,
        excluded_ingredients=menu.excluded_ingredients,
        region=menu.region,
        seed=menu.seed,
        slots=slot_outs,
        warnings=warnings.menu,
        created_at=menu.created_at,
        updated_at=menu.updated_at,
    )
