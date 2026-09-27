# SmartMeal Hub — v0.1.0 Specification
## Stage 1: Recipe Catalog API

**Version:** 0.1.0  
**Stage:** 1 of 4  
**Scope:** Core recipe catalog with CRUD, rating, and search

---

## 1. Overview

v0.1.0 delivers the foundational recipe catalog service. It is the prerequisite for all future stages — menu generation (v0.2.0) and pantry matching (v0.3.0) both depend on a stable, queryable recipe store.

**Goals for this version:**
- Users can register and authenticate.
- Authenticated users can add and delete their own recipes.
- Any user (including anonymous) can search and view recipes.
- Authenticated users can rate recipes (1–5 stars).
- Public API surface is stable enough for the frontend to consume.

**Out of scope for v0.1.0:**
- Menu generation
- Pantry / shopping list management
- Admin moderation tools
- Image upload (accept URL only)

---

## 2. Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.12 | |
| Framework | FastAPI | Auto-generates OpenAPI docs at `/docs` |
| Database | PostgreSQL 16 | Via `asyncpg` + SQLAlchemy 2.x (async) |
| Auth | JWT (HS256) | `python-jose`, tokens via `Authorization: Bearer` |
| Migrations | Alembic | |
| Containerization | Docker + docker-compose | Single service for v0.1.0; split in v0.4.0 |
| Testing | pytest + httpx | At least happy-path coverage per endpoint |

> Microservice split is deferred to Stage 4. v0.1.0 is a single deployable service.

---

## 3. Database Schema

### 3.1 `users`

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK, default gen_random_uuid() |
| `email` | VARCHAR(255) | UNIQUE, NOT NULL |
| `password_hash` | VARCHAR(255) | NOT NULL |
| `display_name` | VARCHAR(100) | NOT NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL, default now() |

### 3.2 `recipes`

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK, default gen_random_uuid() |
| `author_id` | UUID | FK → users.id, NOT NULL |
| `title` | VARCHAR(200) | NOT NULL |
| `description` | TEXT | |
| `ingredients` | JSONB | NOT NULL — see §3.4 |
| `steps` | JSONB | NOT NULL — ordered array of strings |
| `diet_tags` | VARCHAR(50)[] | e.g. `{vegetarian, keto, low-calorie}` |
| `cuisine` | VARCHAR(100) | e.g. `Italian`, `Asian` |
| `servings` | SMALLINT | NOT NULL, default 2 |
| `prep_time_min` | SMALLINT | minutes |
| `cook_time_min` | SMALLINT | minutes |
| `image_url` | TEXT | optional |
| `avg_rating` | NUMERIC(3,2) | denormalized, updated on rating change |
| `rating_count` | INTEGER | NOT NULL, default 0 |
| `created_at` | TIMESTAMPTZ | NOT NULL, default now() |
| `updated_at` | TIMESTAMPTZ | NOT NULL, default now() |

### 3.3 `recipe_ratings`

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK, default gen_random_uuid() |
| `recipe_id` | UUID | FK → recipes.id ON DELETE CASCADE |
| `user_id` | UUID | FK → users.id |
| `score` | SMALLINT | NOT NULL, CHECK (score BETWEEN 1 AND 5) |
| `comment` | TEXT | optional |
| `created_at` | TIMESTAMPTZ | NOT NULL, default now() |
| | | UNIQUE (recipe_id, user_id) — one rating per user per recipe |

### 3.4 `ingredients` JSONB shape

```json
[
  { "name": "chicken breast", "amount": 500, "unit": "g" },
  { "name": "garlic", "amount": 3, "unit": "cloves" }
]
```

Required fields per item: `name` (string), `amount` (number > 0), `unit` (string).

---

## 4. API Specification

**Base path:** `/api/v1`  
**Content-Type:** `application/json`  
**Auth header:** `Authorization: Bearer <jwt_token>`

---

### 4.1 Auth

#### `POST /auth/register`
Register a new user.

**Request body:**
```json
{
  "email": "user@example.com",
  "password": "min8chars",
  "display_name": "Jane"
}
```

