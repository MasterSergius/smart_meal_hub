"""Menus API — spec v0.2.0 §6.5, §7, §8 (GEN-…, MENU-…, SCALE-…).

Generation draws from the whole catalog, so every test starts from an empty one
(``empty_catalog``) and creates exactly the recipes it needs.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recipe import Recipe

MENUS_URL = "/api/v1/menus"
GENERATE_URL = f"{MENUS_URL}/generate"
RECIPES_URL = "/api/v1/recipes"
PREFS_URL = "/api/v1/users/me/preferences"
MEALS = ("breakfast", "lunch", "dinner")


@pytest.fixture(autouse=True)
async def empty_catalog(db: AsyncSession) -> None:
    """Delete all recipes (their ratings cascade; menu slots are emptied)."""
    await db.execute(delete(Recipe))
    await db.commit()


async def _auth_header(client: AsyncClient) -> dict:
    email = f"menu-{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "display_name": "Mia"},
    )
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _add_recipe(
    client: AsyncClient,
    headers: dict,
    meal_types: list[str],
    ingredients: list[tuple[str, float, str]] | None = None,
    diet_tags: list[str] | None = None,
    servings: int = 2,
    cuisine: str | None = None,
) -> str:
    payload = {
        "title": f"Recipe {uuid.uuid4().hex[:6]}",
        "ingredients": [
            {"name": n, "amount": a, "unit": u} for n, a, u in (ingredients or [("rice", 100, "g")])
        ],
        "steps": ["Cook."],
        "diet_tags": diet_tags or [],
        "meal_types": meal_types,
        "servings": servings,
        "cuisine": cuisine,
    }
    r = await client.post(RECIPES_URL, json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _add_week(
    client: AsyncClient,
    headers: dict,
    ingredients: list[tuple[str, float, str]] | None = None,
    diet_tags: list[str] | None = None,
) -> dict[str, set[str]]:
    """7 recipes per meal type, each for one meal type only."""
    return {
        meal: {
            await _add_recipe(client, headers, [meal], ingredients, diet_tags) for _ in range(7)
        }
        for meal in MEALS
    }


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def _recipe_ids(menu: dict) -> list[str | None]:
    return [s["recipe"]["id"] if s["recipe"] else None for s in menu["slots"]]


# ── Generation ────────────────────────────────────────────────────────────────


async def test_generate_full_week(client: AsyncClient) -> None:
    headers = await _auth_header(client)
    week = await _add_week(client, headers)
    r = await client.post(GENERATE_URL, json={"start_date": _today()}, headers=headers)
    assert r.status_code == 201, r.text
    menu = r.json()

    slots = menu["slots"]
    assert [(s["day"], s["meal_type"]) for s in slots] == [
        (d, m) for d in range(1, 8) for m in MEALS
    ]
    start = datetime.now(UTC).date()
    assert [s["date"] for s in slots[::3]] == [
        (start + timedelta(days=i)).isoformat() for i in range(7)
    ]
    for s in slots:  # GEN-3
        assert s["recipe"]["id"] in week[s["meal_type"]]
    assert len(set(_recipe_ids(menu))) == 21  # GEN-10
    assert menu["warnings"] == []
    assert isinstance(menu["seed"], int)


async def test_generate_without_body_uses_defaults(client: AsyncClient) -> None:
    headers = await _auth_header(client)
    await _add_week(client, headers)
    r = await client.post(GENERATE_URL, headers=headers)
    assert r.status_code == 201
    body = r.json()
    assert body["start_date"] == _today()
    assert body["servings"] == 2 and body["diets"] == [] and body["region"] is None


async def test_gen9_same_seed_same_menu(client: AsyncClient) -> None:
    headers = await _auth_header(client)
    await _add_week(client, headers)
    body = {"start_date": _today(), "seed": 12345}
    first = (await client.post(GENERATE_URL, json=body, headers=headers)).json()
    second = (await client.post(GENERATE_URL, json=body, headers=headers)).json()
    assert first["id"] != second["id"]
    assert _recipe_ids(first) == _recipe_ids(second)
    assert first["seed"] == 12345


async def test_gen4_gen5_preferences_applied(client: AsyncClient) -> None:
    headers = await _auth_header(client)
    veg = await _add_week(client, headers, diet_tags=["Vegetarian"])  # C-1: stored lowercase
    await _add_week(client, headers)  # not vegetarian
    peanut_butter = [("Peanut Butter", 2, "tbsp")]
    await _add_week(client, headers, diet_tags=["vegan"], ingredients=peanut_butter)
    await client.put(
        PREFS_URL,
        json={"diets": ["vegetarian"], "excluded_ingredients": ["peanut"], "household_size": 4},
        headers=headers,
    )
    menu = (await client.post(GENERATE_URL, headers=headers)).json()
    allowed = set().union(*veg.values())
    assert set(_recipe_ids(menu)) <= allowed
    assert menu["diets"] == ["vegetarian"]
    assert menu["excluded_ingredients"] == ["peanut"]
    assert menu["servings"] == 4


async def test_gen4_vegan_counts_as_vegetarian(client: AsyncClient) -> None:
    headers = await _auth_header(client)
    vegan = await _add_week(client, headers, diet_tags=["vegan"])
    menu = (
        await client.post(GENERATE_URL, json={"diets": ["vegetarian"]}, headers=headers)
    ).json()
    assert set(_recipe_ids(menu)) == set().union(*vegan.values())


async def test_request_overrides_are_not_saved(client: AsyncClient) -> None:
    headers = await _auth_header(client)
    await _add_week(client, headers)
    await client.put(PREFS_URL, json={"region": "UA", "household_size": 3}, headers=headers)
    menu = (
        await client.post(GENERATE_URL, json={"region": None, "servings": 5}, headers=headers)
    ).json()
    assert menu["region"] is None and menu["servings"] == 5
    prefs = (await client.get(PREFS_URL, headers=headers)).json()
    assert prefs["region"] == "UA" and prefs["household_size"] == 3


async def test_gen12_gen13_partial_menu_with_warnings(client: AsyncClient) -> None:
    headers = await _auth_header(client)
    only = await _add_recipe(client, headers, ["breakfast"])
    r = await client.post(GENERATE_URL, headers=headers)
    assert r.status_code == 201  # D-2: never fails for lack of recipes
    menu = r.json()
    assert all(
        (s["recipe"] and s["recipe"]["id"] == only) if s["meal_type"] == "breakfast"
        else s["recipe"] is None
        for s in menu["slots"]
    )
    assert "Some breakfast dishes repeat during the week" in menu["warnings"]
    assert "Day 1 lunch: no dish" in menu["warnings"]
    assert sum(w.endswith(": no dish") for w in menu["warnings"]) == 14


@pytest.mark.parametrize(
    "body",
    [
        {"start_date": "2000-01-01"},
        {"servings": 0},
        {"servings": 21},
        {"diets": ["paleo"]},
        {"region": "Ukraine"},
        {"seed": -1},
    ],
)
async def test_generate_validation(client: AsyncClient, body: dict) -> None:
    r = await client.post(GENERATE_URL, json=body, headers=await _auth_header(client))
    assert r.status_code == 422


async def test_gen6_region_seasonal_data_is_used(client: AsyncClient, db: AsyncSession) -> None:
    """Seasonal produce only shifts weights; here it just must not break generation."""
    from app.models.seasonal import SeasonalProduce

    db.add(SeasonalProduce(region="ZZ", name="pumpkin", months=list(range(1, 13))))
    await db.commit()
    headers = await _auth_header(client)
    await _add_week(client, headers, ingredients=[("pumpkin", 300, "g")])
    r = await client.post(GENERATE_URL, json={"region": "zz"}, headers=headers)
    assert r.status_code == 201
    assert r.json()["region"] == "ZZ"


# ── Reading, listing, ownership ───────────────────────────────────────────────


async def test_menu1_other_users_get_404(client: AsyncClient) -> None:
    owner = await _auth_header(client)
    other = await _auth_header(client)
    await _add_week(client, owner)
    menu_id = (await client.post(GENERATE_URL, headers=owner)).json()["id"]
    url = f"{MENUS_URL}/{menu_id}"

    assert (await client.get(url, headers=other)).status_code == 404
    assert (await client.patch(url, json={"servings": 3}, headers=other)).status_code == 404
    assert (await client.delete(url, headers=other)).status_code == 404
    assert (await client.post(f"{url}/slots/1/lunch/replace", headers=other)).status_code == 404
    assert (await client.get(url, headers=owner)).status_code == 200


async def test_menu_endpoints_require_auth(client: AsyncClient) -> None:
    assert (await client.post(GENERATE_URL)).status_code == 403  # missing header, as in v0.1
    assert (await client.get(MENUS_URL)).status_code == 403


async def test_menu2_list_newest_first(client: AsyncClient) -> None:
    headers = await _auth_header(client)
    await _add_recipe(client, headers, ["breakfast"])
    today = datetime.now(UTC).date()
    for offset in (0, 7, 3):
        body = {"start_date": (today + timedelta(days=offset)).isoformat()}
        await client.post(GENERATE_URL, json=body, headers=headers)

    r = await client.get(MENUS_URL, params={"limit": 2}, headers=headers)
    assert r.status_code == 200
    page = r.json()
    assert page["total"] == 3 and len(page["items"]) == 2
    assert [i["start_date"] for i in page["items"]] == [
        (today + timedelta(days=7)).isoformat(),
        (today + timedelta(days=3)).isoformat(),
    ]
    assert page["items"][0]["empty_slots"] == 14  # only breakfasts filled


async def test_menu2_list_only_own_menus(client: AsyncClient) -> None:
    owner = await _auth_header(client)
    other = await _auth_header(client)
    await _add_recipe(client, owner, ["breakfast"])
    await client.post(GENERATE_URL, headers=owner)
    assert (await client.get(MENUS_URL, headers=other)).json()["total"] == 0


async def test_menu3_delete(client: AsyncClient) -> None:
    headers = await _auth_header(client)
    await _add_recipe(client, headers, ["breakfast"])
    menu_id = (await client.post(GENERATE_URL, headers=headers)).json()["id"]
    assert (await client.delete(f"{MENUS_URL}/{menu_id}", headers=headers)).status_code == 204
    assert (await client.get(f"{MENUS_URL}/{menu_id}", headers=headers)).status_code == 404


async def test_menu7_deleted_recipe_empties_slot(client: AsyncClient) -> None:
    headers = await _auth_header(client)
    recipe_id = await _add_recipe(client, headers, ["breakfast"])
    menu_id = (await client.post(GENERATE_URL, headers=headers)).json()["id"]
    await client.delete(f"{RECIPES_URL}/{recipe_id}", headers=headers)

    menu = (await client.get(f"{MENUS_URL}/{menu_id}", headers=headers)).json()
    assert all(s["recipe"] is None and s["scaled_ingredients"] == [] for s in menu["slots"])
    assert "Day 1 breakfast: no dish" in menu["warnings"]


# ── Scaling (FR-1.3) ──────────────────────────────────────────────────────────


async def test_scale1_menu_rescales_on_patch(client: AsyncClient) -> None:
    headers = await _auth_header(client)
    await _add_recipe(
        client,
        headers,
        ["breakfast"],
        ingredients=[("garlic", 3, "cloves"), ("chicken breast", 500, "g")],
        servings=2,
    )
    menu = (await client.post(GENERATE_URL, json={"servings": 2}, headers=headers)).json()
    assert menu["slots"][0]["scaled_ingredients"][0]["amount"] == 3

    r = await client.patch(f"{MENUS_URL}/{menu['id']}", json={"servings": 3}, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["servings"] == 3
    assert body["slots"][0]["scaled_ingredients"] == [
        {"name": "garlic", "amount": 5, "unit": "cloves"},
        {"name": "chicken breast", "amount": 750, "unit": "g"},
    ]


async def test_patch_servings_validation(client: AsyncClient) -> None:
    headers = await _auth_header(client)
    await _add_recipe(client, headers, ["breakfast"])
    menu_id = (await client.post(GENERATE_URL, headers=headers)).json()["id"]
    r = await client.patch(f"{MENUS_URL}/{menu_id}", json={"servings": 0}, headers=headers)
    assert r.status_code == 422


# ── Replacement (FR-1.2) ──────────────────────────────────────────────────────


async def test_menu4_automatic_replace(client: AsyncClient) -> None:
    headers = await _auth_header(client)
    week = await _add_week(client, headers)
    spare = await _add_recipe(client, headers, ["lunch"])  # 8 lunches, 7 slots → one unused
    menu = (await client.post(GENERATE_URL, headers=headers)).json()
    old = menu["slots"][1]["recipe"]["id"]  # day 1 lunch
    unused = (week["lunch"] | {spare}) - set(_recipe_ids(menu))
    assert len(unused) == 1

    r = await client.post(f"{MENUS_URL}/{menu['id']}/slots/1/lunch/replace", headers=headers)
    assert r.status_code == 200, r.text
    slot = r.json()
    assert slot["day"] == 1 and slot["meal_type"] == "lunch"
    assert slot["recipe"]["id"] != old
    assert slot["recipe"]["id"] in unused  # a recipe not yet in the menu is preferred


async def test_menu4_replace_follows_menu_rules(client: AsyncClient) -> None:
    headers = await _auth_header(client)
    await _add_recipe(client, headers, ["lunch"])
    await _add_recipe(client, headers, ["lunch"], ingredients=[("peanuts", 50, "g")])
    menu = (
        await client.post(GENERATE_URL, json={"excluded_ingredients": ["peanut"]}, headers=headers)
    ).json()
    r = await client.post(f"{MENUS_URL}/{menu['id']}/slots/1/lunch/replace", headers=headers)
    # the only other lunch has peanuts, so the one allowed recipe (already in the slot)
    # can only be swapped for itself → no alternative
    assert r.status_code == 409


async def test_menu6_chosen_recipe_with_excluded_ingredient_warns(client: AsyncClient) -> None:
    headers = await _auth_header(client)
    await _add_recipe(client, headers, ["breakfast"])
    nutty = await _add_recipe(
        client, headers, ["dinner"], ingredients=[("peanut butter", 2, "tbsp")]
    )
    menu = (
        await client.post(GENERATE_URL, json={"excluded_ingredients": ["peanut"]}, headers=headers)
    ).json()

    url = f"{MENUS_URL}/{menu['id']}/slots/2/breakfast/replace"
    r = await client.post(url, json={"recipe_id": nutty}, headers=headers)
    assert r.status_code == 200  # D-3: allowed (meal type and stop-list not enforced)
    slot = r.json()
    assert slot["recipe"]["id"] == nutty
    assert slot["warnings"] == ["Contains excluded ingredient: peanut"]

    full = (await client.get(f"{MENUS_URL}/{menu['id']}", headers=headers)).json()
    assert "Day 2 breakfast: Contains excluded ingredient: peanut" in full["warnings"]  # MENU-9


async def test_menu6_unknown_recipe_404(client: AsyncClient) -> None:
    headers = await _auth_header(client)
    await _add_recipe(client, headers, ["breakfast"])
    menu_id = (await client.post(GENERATE_URL, headers=headers)).json()["id"]
    r = await client.post(
        f"{MENUS_URL}/{menu_id}/slots/1/breakfast/replace",
        json={"recipe_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert r.status_code == 404


async def test_menu7_empty_slot_can_be_refilled(client: AsyncClient) -> None:
    headers = await _auth_header(client)
    await _add_recipe(client, headers, ["breakfast"])
    menu_id = (await client.post(GENERATE_URL, headers=headers)).json()["id"]
    lunch = await _add_recipe(client, headers, ["lunch"])
    r = await client.post(f"{MENUS_URL}/{menu_id}/slots/3/lunch/replace", headers=headers)
    assert r.status_code == 200
    assert r.json()["recipe"]["id"] == lunch


async def test_menu8_replace_bumps_updated_at(client: AsyncClient) -> None:
    headers = await _auth_header(client)
    await _add_recipe(client, headers, ["breakfast"])
    other = await _add_recipe(client, headers, ["breakfast"])
    menu = (await client.post(GENERATE_URL, headers=headers)).json()
    await client.post(
        f"{MENUS_URL}/{menu['id']}/slots/1/breakfast/replace",
        json={"recipe_id": other},
        headers=headers,
    )
    after = (await client.get(f"{MENUS_URL}/{menu['id']}", headers=headers)).json()
    assert after["updated_at"] >= menu["updated_at"]
    assert after["slots"][0]["recipe"]["id"] == other


@pytest.mark.parametrize("path", ["slots/0/lunch", "slots/8/lunch", "slots/1/brunch"])
async def test_replace_bad_slot_422(client: AsyncClient, path: str) -> None:
    headers = await _auth_header(client)
    await _add_recipe(client, headers, ["breakfast"])
    menu_id = (await client.post(GENERATE_URL, headers=headers)).json()["id"]
    r = await client.post(f"{MENUS_URL}/{menu_id}/{path}/replace", headers=headers)
    assert r.status_code == 422
