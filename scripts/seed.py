"""
Seed the database with a demo user and sample recipes.
Run via: make seed  (locally) or make docker-seed (in Docker)
"""

import asyncio
import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://smarthub:smarthub@localhost:5432/smarthub"
)
os.environ.setdefault("JWT_SECRET", "seed-secret")
os.environ.setdefault("APP_ENV", "dev")

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.recipe import Recipe
from app.models.user import User
from app.services.auth import hash_password

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
        "meal_types": ["lunch", "dinner"],
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
        "meal_types": ["lunch", "dinner"],
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
        "meal_types": ["breakfast"],
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
        "meal_types": ["lunch", "dinner"],
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
        "meal_types": ["lunch"],
        "cuisine": "American",
        "servings": 2,
        "prep_time_min": 10,
        "cook_time_min": 0,
    },
]


def _recipe(
    title: str,
    description: str,
    ingredients: list[tuple[str, float, str]],
    steps: list[str],
    diet_tags: list[str],
    cuisine: str,
    meal_types: list[str],
    servings: int = 2,
    prep: int = 10,
    cook: int = 20,
) -> dict:
    """Compact constructor for the v0.2 seed recipes below."""
    return {
        "title": title,
        "description": description,
        "ingredients": [{"name": n, "amount": a, "unit": u} for n, a, u in ingredients],
        "steps": steps,
        "diet_tags": diet_tags,
        "cuisine": cuisine,
        "meal_types": meal_types,
        "servings": servings,
        "prep_time_min": prep,
        "cook_time_min": cook,
    }


B, L, D = "breakfast", "lunch", "dinner"
VEG, VEGAN, KETO, LOWCAL, GF = "vegetarian", "vegan", "keto", "low-calorie", "gluten-free"

