import pytest
from httpx import AsyncClient


async def test_register(client: AsyncClient) -> None:
    ...


async def test_register_duplicate_email(client: AsyncClient) -> None:
    ...


async def test_login_success(client: AsyncClient) -> None:
    ...


async def test_login_wrong_password(client: AsyncClient) -> None:
    ...


async def test_me_authenticated(client: AsyncClient) -> None:
    ...


async def test_me_unauthenticated(client: AsyncClient) -> None:
    ...
