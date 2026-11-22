import uuid
from typing import Annotated

from fastapi import APIRouter, Body, Path, Query, status

from app.constants import MealType
from app.dependencies import CurrentUser, DbSession
from app.schemas.menu import (
    MenuGenerateIn,
    MenuListOut,
    MenuListParams,
    MenuOut,
    MenuPatchIn,
    MenuSlotOut,
    SlotReplaceIn,
)
from app.services import menu as menu_service

router = APIRouter()


@router.post("/generate", response_model=MenuOut, status_code=status.HTTP_201_CREATED)
async def generate_menu(
    current_user: CurrentUser,
    db: DbSession,
    data: Annotated[MenuGenerateIn | None, Body()] = None,
) -> MenuOut:
    """``POST /menus/generate``: build and store a 7-day menu (FR-1.1).

    The body is optional; missing fields come from the user's preferences. Always
    returns 201 when the input is valid, with ``warnings`` if some slots repeat a
    dish or stay empty (D-2).
    """
    return await menu_service.generate_menu(db, current_user, data or MenuGenerateIn())


@router.get("", response_model=MenuListOut)
async def list_menus(
    params: Annotated[MenuListParams, Query()], current_user: CurrentUser, db: DbSession
) -> MenuListOut:
    """``GET /menus``: the caller's menus, newest first (MENU-2)."""
    return await menu_service.list_menus(db, current_user, params)


@router.get("/{menu_id}", response_model=MenuOut)
async def get_menu(menu_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> MenuOut:
    """``GET /menus/{menu_id}``: one menu with scaled ingredients; 404 if not the owner's."""
    return await menu_service.get_menu(db, current_user, menu_id)


@router.patch("/{menu_id}", response_model=MenuOut)
async def update_menu(
    menu_id: uuid.UUID, data: MenuPatchIn, current_user: CurrentUser, db: DbSession
) -> MenuOut:
    """``PATCH /menus/{menu_id}``: change the number of servings (FR-1.3)."""
    return await menu_service.update_servings(db, current_user, menu_id, data.servings)


@router.delete("/{menu_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_menu(menu_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> None:
    """``DELETE /menus/{menu_id}``: delete a menu (MENU-3); 404 if not the owner's."""
    await menu_service.delete_menu(db, current_user, menu_id)


@router.post("/{menu_id}/slots/{day}/{meal_type}/replace", response_model=MenuSlotOut)
async def replace_slot(
    menu_id: uuid.UUID,
    day: Annotated[int, Path(ge=1, le=7)],
    meal_type: MealType,
    current_user: CurrentUser,
    db: DbSession,
    data: Annotated[SlotReplaceIn | None, Body()] = None,
) -> MenuSlotOut:
    """``POST /menus/{id}/slots/{day}/{meal_type}/replace``: swap one dish (FR-1.2).

    Without a body a new recipe is picked automatically (MENU-4, 409 if none is
    left); with ``{"recipe_id": ...}`` that recipe is used (MENU-6).
    """
    recipe_id = data.recipe_id if data else None
    return await menu_service.replace_slot(db, current_user, menu_id, day, meal_type, recipe_id)
