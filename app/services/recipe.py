import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.recipe import Recipe
from app.models.user import User
from app.schemas.recipe import RecipeCreate, RecipeOut, RecipeSearchOut, RecipeSearchParams


async def create_recipe(db: AsyncSession, data: RecipeCreate, author: User) -> Recipe:
    recipe = Recipe(
        author_id=author.id,
        title=data.title,
        description=data.description,
        ingredients=[i.model_dump() for i in data.ingredients],
        steps=data.steps,
        diet_tags=data.diet_tags,
        cuisine=data.cuisine,
        servings=data.servings,
        prep_time_min=data.prep_time_min,
        cook_time_min=data.cook_time_min,
        image_url=data.image_url,
    )
    db.add(recipe)
    await db.commit()
    await db.refresh(recipe)
    # reload with author relationship
    return await get_recipe(db, recipe.id)


async def get_recipe(db: AsyncSession, recipe_id: uuid.UUID) -> Recipe:
    result = await db.execute(
        select(Recipe).options(selectinload(Recipe.author)).where(Recipe.id == recipe_id)
    )
    recipe = result.scalar_one_or_none()
    if not recipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")
    return recipe


async def delete_recipe(db: AsyncSession, recipe_id: uuid.UUID, current_user: User) -> None:
    recipe = await get_recipe(db, recipe_id)
    if recipe.author_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the author")
    await db.delete(recipe)
    await db.commit()


async def search_recipes(db: AsyncSession, params: RecipeSearchParams) -> RecipeSearchOut:
    query = select(Recipe).options(selectinload(Recipe.author))

    if params.q:
        term = f"%{params.q}%"
        query = query.where(
            or_(Recipe.title.ilike(term), Recipe.description.ilike(term))
        )

    if params.diet_tags:
        tags = [t.strip() for t in params.diet_tags.split(",") if t.strip()]
        for tag in tags:
            query = query.where(Recipe.diet_tags.contains([tag]))

    if params.cuisine:
        query = query.where(func.lower(Recipe.cuisine) == params.cuisine.lower())

    if params.max_total_time is not None:
        total = func.coalesce(Recipe.prep_time_min, 0) + func.coalesce(Recipe.cook_time_min, 0)
        query = query.where(total <= params.max_total_time)

    if params.min_rating is not None:
        query = query.where(Recipe.avg_rating >= params.min_rating)

    # count before pagination
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    query = (
        query
        .order_by(Recipe.avg_rating.desc().nulls_last(), Recipe.created_at.desc())
        .offset((params.page - 1) * params.limit)
        .limit(params.limit)
    )
    result = await db.execute(query)
    recipes = result.scalars().all()

    items = [_to_out(r) for r in recipes]
    return RecipeSearchOut(total=total, page=params.page, limit=params.limit, items=items)


def _to_out(recipe: Recipe) -> RecipeOut:
    prep = recipe.prep_time_min or 0
    cook = recipe.cook_time_min or 0
    total = (prep + cook) or None
    return RecipeOut(
        id=recipe.id,
        author=recipe.author,
        title=recipe.title,
        description=recipe.description,
        ingredients=recipe.ingredients,
        steps=recipe.steps,
        diet_tags=recipe.diet_tags,
        cuisine=recipe.cuisine,
        servings=recipe.servings,
        prep_time_min=recipe.prep_time_min,
        cook_time_min=recipe.cook_time_min,
        total_time_min=total,
        image_url=recipe.image_url,
        avg_rating=float(recipe.avg_rating) if recipe.avg_rating is not None else None,
        rating_count=recipe.rating_count,
        created_at=recipe.created_at,
        updated_at=recipe.updated_at,
    )
