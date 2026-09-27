import pytest
from httpx import AsyncClient


async def test_add_recipe(client: AsyncClient) -> None:
    ...


async def test_add_recipe_unauthenticated(client: AsyncClient) -> None:
    ...


async def test_get_recipe(client: AsyncClient) -> None:
    ...


async def test_get_recipe_not_found(client: AsyncClient) -> None:
    ...


async def test_delete_recipe_by_author(client: AsyncClient) -> None:
    ...


async def test_delete_recipe_by_non_author(client: AsyncClient) -> None:
    ...


async def test_search_no_params(client: AsyncClient) -> None:
    ...


async def test_search_by_text(client: AsyncClient) -> None:
    ...


async def test_search_by_diet_tags(client: AsyncClient) -> None:
    ...


async def test_search_max_total_time(client: AsyncClient) -> None:
    ...