**Responses:**
| Status | Description |
|---|---|
| 201 | User created — returns `UserOut` |
| 409 | Email already registered |
| 422 | Validation error |

---

#### `POST /auth/login`
Authenticate and receive a JWT.

**Request body:**
```json
{
  "email": "user@example.com",
  "password": "min8chars"
}
```

**Responses:**
| Status | Body |
|---|---|
| 200 | `{ "access_token": "...", "token_type": "bearer" }` |
| 401 | Invalid credentials |

Token expiry: **24 hours**.

---

#### `GET /auth/me`
Return the current authenticated user's profile.

**Auth:** Required  
**Response 200:** `UserOut`

---

### 4.2 Recipes

#### `POST /recipes` — Add Recipe
Create a new recipe. The authenticated user becomes the author.

**Auth:** Required

**Request body:**
```json
{
  "title": "Garlic Butter Chicken",
  "description": "Quick weeknight dinner.",
  "ingredients": [
    { "name": "chicken breast", "amount": 500, "unit": "g" },
    { "name": "butter", "amount": 50, "unit": "g" },
    { "name": "garlic", "amount": 4, "unit": "cloves" }
  ],
  "steps": [
    "Season chicken with salt and pepper.",
    "Melt butter in a pan over medium heat.",
    "Cook chicken 6 min per side until golden."
  ],
  "diet_tags": ["low-calorie"],
  "cuisine": "American",
  "servings": 2,
  "prep_time_min": 10,
  "cook_time_min": 15,
  "image_url": "https://example.com/photo.jpg"
}
```

**Required fields:** `title`, `ingredients` (min 1 item), `steps` (min 1 step), `servings`  
**Optional:** all others

**Responses:**
| Status | Description |
|---|---|
| 201 | Recipe created — returns `RecipeOut` |
| 401 | Not authenticated |
| 422 | Validation error |

---

#### `GET /recipes/{id}` — Get Recipe
Fetch a single recipe by ID.

**Auth:** Not required

**Responses:**
| Status | Description |
|---|---|
| 200 | `RecipeOut` |
| 404 | Recipe not found |

---

#### `DELETE /recipes/{id}` — Delete Recipe
Delete a recipe. Only the author can delete their own recipe.

**Auth:** Required

**Responses:**
| Status | Description |
|---|---|
| 204 | Deleted successfully |
| 401 | Not authenticated |
| 403 | Not the author |
| 404 | Recipe not found |

---

#### `POST /recipes/{id}/ratings` — Rate Recipe
Submit or update a rating. A user can rate a recipe only once; submitting again overwrites the previous rating.

**Auth:** Required

**Request body:**
```json
{
  "score": 4,
  "comment": "Great recipe, a bit salty for my taste."
}
```

**Required:** `score` (integer 1–5)  
**Optional:** `comment`

**Responses:**
| Status | Description |
|---|---|
| 200 | Rating saved — returns `RatingOut` with updated `avg_rating` |
| 401 | Not authenticated |
| 403 | Author cannot rate their own recipe |
| 404 | Recipe not found |
| 422 | Validation error (score out of range) |

`avg_rating` and `rating_count` on the recipe are recalculated atomically on every rating write.

---

#### `GET /recipes/search` — Search Recipes
Search and filter the recipe catalog. Available to all users.

**Auth:** Not required

**Query parameters:**

| Parameter | Type | Description |
|---|---|---|
| `q` | string | Full-text search on title + description. Optional. |
| `diet_tags` | string (comma-separated) | Filter by tags, e.g. `vegetarian,keto`. AND logic. |
| `cuisine` | string | Filter by cuisine (case-insensitive). |
| `max_total_time` | integer | Max prep + cook time in minutes. |
| `min_rating` | float | Minimum avg_rating, e.g. `3.5`. |
| `page` | integer | Page number, default `1`. |
| `limit` | integer | Results per page, default `20`, max `100`. |

**Example:**
```
GET /api/v1/recipes/search?q=chicken&diet_tags=low-calorie&max_total_time=30&min_rating=4&page=1&limit=20
```

