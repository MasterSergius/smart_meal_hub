import pytest
from httpx import AsyncClient


async def test_rate_recipe(client: AsyncClient) -> None:
    ...


async def test_rate_own_recipe_forbidden(client: AsyncClient) -> None:
    ...


async def test_rating_updates_avg(client: AsyncClient) -> None:
    ...


async def test_rerate_overwrites_previous(client: AsyncClient) -> None:
    ...


async def test_rate_nonexistent_recipe(client: AsyncClient) -> None:
    ...
