import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import ForbiddenError, NotFoundError
from app.models.recipe import Recipe
from app.models.user import User
from app.schemas.recipe import RecipeCreate, RecipeOut, RecipeSearchOut, RecipeSearchParams


async def create_recipe(db: AsyncSession, data: RecipeCreate, author: User) -> Recipe:
    """Persist a new recipe owned by ``author`` and return it with ``author`` loaded.

    Input is already validated by ``RecipeCreate`` (lengths and ranges match the DB
    columns), so no error handling is needed here: anything unexpected is a real
    server error and is handled by the global SQLAlchemyError handler. The recipe is
    re-read through ``get_recipe`` so the ``author`` relationship is eagerly loaded,
    because lazy loading is not possible with an async session.
    """
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
    return await get_recipe(db, recipe.id)


async def get_recipe(db: AsyncSession, recipe_id: uuid.UUID) -> Recipe:
    """Load one recipe by id, with its ``author`` eagerly loaded via ``selectinload``.

    ``populate_existing`` refreshes the object if it is already in the session's
    identity map, so callers always see the current DB state (e.g. server-generated
    timestamps right after an insert).

    Raises:
        NotFoundError: no recipe with that id.
    """
    result = await db.execute(
        select(Recipe)
        .options(selectinload(Recipe.author))
        .where(Recipe.id == recipe_id)
        .execution_options(populate_existing=True)
    )
    recipe = result.scalar_one_or_none()
    if not recipe:
        raise NotFoundError("Recipe not found")
    return recipe


async def delete_recipe(db: AsyncSession, recipe_id: uuid.UUID, current_user: User) -> None:
    """Delete a recipe; only its author may do so.

    Its ratings are removed too, by the ``ON DELETE CASCADE`` on ``recipe_ratings``
    and the ORM ``delete-orphan`` cascade on ``Recipe.ratings``.

    Raises:
        NotFoundError: no recipe with that id.
        ForbiddenError: ``current_user`` is not the recipe's author.
    """
    recipe = await get_recipe(db, recipe_id)
    if recipe.author_id != current_user.id:
        raise ForbiddenError("Not the author")
    await db.delete(recipe)
    await db.commit()


def _escape_like(value: str) -> str:
    """Escape LIKE/ILIKE wildcards so user text is matched literally.

    Without this, ``q="%"`` would match every recipe and ``_`` would match any single
    character. Must be used together with ``escape="\\\\"`` on the ``ilike`` call.
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def search_recipes(db: AsyncSession, params: RecipeSearchParams) -> RecipeSearchOut:
    """Filter, sort and paginate recipes.

    Parameter bounds are validated by ``RecipeSearchParams``. The query is built up
    one optional filter at a time (all combined with AND):

    - ``q``: case-insensitive substring match on title or description
      (wildcards in the input are escaped and matched literally).
    - ``diet_tags``: comma-separated; the recipe must have *all* of them
      (Postgres array containment, ``diet_tags @> ARRAY[...]``).
    - ``cuisine``: case-insensitive exact match.
    - ``max_total_time``: prep + cook minutes, a missing value counting as 0.
    - ``min_rating``: minimum ``avg_rating``; unrated recipes are excluded.

    ``total`` is counted on the filtered query before pagination. Results are ordered
    by rating (unrated last) and then newest first.
    """
    query = select(Recipe).options(selectinload(Recipe.author))

    if params.q:
        term = f"%{_escape_like(params.q)}%"
        query = query.where(
            or_(Recipe.title.ilike(term, escape="\\"), Recipe.description.ilike(term, escape="\\"))
        )

    if params.diet_tags:
        tags = [t.strip() for t in params.diet_tags.split(",") if t.strip()]
        if tags:
            query = query.where(Recipe.diet_tags.contains(tags))

    if params.cuisine:
        query = query.where(func.lower(Recipe.cuisine) == params.cuisine.lower())

    if params.max_total_time is not None:
        total_time = func.coalesce(Recipe.prep_time_min, 0) + func.coalesce(Recipe.cook_time_min, 0)
        query = query.where(total_time <= params.max_total_time)

    if params.min_rating is not None:
        query = query.where(Recipe.avg_rating >= params.min_rating)

    # count before pagination
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    query = (
        query.order_by(Recipe.avg_rating.desc().nulls_last(), Recipe.created_at.desc())
        .offset((params.page - 1) * params.limit)
        .limit(params.limit)
    )
    result = await db.execute(query)
    recipes = result.scalars().all()

    items = [to_recipe_out(r) for r in recipes]
    return RecipeSearchOut(total=total, page=params.page, limit=params.limit, items=items)


def to_recipe_out(recipe: Recipe) -> RecipeOut:
    """Convert an ORM ``Recipe`` (with ``author`` loaded) into the ``RecipeOut`` schema.

    Adds the derived ``total_time_min`` (prep + cook, ``None`` when both are missing)
    and converts ``avg_rating`` from ``Decimal`` (a Postgres NUMERIC) to ``float``.
    """
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
