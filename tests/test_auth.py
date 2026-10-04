from httpx import AsyncClient

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/auth/me"

USER = {"email": "alice@example.com", "password": "password123", "display_name": "Alice"}


async def test_register(client: AsyncClient) -> None:
    r = await client.post(REGISTER_URL, json=USER)
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == USER["email"]
    assert body["display_name"] == USER["display_name"]
    assert "id" in body
    assert "password_hash" not in body


async def test_register_duplicate_email(client: AsyncClient) -> None:
    await client.post(REGISTER_URL, json=USER)
    r = await client.post(REGISTER_URL, json=USER)
    assert r.status_code == 409


async def test_login_success(client: AsyncClient) -> None:
    await client.post(REGISTER_URL, json=USER)
    r = await client.post(LOGIN_URL, json={"email": USER["email"], "password": USER["password"]})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


async def test_login_wrong_password(client: AsyncClient) -> None:
    await client.post(REGISTER_URL, json=USER)
    r = await client.post(LOGIN_URL, json={"email": USER["email"], "password": "wrongpass"})
    assert r.status_code == 401


async def test_me_authenticated(client: AsyncClient) -> None:
    await client.post(REGISTER_URL, json=USER)
    login = await client.post(
        LOGIN_URL, json={"email": USER["email"], "password": USER["password"]}
    )
    token = login.json()["access_token"]
    r = await client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == USER["email"]


async def test_me_unauthenticated(client: AsyncClient) -> None:
    r = await client.get(ME_URL)
    assert r.status_code == 403


async def test_register_short_password(client: AsyncClient) -> None:
    r = await client.post(
        REGISTER_URL, json={**USER, "email": "short@example.com", "password": "short"}
    )
    assert r.status_code == 422


async def test_me_invalid_token(client: AsyncClient) -> None:
    r = await client.get(ME_URL, headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"
