"""
Seed the database with a demo user and sample recipes.
Run via: make seed  (locally) or make docker-seed (in Docker)
"""
import asyncio
import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://smarthub:smarthub@localhost:5432/smarthub")
os.environ.setdefault("JWT_SECRET", "seed-secret")

from app.database import AsyncSessionLocal
from app.services.auth import hash_password
from app.models.user import User
from app.models.recipe import Recipe

DEMO_USER = {
    "email": "chef@example.com",
    "password": "password123",
    "display_name": "Chef Demo",
}

RECIPES = [
    {
        "title": "Garlic Butter Chicken",
        "description": "A quick and flavourful weeknight dinner ready in under 30 minutes.",
        "ingredients": [
            {"name": "chicken breast", "amount": 500, "unit": "g"},
            {"name": "butter", "amount": 50, "unit": "g"},
            {"name": "garlic", "amount": 4, "unit": "cloves"},
            {"name": "lemon juice", "amount": 2, "unit": "tbsp"},
            {"name": "fresh parsley", "amount": 10, "unit": "g"},
        ],
        "steps": [
            "Season chicken breasts with salt and pepper on both sides.",
            "Melt butter in a large skillet over medium-high heat.",
            "Add chicken and cook for 6 minutes per side until golden.",
            "Add minced garlic and cook for 1 minute until fragrant.",
            "Squeeze lemon juice over the chicken, garnish with parsley.",
        ],
        "diet_tags": ["low-calorie", "gluten-free"],
        "cuisine": "American",
        "servings": 2,
        "prep_time_min": 10,
        "cook_time_min": 15,
    },
    {
        "title": "Classic Margherita Pizza",
        "description": "Thin-crust pizza with fresh tomatoes, mozzarella, and basil.",
        "ingredients": [
            {"name": "pizza dough", "amount": 300, "unit": "g"},
            {"name": "tomato sauce", "amount": 150, "unit": "ml"},
            {"name": "fresh mozzarella", "amount": 200, "unit": "g"},
            {"name": "fresh basil", "amount": 15, "unit": "g"},
            {"name": "olive oil", "amount": 2, "unit": "tbsp"},
        ],
        "steps": [
            "Preheat oven to 250°C with a baking stone or tray inside.",
            "Roll dough into a thin round on a floured surface.",
            "Spread tomato sauce leaving a 2cm border.",
            "Tear mozzarella and scatter over the sauce.",
            "Bake for 10-12 minutes until crust is golden and cheese bubbles.",
            "Finish with fresh basil leaves and a drizzle of olive oil.",
        ],
        "diet_tags": ["vegetarian"],
        "cuisine": "Italian",
        "servings": 2,
        "prep_time_min": 20,
        "cook_time_min": 12,
    },
    {
        "title": "Avocado & Egg Breakfast Bowl",
        "description": "A nutritious high-protein breakfast ready in 10 minutes.",
        "ingredients": [
            {"name": "eggs", "amount": 2, "unit": "pcs"},
            {"name": "avocado", "amount": 1, "unit": "pcs"},
            {"name": "cherry tomatoes", "amount": 100, "unit": "g"},
            {"name": "feta cheese", "amount": 30, "unit": "g"},
            {"name": "olive oil", "amount": 1, "unit": "tbsp"},
            {"name": "red pepper flakes", "amount": 1, "unit": "pinch"},
        ],
        "steps": [
            "Fry or poach eggs to your liking.",
            "Halve the avocado, remove the pit, and slice.",
            "Arrange avocado, eggs, and cherry tomatoes in a bowl.",
            "Crumble feta on top, drizzle with olive oil.",
            "Season with red pepper flakes, salt, and pepper.",
        ],
        "diet_tags": ["vegetarian", "keto", "gluten-free", "low-calorie"],
        "cuisine": "American",
        "servings": 1,
        "prep_time_min": 5,
        "cook_time_min": 5,
    },
    {
        "title": "Thai Green Curry",
        "description": "Aromatic coconut curry with vegetables and jasmine rice.",
        "ingredients": [
            {"name": "green curry paste", "amount": 3, "unit": "tbsp"},
            {"name": "coconut milk", "amount": 400, "unit": "ml"},
            {"name": "tofu", "amount": 300, "unit": "g"},
            {"name": "zucchini", "amount": 200, "unit": "g"},
            {"name": "bell pepper", "amount": 1, "unit": "pcs"},
            {"name": "fish sauce", "amount": 2, "unit": "tbsp"},
            {"name": "jasmine rice", "amount": 300, "unit": "g"},
            {"name": "lime", "amount": 1, "unit": "pcs"},
        ],
        "steps": [
            "Cook jasmine rice according to package instructions.",
            "Fry curry paste in a wok over medium heat for 1 minute.",
            "Pour in coconut milk and bring to a gentle simmer.",
            "Add tofu, zucchini, and bell pepper; cook for 10 minutes.",
            "Season with fish sauce and a squeeze of lime.",
            "Serve over rice.",
        ],
        "diet_tags": ["vegetarian", "gluten-free"],
        "cuisine": "Asian",
        "servings": 3,
        "prep_time_min": 15,
        "cook_time_min": 20,
    },
    {
        "title": "Classic Caesar Salad",
        "description": "Crisp romaine lettuce with creamy Caesar dressing and croutons.",
        "ingredients": [
            {"name": "romaine lettuce", "amount": 300, "unit": "g"},
            {"name": "parmesan", "amount": 50, "unit": "g"},
            {"name": "croutons", "amount": 80, "unit": "g"},
            {"name": "Caesar dressing", "amount": 60, "unit": "ml"},
            {"name": "black pepper", "amount": 1, "unit": "pinch"},
        ],
        "steps": [
            "Wash and chop romaine into bite-sized pieces.",
            "Toss lettuce with Caesar dressing until evenly coated.",
            "Add croutons and shaved parmesan.",
            "Season with black pepper and serve immediately.",
        ],
        "diet_tags": ["vegetarian", "low-calorie"],
        "cuisine": "American",
        "servings": 2,
        "prep_time_min": 10,
        "cook_time_min": 0,
    },
]


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        # create demo user if not exists
        from sqlalchemy import select
        result = await db.execute(select(User).where(User.email == DEMO_USER["email"]))
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                email=DEMO_USER["email"],
                password_hash=hash_password(DEMO_USER["password"]),
                display_name=DEMO_USER["display_name"],
            )
            db.add(user)
            await db.flush()
            print(f"Created user: {DEMO_USER['email']} / {DEMO_USER['password']}")
        else:
            print(f"User already exists: {DEMO_USER['email']}")

        # add recipes that don't exist yet
        added = 0
        for payload in RECIPES:
            result = await db.execute(select(Recipe).where(Recipe.title == payload["title"]))
            if result.scalar_one_or_none():
                continue
            db.add(Recipe(author_id=user.id, **payload))
            added += 1

        await db.commit()
        print(f"Seeded {added} recipe(s). {len(RECIPES) - added} already existed.")


if __name__ == "__main__":
    asyncio.run(seed())
