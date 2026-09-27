import pytest
from httpx import AsyncClient

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
RECIPES_URL = "/api/v1/recipes"
SEARCH_URL = "/api/v1/recipes/search"

RECIPE_PAYLOAD = {
    "title": "Garlic Butter Chicken",
    "description": "Quick weeknight dinner",
    "ingredients": [
        {"name": "chicken breast", "amount": 500, "unit": "g"},
        {"name": "butter", "amount": 50, "unit": "g"},
    ],
    "steps": ["Season chicken.", "Cook in butter 6 min per side."],
    "diet_tags": ["low-calorie"],
    "cuisine": "American",
    "servings": 2,
    "prep_time_min": 10,
    "cook_time_min": 15,
}


async def _auth_header(client: AsyncClient, email: str = "bob@example.com") -> dict:
    await client.post(REGISTER_URL, json={"email": email, "password": "password123", "display_name": "Bob"})
    r = await client.post(LOGIN_URL, json={"email": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_add_recipe(client: AsyncClient) -> None:
    headers = await _auth_header(client)
    r = await client.post(RECIPES_URL, json=RECIPE_PAYLOAD, headers=headers)
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == RECIPE_PAYLOAD["title"]
    assert body["total_time_min"] == 25
    assert body["author"]["display_name"] == "Bob"


async def test_add_recipe_unauthenticated(client: AsyncClient) -> None:
    r = await client.post(RECIPES_URL, json=RECIPE_PAYLOAD)
    assert r.status_code == 403


async def test_get_recipe(client: AsyncClient) -> None:
    headers = await _auth_header(client, "get_recipe@example.com")
    created = await client.post(RECIPES_URL, json=RECIPE_PAYLOAD, headers=headers)
    recipe_id = created.json()["id"]
    r = await client.get(f"{RECIPES_URL}/{recipe_id}")
    assert r.status_code == 200
    assert r.json()["id"] == recipe_id


async def test_get_recipe_not_found(client: AsyncClient) -> None:
    r = await client.get(f"{RECIPES_URL}/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


async def test_delete_recipe_by_author(client: AsyncClient) -> None:
    headers = await _auth_header(client, "del_author@example.com")
    created = await client.post(RECIPES_URL, json=RECIPE_PAYLOAD, headers=headers)
    recipe_id = created.json()["id"]
    r = await client.delete(f"{RECIPES_URL}/{recipe_id}", headers=headers)
    assert r.status_code == 204
    assert (await client.get(f"{RECIPES_URL}/{recipe_id}")).status_code == 404


async def test_delete_recipe_by_non_author(client: AsyncClient) -> None:
    author_headers = await _auth_header(client, "owner@example.com")
    other_headers = await _auth_header(client, "intruder@example.com")
    created = await client.post(RECIPES_URL, json=RECIPE_PAYLOAD, headers=author_headers)
    recipe_id = created.json()["id"]
    r = await client.delete(f"{RECIPES_URL}/{recipe_id}", headers=other_headers)
    assert r.status_code == 403


async def test_search_no_params(client: AsyncClient) -> None:
    headers = await _auth_header(client, "search_base@example.com")
    await client.post(RECIPES_URL, json=RECIPE_PAYLOAD, headers=headers)
    r = await client.get(SEARCH_URL)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert body["total"] >= 1


async def test_search_by_text(client: AsyncClient) -> None:
    headers = await _auth_header(client, "search_text@example.com")
    await client.post(RECIPES_URL, json=RECIPE_PAYLOAD, headers=headers)
    r = await client.get(SEARCH_URL, params={"q": "Garlic"})
    assert r.status_code == 200
    assert any("Garlic" in item["title"] for item in r.json()["items"])


async def test_search_by_diet_tags(client: AsyncClient) -> None:
    headers = await _auth_header(client, "search_tags@example.com")
    await client.post(RECIPES_URL, json=RECIPE_PAYLOAD, headers=headers)
    r = await client.get(SEARCH_URL, params={"diet_tags": "low-calorie"})
    assert r.status_code == 200
    assert all("low-calorie" in item["diet_tags"] for item in r.json()["items"])


async def test_search_max_total_time(client: AsyncClient) -> None:
    headers = await _auth_header(client, "search_time@example.com")
    await client.post(RECIPES_URL, json=RECIPE_PAYLOAD, headers=headers)
    r = await client.get(SEARCH_URL, params={"max_total_time": 20})
    assert r.status_code == 200
    # RECIPE_PAYLOAD total is 25 min — should not appear
    assert all((i["total_time_min"] or 0) <= 20 for i in r.json()["items"])
