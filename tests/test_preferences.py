"""Preferences API — spec v0.2.0 §4 (PREF-1 … PREF-5)."""

import uuid

from httpx import AsyncClient

PREFS_URL = "/api/v1/users/me/preferences"


async def _auth_header(client: AsyncClient) -> dict:
    email = f"prefs-{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "display_name": "Pat"},
    )
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_pref1_defaults_before_first_save(client: AsyncClient) -> None:
    r = await client.get(PREFS_URL, headers=await _auth_header(client))
    assert r.status_code == 200
    assert r.json() == {
        "diets": [],
        "excluded_ingredients": [],
        "household_size": 2,
        "region": None,
        "updated_at": None,
    }


async def test_put_normalises_and_get_returns_saved(client: AsyncClient) -> None:
    headers = await _auth_header(client)
    r = await client.put(
        PREFS_URL,
        json={
            "diets": ["vegetarian", "vegetarian", "gluten-free"],
            "excluded_ingredients": ["Peanut", "shrimp ", "", "PEANUT", "  Sesame   Oil "],
            "household_size": 3,
            "region": "ua",
        },
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["diets"] == ["vegetarian", "gluten-free"]  # PREF-2: duplicates removed
    assert body["excluded_ingredients"] == ["peanut", "shrimp", "sesame oil"]  # PREF-3
    assert body["household_size"] == 3
    assert body["region"] == "UA"  # PREF-4
    assert body["updated_at"] is not None

    again = await client.get(PREFS_URL, headers=headers)
    assert again.json() == body


async def test_pref5_put_replaces_whole_object(client: AsyncClient) -> None:
    headers = await _auth_header(client)
    await client.put(
        PREFS_URL,
        json={"diets": ["keto"], "excluded_ingredients": ["milk"], "region": "UA"},
        headers=headers,
    )
    r = await client.put(PREFS_URL, json={"household_size": 4}, headers=headers)
    body = r.json()
    assert body["diets"] == [] and body["excluded_ingredients"] == [] and body["region"] is None
    assert body["household_size"] == 4


async def test_pref2_unknown_diet_rejected(client: AsyncClient) -> None:
    headers = await _auth_header(client)
    r = await client.put(PREFS_URL, json={"diets": ["carnivore"]}, headers=headers)
    assert r.status_code == 422


async def test_pref3_limits(client: AsyncClient) -> None:
    headers = await _auth_header(client)
    too_many = [f"item {i}" for i in range(51)]
    r = await client.put(PREFS_URL, json={"excluded_ingredients": too_many}, headers=headers)
    assert r.status_code == 422
    r = await client.put(PREFS_URL, json={"excluded_ingredients": ["x" * 101]}, headers=headers)
    assert r.status_code == 422


async def test_pref4_bad_region_rejected(client: AsyncClient) -> None:
    headers = await _auth_header(client)
    for region in ["UKR", "U1", ""]:
        r = await client.put(PREFS_URL, json={"region": region}, headers=headers)
        assert r.status_code == 422, region


async def test_household_size_range(client: AsyncClient) -> None:
    headers = await _auth_header(client)
    for size in [0, 21]:
        r = await client.put(PREFS_URL, json={"household_size": size}, headers=headers)
        assert r.status_code == 422


async def test_preferences_require_auth(client: AsyncClient) -> None:
    assert (await client.get(PREFS_URL)).status_code == 403  # missing header, as in v0.1
    assert (await client.put(PREFS_URL, json={})).status_code == 403
