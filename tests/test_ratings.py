import pytest
from httpx import AsyncClient

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
RECIPES_URL = "/api/v1/recipes"

RECIPE_PAYLOAD = {
    "title": "Test Recipe",
    "ingredients": [{"name": "egg", "amount": 2, "unit": "pcs"}],
    "steps": ["Boil eggs."],
    "servings": 1,
}


async def _auth_header(client: AsyncClient, email: str) -> dict:
    await client.post(REGISTER_URL, json={"email": email, "password": "password123", "display_name": email.split("@")[0]})
    r = await client.post(LOGIN_URL, json={"email": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_rate_recipe(client: AsyncClient) -> None:
    author = await _auth_header(client, "rate_author@example.com")
    rater = await _auth_header(client, "rater@example.com")
    recipe_id = (await client.post(RECIPES_URL, json=RECIPE_PAYLOAD, headers=author)).json()["id"]

    r = await client.post(f"{RECIPES_URL}/{recipe_id}/ratings", json={"score": 4}, headers=rater)
    assert r.status_code == 200
    body = r.json()
    assert body["score"] == 4
    assert body["recipe_avg_rating"] == 4.0
    assert body["recipe_rating_count"] == 1


async def test_rate_own_recipe_forbidden(client: AsyncClient) -> None:
    author = await _auth_header(client, "own_rate@example.com")
    recipe_id = (await client.post(RECIPES_URL, json=RECIPE_PAYLOAD, headers=author)).json()["id"]
    r = await client.post(f"{RECIPES_URL}/{recipe_id}/ratings", json={"score": 5}, headers=author)
    assert r.status_code == 403


async def test_rating_updates_avg(client: AsyncClient) -> None:
    author = await _auth_header(client, "avg_author@example.com")
    rater1 = await _auth_header(client, "avg_rater1@example.com")
    rater2 = await _auth_header(client, "avg_rater2@example.com")
    recipe_id = (await client.post(RECIPES_URL, json=RECIPE_PAYLOAD, headers=author)).json()["id"]

    await client.post(f"{RECIPES_URL}/{recipe_id}/ratings", json={"score": 4}, headers=rater1)
    r = await client.post(f"{RECIPES_URL}/{recipe_id}/ratings", json={"score": 2}, headers=rater2)
    assert r.json()["recipe_avg_rating"] == 3.0
    assert r.json()["recipe_rating_count"] == 2


async def test_rerate_overwrites_previous(client: AsyncClient) -> None:
    author = await _auth_header(client, "rerate_author@example.com")
    rater = await _auth_header(client, "rerate_rater@example.com")
    recipe_id = (await client.post(RECIPES_URL, json=RECIPE_PAYLOAD, headers=author)).json()["id"]

    await client.post(f"{RECIPES_URL}/{recipe_id}/ratings", json={"score": 2}, headers=rater)
    r = await client.post(f"{RECIPES_URL}/{recipe_id}/ratings", json={"score": 5}, headers=rater)
    assert r.status_code == 200
    assert r.json()["recipe_rating_count"] == 1  # still one rating
    assert r.json()["recipe_avg_rating"] == 5.0


async def test_rate_nonexistent_recipe(client: AsyncClient) -> None:
    rater = await _auth_header(client, "rate_missing@example.com")
    r = await client.post(
        f"{RECIPES_URL}/00000000-0000-0000-0000-000000000000/ratings",
        json={"score": 3},
        headers=rater,
    )
    assert r.status_code == 404