# spec v0.2.0 SEED-1: enough breakfasts, lunches and dinners (incl. a full vegetarian
# week without repeats) for menu generation to fill every slot.
RECIPES += [
    # ── Breakfast ──────────────────────────────────────────────────────────────
    _recipe(
        "Overnight Oats with Berries",
        "No-cook oats soaked in milk overnight, topped with fresh berries.",
        [("rolled oats", 80, "g"), ("milk", 200, "ml"), ("blueberry", 60, "g"),
         ("honey", 1, "tbsp")],
        ["Mix oats and milk in a jar.", "Refrigerate overnight.", "Top with berries and honey."],
        [VEG], "American", [B], servings=1, prep=5, cook=0,
    ),
    _recipe(
        "Syrniki",
        "Golden cottage cheese pancakes, a Ukrainian breakfast classic.",
        [("cottage cheese", 400, "g"), ("egg", 1, "pcs"), ("flour", 60, "g"),
         ("sugar", 2, "tbsp"), ("sour cream", 100, "g")],
        ["Mix cottage cheese, egg, sugar and flour.", "Shape small patties.",
         "Fry 3 minutes per side; serve with sour cream."],
        [VEG], "Ukrainian", [B], prep=10, cook=15,
    ),
    _recipe(
        "Buckwheat Porridge with Milk",
        "Warm, nutty buckwheat simmered in milk.",
        [("buckwheat", 120, "g"), ("milk", 300, "ml"), ("butter", 10, "g"), ("salt", 1, "pinch")],
        ["Rinse buckwheat.", "Simmer in milk with salt for 20 minutes.", "Stir in butter."],
        [VEG, GF], "Ukrainian", [B], prep=5, cook=20,
    ),
    _recipe(
        "Spinach and Feta Omelette",
        "Fluffy three-egg omelette with wilted spinach and feta.",
        [("egg", 3, "pcs"), ("spinach", 50, "g"), ("feta cheese", 40, "g"),
         ("olive oil", 1, "tsp")],
        ["Wilt spinach in oil.", "Pour in beaten eggs.", "Add feta, fold and serve."],
        [VEG, KETO, GF, LOWCAL], "Mediterranean", [B], servings=1, prep=5, cook=8,
    ),
    _recipe(
        "Banana Peanut Butter Toast",
        "Wholegrain toast with peanut butter and sliced banana.",
        [("wholegrain bread", 2, "slices"), ("peanut butter", 2, "tbsp"), ("banana", 1, "pcs")],
        ["Toast the bread.", "Spread peanut butter.", "Top with banana slices."],
        [VEG, VEGAN], "American", [B], servings=1, prep=5, cook=3,
    ),
    _recipe(
        "Greek Yogurt Parfait",
        "Layers of yogurt, granola and seasonal fruit.",
        [("greek yogurt", 200, "g"), ("granola", 40, "g"), ("strawberry", 80, "g"),
         ("honey", 1, "tsp")],
        ["Layer yogurt, granola and fruit in a glass.", "Drizzle with honey."],
        [VEG, GF], "Greek", [B], servings=1, prep=5, cook=0,
    ),
    _recipe(
        "Shakshuka",
        "Eggs poached in a spiced tomato and pepper sauce.",
        [("egg", 4, "pcs"), ("tomato", 400, "g"), ("bell pepper", 1, "pcs"), ("onion", 1, "pcs"),
         ("garlic", 2, "cloves"), ("cumin", 1, "tsp")],
        ["Soften onion, pepper and garlic.", "Add tomatoes and cumin, simmer 10 minutes.",
         "Crack in eggs, cover and cook until set."],
        [VEG, GF], "Middle Eastern", [B, L], prep=10, cook=20,
    ),
    _recipe(
        "Apple Cinnamon Pancakes",
        "Soft pancakes with grated apple and cinnamon.",
        [("flour", 150, "g"), ("milk", 200, "ml"), ("egg", 1, "pcs"), ("apple", 1, "pcs"),
         ("cinnamon", 1, "tsp")],
        ["Whisk flour, milk and egg.", "Fold in grated apple and cinnamon.",
         "Fry small pancakes until golden."],
        [VEG], "American", [B], prep=10, cook=15,
    ),
    _recipe(
        "Smoked Salmon Scrambled Eggs",
        "Creamy scrambled eggs with smoked salmon and dill.",
        [("egg", 3, "pcs"), ("smoked salmon", 60, "g"), ("butter", 10, "g"), ("dill", 5, "g")],
        ["Scramble eggs gently in butter.", "Fold in salmon and dill off the heat."],
        [KETO, GF], "Scandinavian", [B], servings=1, prep=5, cook=5,
    ),
    # ── Vegetarian lunch & dinner ──────────────────────────────────────────────
    _recipe(
        "Vegetarian Borscht",
        "Ruby-red beet soup with cabbage, potato and sour cream.",
        [("beet", 2, "pcs"), ("cabbage", 300, "g"), ("potato", 2, "pcs"), ("carrot", 1, "pcs"),
         ("onion", 1, "pcs"), ("tomato paste", 2, "tbsp"), ("sour cream", 100, "g")],
        ["Simmer diced potato in 2 l of water.", "Sauté onion, carrot and grated beet with paste.",
         "Add cabbage and the sauté to the pot; cook 15 minutes.", "Serve with sour cream."],
        [VEG, GF], "Ukrainian", [L, D], servings=4, prep=20, cook=45,
    ),
    _recipe(
        "Potato Vareniki",
        "Dumplings filled with mashed potato and fried onion.",
        [("flour", 300, "g"), ("potato", 4, "pcs"), ("onion", 1, "pcs"), ("butter", 30, "g"),
         ("sour cream", 100, "g")],
        ["Make a dough from flour and water.", "Fill rounds with potato mash and onion.",
         "Boil until they float; serve with butter and sour cream."],
        [VEG], "Ukrainian", [L, D], servings=4, prep=40, cook=15,
    ),
    _recipe(
        "Mushroom Risotto",
        "Creamy arborio rice with mushrooms and parmesan.",
        [("arborio rice", 200, "g"), ("mushroom", 250, "g"), ("vegetable stock", 800, "ml"),
         ("onion", 1, "pcs"), ("parmesan", 40, "g"), ("butter", 20, "g")],
        ["Fry onion and mushrooms.", "Toast rice, then add stock ladle by ladle.",
         "Finish with butter and parmesan."],
        [VEG, GF], "Italian", [L, D], prep=10, cook=30,
    ),
    _recipe(
        "Red Lentil Soup",
        "Hearty spiced lentil soup with carrot and lemon.",
        [("red lentils", 200, "g"), ("carrot", 1, "pcs"), ("onion", 1, "pcs"),
         ("garlic", 2, "cloves"), ("cumin", 1, "tsp"), ("lemon", 1, "pcs")],
        ["Sauté onion, carrot and garlic.", "Add lentils, cumin and 1 l of water; simmer 25 min.",
         "Blend and add lemon juice."],
        [VEG, VEGAN, GF, LOWCAL], "Turkish", [L], servings=4, prep=10, cook=30,
    ),
    _recipe(
        "Chickpea Curry",
        "Chickpeas simmered in a coconut and tomato curry sauce.",
        [("chickpeas", 400, "g"), ("coconut milk", 400, "ml"), ("tomato", 200, "g"),
         ("onion", 1, "pcs"), ("curry paste", 2, "tbsp"), ("rice", 200, "g")],
        ["Fry onion with curry paste.", "Add tomato, chickpeas and coconut milk; simmer 15 min.",
         "Serve over rice."],
        [VEG, VEGAN, GF], "Indian", [L, D], servings=4, prep=10, cook=25,
    ),
    _recipe(
        "Tofu Vegetable Stir-Fry",
        "Crispy tofu with broccoli, pepper and soy-ginger sauce.",
        [("firm tofu", 300, "g"), ("broccoli", 200, "g"), ("bell pepper", 1, "pcs"),
         ("soy sauce", 3, "tbsp"), ("ginger", 10, "g"), ("rice", 150, "g")],
        ["Fry tofu cubes until crisp.", "Stir-fry vegetables with ginger.",
         "Toss with tofu and soy sauce; serve with rice."],
        [VEG, VEGAN], "Asian", [L, D], prep=15, cook=15,
    ),
    _recipe(
        "Caprese Pasta",
        "Pasta with cherry tomatoes, mozzarella and basil.",
        [("pasta", 200, "g"), ("cherry tomatoes", 250, "g"), ("mozzarella", 125, "g"),
         ("fresh basil", 10, "g"), ("olive oil", 2, "tbsp")],
        ["Cook pasta.", "Warm halved tomatoes in olive oil.",
         "Toss with pasta, mozzarella and basil."],
        [VEG], "Italian", [L, D], prep=5, cook=15,
    ),
    _recipe(
        "Stuffed Bell Peppers",
        "Peppers filled with rice, vegetables and herbs, baked in tomato sauce.",
        [("bell pepper", 4, "pcs"), ("rice", 150, "g"), ("carrot", 1, "pcs"), ("onion", 1, "pcs"),
         ("tomato sauce", 300, "ml"), ("parsley", 10, "g")],
        ["Cook rice with sautéed carrot and onion.", "Fill the peppers.",
         "Bake in tomato sauce at 180 °C for 40 minutes."],
        [VEG, GF], "Ukrainian", [D], servings=4, prep=20, cook=50,
    ),
    _recipe(
        "Pumpkin Cream Soup",
        "Velvety roasted pumpkin soup with a hint of ginger.",
        [("pumpkin", 800, "g"), ("onion", 1, "pcs"), ("vegetable stock", 700, "ml"),
         ("ginger", 10, "g"), ("coconut milk", 100, "ml")],
        ["Roast pumpkin chunks 25 minutes.", "Simmer with onion, ginger and stock.",
         "Blend with coconut milk."],
        [VEG, VEGAN, GF, LOWCAL], "European", [L], servings=4, prep=10, cook=40,
    ),
    _recipe(
        "Greek Salad",
        "Tomatoes, cucumber, olives and feta with oregano.",
        [("tomato", 2, "pcs"), ("cucumber", 1, "pcs"), ("red onion", 0.5, "pcs"),
         ("feta cheese", 100, "g"), ("olives", 50, "g"), ("olive oil", 2, "tbsp")],
        ["Chop the vegetables.", "Top with feta and olives.", "Dress with oil and oregano."],
        [VEG, GF, KETO, LOWCAL], "Greek", [L], prep=10, cook=0,
    ),
    _recipe(
        "Eggplant Parmigiana",
        "Layers of fried eggplant, tomato sauce and cheese.",
        [("eggplant", 2, "pcs"), ("tomato sauce", 400, "ml"), ("mozzarella", 200, "g"),
         ("parmesan", 50, "g"), ("fresh basil", 10, "g")],
        ["Slice and fry the eggplant.", "Layer with sauce and cheeses.",
         "Bake at 190 °C for 30 minutes."],
        [VEG, GF], "Italian", [D], servings=4, prep=20, cook=45,
    ),
    _recipe(
        "Zucchini Fritters",
        "Crispy zucchini pancakes with garlic yogurt dip.",
        [("zucchini", 2, "pcs"), ("egg", 1, "pcs"), ("flour", 50, "g"), ("dill", 5, "g"),
         ("greek yogurt", 100, "g"), ("garlic", 1, "cloves")],
        ["Grate and squeeze the zucchini.", "Mix with egg, flour and dill.",
         "Fry spoonfuls until golden; serve with garlic yogurt."],
        [VEG], "Ukrainian", [L], prep=15, cook=15,
    ),
    _recipe(
        "Black Bean Tacos",
        "Spiced black beans in corn tortillas with avocado and salsa.",
        [("black beans", 400, "g"), ("corn tortillas", 6, "pcs"), ("avocado", 1, "pcs"),
         ("tomato", 1, "pcs"), ("lime", 1, "pcs"), ("cumin", 1, "tsp")],
        ["Warm beans with cumin.", "Dice tomato and avocado with lime juice.",
         "Fill warm tortillas."],
        [VEG, VEGAN, GF], "Mexican", [L, D], prep=10, cook=10,
    ),
    _recipe(
        "Mushroom Holubtsi",
        "Cabbage rolls stuffed with rice and mushrooms, stewed in tomato sauce.",
        [("cabbage", 1, "pcs"), ("rice", 200, "g"), ("mushroom", 300, "g"), ("onion", 1, "pcs"),
         ("carrot", 1, "pcs"), ("tomato sauce", 400, "ml")],
        ["Blanch cabbage leaves.", "Fill with rice, mushrooms, onion and carrot.",
         "Stew rolls in tomato sauce for 45 minutes."],
        [VEG, GF], "Ukrainian", [L, D], servings=4, prep=30, cook=50,
    ),
    _recipe(
        "Spinach Lasagna",
        "Lasagna with spinach, ricotta and béchamel.",
        [("lasagna sheets", 250, "g"), ("spinach", 400, "g"), ("ricotta", 250, "g"),
         ("milk", 500, "ml"), ("flour", 40, "g"), ("parmesan", 50, "g")],
        ["Make béchamel with milk and flour.", "Layer sheets, spinach-ricotta and sauce.",
         "Bake at 190 °C for 35 minutes."],
        [VEG], "Italian", [D], servings=6, prep=25, cook=40,
    ),
    _recipe(
        "Cauliflower Steaks with Tahini",
        "Thick roasted cauliflower slices with lemon tahini sauce.",
        [("cauliflower", 1, "pcs"), ("tahini", 3, "tbsp"), ("lemon", 1, "pcs"),
         ("garlic", 1, "cloves"), ("olive oil", 2, "tbsp"), ("parsley", 10, "g")],
        ["Cut cauliflower into thick slices.", "Roast with olive oil at 220 °C for 25 minutes.",
         "Whisk tahini, lemon juice and garlic; spoon over and add parsley."],
        [VEG, VEGAN, GF, LOWCAL], "Middle Eastern", [D], prep=10, cook=25,
    ),
    _recipe(
        "Baked Potatoes with Mushrooms",
        "Jacket potatoes filled with fried mushrooms, onion and sour cream.",
        [("potato", 4, "pcs"), ("mushroom", 250, "g"), ("onion", 1, "pcs"),
         ("sour cream", 100, "g"), ("dill", 5, "g")],
        ["Bake potatoes at 200 °C for 50 minutes.", "Fry mushrooms with onion.",
         "Split potatoes, fill and top with sour cream and dill."],
        [VEG, GF], "Ukrainian", [D], prep=10, cook=50,
    ),
    # ── Meat & fish lunch & dinner ─────────────────────────────────────────────
    _recipe(
        "Chicken Kyiv",
        "Breaded chicken breast filled with herb garlic butter.",
        [("chicken breast", 2, "pcs"), ("butter", 60, "g"), ("garlic", 2, "cloves"),
         ("dill", 5, "g"), ("breadcrumbs", 80, "g"), ("egg", 1, "pcs")],
        ["Make herb butter and freeze it.", "Wrap butter in flattened chicken.",
         "Bread and fry, then bake 15 minutes at 190 °C."],
        [], "Ukrainian", [D], prep=30, cook=25,
    ),
    _recipe(
        "Baked Salmon with Broccoli",
        "Lemon-herb salmon fillets roasted with broccoli.",
        [("salmon fillet", 2, "pcs"), ("broccoli", 300, "g"), ("lemon", 1, "pcs"),
         ("olive oil", 2, "tbsp"), ("garlic", 2, "cloves")],
        ["Toss broccoli with oil and garlic.", "Add salmon and lemon slices.",
         "Roast at 200 °C for 15 minutes."],
        [KETO, GF, LOWCAL], "Mediterranean", [L, D], prep=10, cook=15,
    ),
    _recipe(
        "Beef Stroganoff",
        "Tender beef strips in a mushroom sour cream sauce.",
        [("beef sirloin", 400, "g"), ("mushroom", 200, "g"), ("onion", 1, "pcs"),
         ("sour cream", 150, "g"), ("butter", 20, "g")],
        ["Sear beef strips quickly.", "Cook onion and mushrooms.",
         "Stir in sour cream and beef; heat through."],
        [GF], "Eastern European", [D], prep=15, cook=20,
    ),
    _recipe(
        "Turkey Meatballs in Tomato Sauce",
        "Light turkey meatballs simmered in herby tomato sauce.",
        [("ground turkey", 500, "g"), ("egg", 1, "pcs"), ("breadcrumbs", 40, "g"),
         ("tomato sauce", 500, "ml"), ("garlic", 2, "cloves"), ("parsley", 10, "g")],
        ["Mix turkey, egg, breadcrumbs and parsley.", "Shape and brown the meatballs.",
         "Simmer in tomato sauce for 20 minutes."],
        [LOWCAL], "Italian", [L, D], servings=4, prep=15, cook=30,
    ),
    _recipe(
        "Chicken Noodle Soup",
        "Comforting broth with chicken, noodles and vegetables.",
        [("chicken thigh", 400, "g"), ("egg noodles", 150, "g"), ("carrot", 2, "pcs"),
         ("onion", 1, "pcs"), ("dill", 5, "g")],
        ["Simmer chicken with onion in 2 l of water for 30 min.", "Shred chicken; add carrot.",
         "Add noodles for the last 8 minutes; finish with dill."],
        [LOWCAL], "Ukrainian", [L], servings=4, prep=10, cook=45,
    ),
    _recipe(
        "Pork Chops with Apples",
        "Pan-seared pork chops with caramelised apple and onion.",
        [("pork chop", 2, "pcs"), ("apple", 2, "pcs"), ("onion", 1, "pcs"), ("butter", 20, "g"),
         ("thyme", 2, "sprigs")],
        ["Sear chops 4 minutes per side; rest.", "Cook sliced apple and onion in butter.",
         "Serve the chops over the apples."],
        [GF, KETO], "European", [D], prep=10, cook=20,
    ),
    _recipe(
        "Shrimp Fried Rice",
        "Wok-fried rice with shrimp, peas and egg.",
        [("cooked rice", 400, "g"), ("shrimp", 250, "g"), ("pea", 100, "g"), ("egg", 2, "pcs"),
         ("soy sauce", 2, "tbsp"), ("green onion", 2, "pcs")],
        ["Scramble eggs and set aside.", "Stir-fry shrimp and peas.",
         "Add rice, soy sauce, eggs and green onion."],
        [], "Asian", [L, D], prep=10, cook=12,
    ),
    _recipe(
        "Tuna Nicoise Salad",
        "Tuna, potato, green beans, egg and olives with vinaigrette.",
        [("canned tuna", 1, "cans"), ("potato", 2, "pcs"), ("green beans", 150, "g"),
         ("egg", 2, "pcs"), ("olives", 40, "g"), ("tomato", 1, "pcs")],
        ["Boil potatoes, beans and eggs.", "Arrange with tuna, olives and tomato.",
         "Dress with vinaigrette."],
        [GF, LOWCAL], "French", [L], prep=15, cook=15,
    ),
]


async def seed() -> None:
    """Insert the demo user and sample recipes. Safe to run repeatedly.

    The user is looked up by email and each recipe by title; only missing ones are
    created, so re-running never duplicates data. Everything is committed in one
    transaction at the end.
    """
    async with AsyncSessionLocal() as db:
        # create demo user if not exists
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
            existing = result.scalar_one_or_none()
            if existing:
                # recipes seeded before v0.2 got the migration's default meal types
                existing.meal_types = payload["meal_types"]
                continue
            db.add(Recipe(author_id=user.id, **payload))
            added += 1

        await db.commit()
        print(f"Seeded {added} recipe(s). {len(RECIPES) - added} already existed.")


if __name__ == "__main__":
    asyncio.run(seed())