**Response 200:**
```json
{
  "total": 42,
  "page": 1,
  "limit": 20,
  "items": [ /* array of RecipeOut */ ]
}
```

Search with no parameters returns all recipes sorted by `avg_rating DESC`, then `created_at DESC`.

---

## 5. Response Schemas

### `UserOut`
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "display_name": "Jane",
  "created_at": "2026-09-27T10:00:00Z"
}
```

### `RecipeOut`
```json
{
  "id": "uuid",
  "author": { "id": "uuid", "display_name": "Jane" },
  "title": "Garlic Butter Chicken",
  "description": "...",
  "ingredients": [ { "name": "...", "amount": 500, "unit": "g" } ],
  "steps": ["Step 1", "Step 2"],
  "diet_tags": ["low-calorie"],
  "cuisine": "American",
  "servings": 2,
  "prep_time_min": 10,
  "cook_time_min": 15,
  "total_time_min": 25,
  "image_url": "https://...",
  "avg_rating": 4.25,
  "rating_count": 8,
  "created_at": "2026-09-27T10:00:00Z",
  "updated_at": "2026-09-27T10:00:00Z"
}
```

### `RatingOut`
```json
{
  "id": "uuid",
  "recipe_id": "uuid",
  "score": 4,
  "comment": "Great!",
  "created_at": "2026-09-27T10:00:00Z",
  "recipe_avg_rating": 4.25,
  "recipe_rating_count": 9
}
```

---

## 6. Non-Functional Requirements (v0.1.0 scope)

| ID | Requirement |
|---|---|
| NFR-01 | `GET /recipes/search` must respond in < 500ms for up to 10,000 recipes. |
| NFR-02 | Passwords must be hashed with bcrypt (min cost factor 12). |
| NFR-03 | JWT secret must be injected via environment variable `JWT_SECRET`. |
| NFR-04 | Service must run via `docker-compose up` with no manual setup. |
| NFR-05 | OpenAPI schema available at `/docs` (FastAPI auto-generated). |
| NFR-06 | Database connection string injected via `DATABASE_URL` env var. |

---

## 7. Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL DSN, e.g. `postgresql+asyncpg://user:pass@db:5432/smarthub` |
| `JWT_SECRET` | Yes | Secret key for signing tokens |
| `JWT_EXPIRE_HOURS` | No | Token lifetime, default `24` |

---

## 8. Project Structure

```
smart_meal_hub/
├── app/
│   ├── main.py            # FastAPI app factory
│   ├── config.py          # Settings from env vars
│   ├── database.py        # Async engine + session
│   ├── models/            # SQLAlchemy ORM models
│   │   ├── user.py
│   │   ├── recipe.py
│   │   └── rating.py
│   ├── schemas/           # Pydantic request/response schemas
│   │   ├── user.py
│   │   ├── recipe.py
│   │   └── rating.py
│   ├── routers/           # FastAPI routers
│   │   ├── auth.py
│   │   ├── recipes.py
│   │   └── ratings.py
│   ├── services/          # Business logic
│   │   ├── auth.py        # Password hashing, JWT
│   │   ├── recipe.py      # CRUD + search logic
│   │   └── rating.py      # Rating upsert + avg recalc
│   └── dependencies.py    # get_current_user, get_db
├── alembic/               # DB migrations
├── tests/
│   ├── test_auth.py
│   ├── test_recipes.py
│   └── test_ratings.py
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## 9. Definition of Done

- [ ] All 8 endpoints implemented and return correct HTTP status codes.
- [ ] `avg_rating` and `rating_count` are consistent after concurrent rating operations.
- [ ] Author cannot rate their own recipe (returns 403).
- [ ] Anonymous users can call search and get recipe by ID; all write operations return 401 without a valid token.
- [ ] At least one passing test per endpoint (happy path).
- [ ] `docker-compose up` starts service + postgres with no errors; migrations run automatically.
- [ ] `/docs` renders full OpenAPI schema.
- [ ] No plaintext passwords stored or logged.
