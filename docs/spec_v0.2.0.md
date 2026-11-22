# SmartMeal Hub — v0.2.0 Specification
## Stage 2: Menu Generation Engine

**Version:** 0.2.0  
**Stage:** 2 of 4  
**Scope:** User preferences, weekly menu generation, one-click dish replacement, portion scaling, deployment readiness  
**Requirements covered:** FR-1.1, FR-1.2, FR-1.3, NFR-1 (see `project_requirements.md`)

Rule ids (`PREF-…`, `GEN-…`, `MENU-…`, `SCALE-…`, `OPS-…`) are referenced by tests and code.

---

## 0. Decisions

Proposed defaults. Each needs the owner's confirmation before implementation starts; once confirmed, mark it **Confirmed**.

| ID | Decision | Proposed default | Status |
|---|---|---|---|
| D-1 | How many diets a user can pick | A **list** of diet tags, all required (AND). Empty list = "balanced" (no diet filter). | **Confirmed** |
| D-2 | What happens when too few recipes match | Return a **partial menu**: repeat the least-used recipe first; if no recipe fits a meal type at all, leave the slot empty and add a warning. Never fail the whole request. | **Confirmed** |
| D-3 | Can a user pick a specific recipe for a slot that breaks their rules? | Yes, always — they may be cooking for somebody else. Diet and meal type aren't checked; a recipe with an excluded ingredient is **accepted with a warning** naming the ingredient. Automatic generation and replacement still never pick such recipes. | **Confirmed** |
| D-4 | Region used for seasonal produce | Region = ISO 3166-1 alpha-2 code. v0.2 ships seasonal data for **one region: `UA`**. Users with no region (or a region without data) get no seasonal scoring. | **Confirmed** |
| D-5 | Who can see a menu | Only its owner. Another user's menu returns **404**, not 403, so menu ids don't leak. | **Confirmed** |
| D-6 | Meal types of existing recipes | Migration backfills every existing recipe with `{lunch, dinner}`; authors can't edit recipes yet, so the seed sets correct values. | **Confirmed** |

---

## 1. Overview

v0.2.0 adds the first planning feature on top of the v0.1 recipe catalog: an authenticated user stores their dietary preferences and generates a 7-day menu (breakfast, lunch, dinner) that respects them. Any dish can be swapped in one click, and changing the number of people rescales every recipe's ingredients.

**Goals for this version:**
- Users can save diet, excluded ingredients (stop-list), household size and region.
- Users can generate, list, view, rescale and delete weekly menus.
- Users can replace a single dish — automatically or with a recipe of their choice.
- Generation is fast (≤ 2 s, NFR-1) and reproducible (same seed → same menu).
- The service is ready to be containerised for AWS (production image, readiness probe, safe config). The AWS deployment itself is a separate follow-up (`docs/deploy_aws.md`, written later).

**Out of scope for v0.2.0:**
- Pantry / fridge inventory and matching modes (FR-2.1, FR-2.2) — v0.3.0
- Unit conversion and aggregated shopping list (FR-2.3) — v0.3.0
- Nutrition / calorie targets
- Allergen groups (e.g. "dairy" expanding to milk, butter, cheese) — users list ingredients one by one
- Editing recipes (`PUT/PATCH /recipes/{id}`)
- Redis caching, microservice split — v0.4.0
- AWS infrastructure (tracked separately, see §10)

---

## 2. Changes to v0.1 behaviour

Findings in v0.1.1 that v0.2 depends on:

| # | Finding | Change in v0.2 |
|---|---|---|
| C-1 | `diet_tags` are stored as typed, so `Vegetarian` and `vegetarian` are different tags and search/generation miss recipes. | Diet tags are normalised (trimmed, lowercased) on create; a migration normalises existing rows. Search lowercases the requested tags too. |
| C-2 | Recipes have no notion of which meal they suit. | New `meal_types` column (§3.1). |
| C-3 | `GET /healthz` doesn't check the database, so a load balancer can't tell when the API can't serve requests. | New readiness probe `GET /readyz` (§9). `/healthz` stays as liveness. |
| C-4 | The app starts with the placeholder `JWT_SECRET=change-me-in-production`. | Refuse to start with a known placeholder or a secret shorter than 32 characters unless `APP_ENV=dev` (§9). |
| C-5 | Ingredient `amount` allows `0` although spec v0.1 says `> 0`. Scaling a 0 is harmless, so it stays; the spec text is corrected to `≥ 0`. | Doc only. |

---

## 3. Database Schema

New and changed tables. One Alembic migration per section is fine; all must apply on top of `ef720ce4bfe9_initial_schema`.

### 3.1 `recipes` (changed)

| Column | Type | Constraints |
|---|---|---|
| `meal_types` | VARCHAR(10)[] | NOT NULL, default `{lunch,dinner}`; values ⊆ {`breakfast`, `lunch`, `dinner`}, at least one |

- GIN index on `meal_types` and on `diet_tags` (generation filters on both).
- Migration: add column with default (D-6), lowercase + trim existing `diet_tags` (C-1).

### 3.2 `user_preferences` (new)

One row per user, created on first `PUT`.

| Column | Type | Constraints |
|---|---|---|
| `user_id` | UUID | PK, FK → users.id ON DELETE CASCADE |
| `diets` | VARCHAR(50)[] | NOT NULL, default `{}` — see PREF-2 |
| `excluded_ingredients` | VARCHAR(100)[] | NOT NULL, default `{}` — the stop-list |
| `household_size` | SMALLINT | NOT NULL, default 2, CHECK 1–20 |
| `region` | CHAR(2) | nullable, uppercase ISO 3166-1 alpha-2 |
| `updated_at` | TIMESTAMPTZ | NOT NULL, default now() |

### 3.3 `seasonal_produce` (new)

Reference data, loaded by the v0.2.0 migration (so every environment has it), not exposed through the API.

| Column | Type | Constraints |
|---|---|---|
| `id` | SERIAL | PK |
| `region` | CHAR(2) | NOT NULL |
| `name` | VARCHAR(100) | NOT NULL, normalised (see §6.1) |
| `months` | SMALLINT[] | NOT NULL, values 1–12 |
| | | UNIQUE (region, name) |

### 3.4 `menus` (new)

A menu stores a **snapshot** of the rules it was generated with, so replacing a dish later uses the same rules even if the user's preferences have changed.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `user_id` | UUID | FK → users.id ON DELETE CASCADE, indexed |
| `start_date` | DATE | NOT NULL — date of day 1 |
| `servings` | SMALLINT | NOT NULL, CHECK 1–20 |
| `diets` | VARCHAR(50)[] | NOT NULL — snapshot |
| `excluded_ingredients` | VARCHAR(100)[] | NOT NULL — snapshot |
| `region` | CHAR(2) | nullable — snapshot |
| `seed` | BIGINT | NOT NULL — random seed used for generation |
| `created_at` | TIMESTAMPTZ | NOT NULL, default now() |
| `updated_at` | TIMESTAMPTZ | NOT NULL, default now() |

### 3.5 `menu_slots` (new)

Exactly 21 rows per menu (7 days × 3 meals), created together with the menu.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `menu_id` | UUID | FK → menus.id ON DELETE CASCADE |
| `day` | SMALLINT | NOT NULL, CHECK 1–7 |
| `meal_type` | VARCHAR(10) | NOT NULL, one of `breakfast`, `lunch`, `dinner` |
| `recipe_id` | UUID | FK → recipes.id **ON DELETE SET NULL**, nullable (empty slot) |
| | | UNIQUE (menu_id, day, meal_type) |

Deleting a recipe empties the slots that used it (MENU-7).

---

## 4. Preferences

### Rules

- **PREF-1** A user without a preferences row gets the defaults: `diets=[]`, `excluded_ingredients=[]`, `household_size=2`, `region=null`.
- **PREF-2** `diets` values come from a fixed list: `vegetarian`, `vegan`, `keto`, `low-calorie`, `gluten-free`. Unknown values → 422. Duplicates are removed. An empty list means "balanced" (D-1).
- **PREF-3** `excluded_ingredients`: each item is normalised (§6.1), empty items are dropped, duplicates removed, max 50 items, each 1–100 characters. Order is kept.
- **PREF-4** `region` is uppercased; must be 2 letters. Unknown-but-valid codes are accepted (they just have no seasonal data).
- **PREF-5** `PUT` replaces the whole object (all fields optional in the body; missing fields reset to the PREF-1 defaults).

### API

#### `GET /users/me/preferences`
**Auth:** Required · **Response 200:** `PreferencesOut` · 401 without token.

#### `PUT /users/me/preferences`
**Auth:** Required

```json
{
  "diets": ["vegetarian"],
  "excluded_ingredients": ["Peanut", "shrimp "],
  "household_size": 3,
  "region": "ua"
}
```

| Status | Description |
|---|---|
| 200 | Saved — returns `PreferencesOut` (normalised: `["peanut", "shrimp"]`, `"UA"`) |
| 401 | Not authenticated |
| 422 | Validation error |

---

## 5. Recipes (changes)

- **REC-1** `POST /recipes` accepts optional `meal_types` (list, 1–3 distinct values from `breakfast|lunch|dinner`; default `["lunch", "dinner"]`). Invalid value or empty list → 422.
- **REC-2** `RecipeOut` gains `meal_types`.
- **REC-3** `GET /recipes/search` gains `meal_type` (single value). Invalid value → 422.
- **REC-4** Diet tags are normalised on create (C-1); search compares lowercased tags.

---

## 6. Menu Generation (FR-1.1)

### 6.1 Ingredient name matching

Used for the stop-list and for seasonal produce.

- **GEN-1** Normalise a name: trim, lowercase, collapse inner whitespace.
- **GEN-2** A term *matches* an ingredient if the term, or the term with `s`/`es` appended, appears in the ingredient name as whole words (not preceded or followed by a letter, digit or `_`). `peanut` matches `peanut butter` and `roasted peanuts`; `egg` matches `eggs`, but not `eggplant`; `nut` does not match `peanut`.
- Known limitation: no synonyms or allergen groups (`prawn` ≠ `shrimp`). Documented in the API description.

### 6.2 Eligibility (hard filters)

A recipe is a **candidate** for a slot only if all of these hold:

- **GEN-3** `meal_type` of the slot ∈ recipe `meal_types`.
- **GEN-4** Recipe `diet_tags` contain every diet in the menu's `diets`. Exception: `vegan` recipes also satisfy `vegetarian`.
- **GEN-5** No ingredient of the recipe matches any stop-list term (GEN-2).

### 6.3 Scoring (soft preferences)

Each candidate gets a weight; higher = more likely to be picked.

```
rating_part  = (avg_rating if rated else 3.0) / 5                       # 0.2 … 1.0
season_part  = in_season_produce / produce_in_recipe   (0 if none known)  # 0 … 1
weight       = 1.0 + RATING_W * rating_part + SEASON_W * season_part
RATING_W = 1.0, SEASON_W = 1.0   (module constants)
```

- **GEN-6** `in_season_produce`: recipe ingredients that match a `seasonal_produce` row for the menu's region whose `months` contain the month of that slot's date. `produce_in_recipe`: ingredients that match any row for that region. Ingredients not in the table are neutral.
- **GEN-7** Unrated recipes count as 3.0 so new recipes still appear.

### 6.4 Selection

- **GEN-8** Slots are filled in order: day 1 breakfast, lunch, dinner, day 2 …
- **GEN-9** For each slot, pick one candidate by weighted random choice using `random.Random(seed)`. The same seed, rules and recipe set always produce the same menu.
- **GEN-10** No recipe appears twice in a menu while unused candidates remain for that slot.
- **GEN-11** A candidate whose cuisine is already used on the same day has its weight multiplied by `0.3` (variety, soft).
- **GEN-12** If every candidate for a slot is already used, pick the least-used one (ties by weight); the menu then shows `"Some <meal> dishes repeat during the week"` (D-2, MENU-9).
- **GEN-13** If a slot has no candidate at all, leave it empty; the menu then shows `"Day <n> <meal>: no dish"` (D-2, MENU-9).
- **GEN-14** Generation loads all candidates in **one** query (filters GEN-3/GEN-4 in SQL; GEN-5 and scoring in Python, loading only the columns needed) plus one query for seasonal produce. No per-slot queries.
- **GEN-15** (NFR-1) `POST /menus/generate` responds in **≤ 2 s** with 10,000 recipes in the catalog.

### 6.5 API

#### `POST /menus/generate`
**Auth:** Required

All fields optional; each missing field comes from the user's preferences (PREF-1 defaults if none). Values given here are validated like PREF-2…PREF-4 but **not** saved to preferences.

```json
{
  "start_date": "2026-11-23",
  "servings": 4,
  "diets": ["vegetarian"],
  "excluded_ingredients": ["mushroom"],
  "region": "UA",
  "seed": 12345
}
```

- `start_date` default: today (UTC). Must be within −7 … +365 days of today, else 422.
- `servings` default: `household_size`. 1–20.
- `seed` default: random 63-bit integer. Stored on the menu and returned.

| Status | Description |
|---|---|
| 201 | Menu created — returns `MenuOut` (may contain `warnings` and empty slots) |
| 401 | Not authenticated |
| 422 | Validation error |

---

## 7. Menus

### Rules

- **MENU-1** Only the owner can read, change or delete a menu; for anyone else it doesn't exist (404, D-5).
- **MENU-2** `GET /menus` lists the caller's menus, newest `start_date` first, then newest `created_at`; paginated like search (`page`, `limit` ≤ 100).
- **MENU-3** `DELETE` removes the menu and its slots.
- **MENU-4** (FR-1.2) **Replace — automatic:** choose a new recipe for the slot using the menu's snapshot rules (GEN-3…GEN-11), excluding the slot's current recipe and every recipe already in the menu. If none is left, allow recipes already used elsewhere in the menu (still not the current one). If still none → 409 `"No alternative recipe available"`.
- **MENU-5** Automatic replacement uses a fresh random choice each call (not the menu seed), so repeated clicks give different dishes.
- **MENU-6** **Replace — chosen recipe:** body `{"recipe_id": "…"}`. The recipe must exist (404 otherwise). Diet, meal type and stop-list are not enforced (D-3): if the recipe matches a stop-list term (GEN-2), it is saved anyway and the slot gets a warning (MENU-9).
- **MENU-9** Warnings are computed on every read from the current slots, never stored:
  - slot level (`MenuSlotOut.warnings`): `"Contains excluded ingredient: <term>"` for each matched stop-list term;
  - menu level (`MenuOut.warnings`), in this order: every slot warning prefixed with its day and meal (`"Day 2 dinner: Contains excluded ingredient: peanut"`); one `"Some <meal> dishes repeat during the week"` per meal type with a repeated recipe (GEN-12); one `"Day <n> <meal>: no dish"` per empty slot (GEN-13, MENU-7).

  So a warning disappears as soon as the dish is replaced.
- **MENU-7** A slot whose recipe was deleted is returned with `recipe: null`; it can be refilled with replace.
- **MENU-8** Replacing a dish or changing servings updates the menu's `updated_at`.

### API

#### `GET /menus` → 200 `MenuListOut`
#### `GET /menus/{id}` → 200 `MenuOut` · 404
#### `PATCH /menus/{id}`
Body: `{"servings": 3}` (1–20). → 200 `MenuOut` · 404 · 422
#### `DELETE /menus/{id}` → 204 · 404
#### `POST /menus/{id}/slots/{day}/{meal_type}/replace`
`day` 1–7, `meal_type` ∈ `breakfast|lunch|dinner` (else 422). Body optional: `{"recipe_id": "uuid"}`.

| Status | Description |
|---|---|
| 200 | Returns the updated `MenuSlotOut` |
| 401 | Not authenticated |
| 404 | Menu not found (or not the owner); chosen recipe not found |
| 409 | No alternative recipe available |
| 422 | Bad day / meal type |

All menu endpoints require auth. As in v0.1, a request without an `Authorization` header gets **403** (FastAPI's `HTTPBearer`), and an invalid or expired token gets **401**; the 401 rows in the tables above mean "not authenticated" in that sense.

---

## 8. Portion Scaling (FR-1.3)

- **SCALE-1** Every slot in `MenuOut` carries `scaled_ingredients`: the recipe's ingredients with `amount × menu.servings / recipe.servings`.
- **SCALE-2** Countable units — `pc`, `pcs`, `piece`, `pieces`, `clove`, `cloves`, `slice`, `slices`, `egg`, `eggs`, `can`, `cans`, `bunch`, `bunches`, and an empty unit — are rounded **up** to a whole number (min 1 when the original amount > 0).
- **SCALE-3** All other units are rounded to 2 decimals. Unit names are kept as written; conversion is v0.3.
- **SCALE-4** Scaling is computed on read, never stored; changing `servings` (PATCH) is enough to rescale the whole menu.

Example: recipe for 2 with `3 cloves` garlic and `500 g` chicken, menu for 3 → `5 cloves` (4.5 rounded up), `750 g`.

---

## 9. Deployment Readiness

Prepares the service for AWS (ECS Fargate + RDS). The AWS setup itself is out of scope here.

- **OPS-1** `GET /readyz` runs `SELECT 1`; 200 `{"status": "ok"}` or 503 `{"status": "unavailable"}`. `/healthz` is unchanged.
- **OPS-2** New env var `APP_ENV` (`dev` | `prod`, default `prod`). In `prod`, startup fails if `JWT_SECRET` is shorter than 32 characters or is one of the known placeholders (`change-me-in-production`, `seed-secret`, `test-secret-key-not-for-production`).
- **OPS-3** `CORS_ORIGINS` (comma-separated, default empty = CORS disabled).
- **OPS-4** `LOG_FORMAT` (`text` | `json`, default `text`); `json` writes one JSON object per line to stdout (CloudWatch-friendly), including request method, path, status and duration.
- **OPS-5** Production Docker image (`Dockerfile` target `prod`, the default): multi-stage, `uv sync --frozen --no-dev`, runs as a non-root user, no source bind mount, `.dockerignore`, `HEALTHCHECK` on `/healthz`, `APP_ENV=prod` and `LOG_FORMAT=json` by default. The `dev` target adds dev dependencies; `docker-compose.yml` uses it and sets `APP_ENV=dev`. The virtualenv lives in `/opt/venv`, so bind-mounting the source doesn't hide it.
- **OPS-6** CI builds the image on every PR and checks migrations: `alembic upgrade head` on an empty DB, then `alembic check` (no pending model changes).

### Environment variables (additions)

| Variable | Required | Description |
|---|---|---|
| `APP_ENV` | No | `dev` or `prod`, default `prod` |
| `CORS_ORIGINS` | No | Comma-separated allowed origins |
| `LOG_FORMAT` | No | `text` or `json`, default `text` |

---

## 10. Response Schemas

### `PreferencesOut`
```json
{
  "diets": ["vegetarian"],
  "excluded_ingredients": ["peanut", "shrimp"],
  "household_size": 3,
  "region": "UA",
  "updated_at": "2026-11-22T10:00:00Z"
}
```
`updated_at` is `null` when the user has never saved preferences.

### `MenuOut`
```json
{
  "id": "uuid",
  "start_date": "2026-11-23",
  "servings": 4,
  "diets": ["vegetarian"],
  "excluded_ingredients": ["mushroom"],
  "region": "UA",
  "seed": 12345,
  "slots": [ /* 21 × MenuSlotOut, ordered by day then breakfast, lunch, dinner */ ],
  "warnings": ["Some breakfast dishes repeat during the week"],
  "created_at": "2026-11-22T10:00:00Z",
  "updated_at": "2026-11-22T10:00:00Z"
}
```
`warnings` is computed on every read (MENU-9), so it stays accurate after replacements and recipe deletions.

### `MenuSlotOut`
```json
{
  "day": 1,
  "date": "2026-11-23",
  "meal_type": "breakfast",
  "recipe": {
    "id": "uuid",
    "title": "Overnight Oats",
    "cuisine": "American",
    "servings": 2,
    "total_time_min": 5,
    "avg_rating": 4.5,
    "image_url": null
  },
  "scaled_ingredients": [ { "name": "rolled oats", "amount": 160, "unit": "g" } ],
  "warnings": []
}
```
Empty slot: `"recipe": null, "scaled_ingredients": [], "warnings": []`. A manually chosen recipe with a stop-list ingredient: `"warnings": ["Contains excluded ingredient: peanut"]`.

### `MenuListOut`
```json
{
  "total": 3, "page": 1, "limit": 20,
  "items": [ { "id": "uuid", "start_date": "2026-11-23", "servings": 4, "empty_slots": 0, "created_at": "..." } ]
}
```

---

## 11. Seed Data

- **SEED-1** At least 30 recipes in total: ≥ 8 breakfast, ≥ 12 lunch, ≥ 12 dinner (a recipe can count for several), with enough `vegetarian` recipes for a full vegetarian week without repeats.
- **SEED-2** `seasonal_produce` for `UA`: at least 25 common vegetables and fruits with their months (loaded by the migration).
- **SEED-3** Seeding stays idempotent (re-running doesn't duplicate rows).

---

## 12. Project Structure (additions)

```
app/
├── constants.py   # meal types, diets, limits shared by schemas and generator
├── logging_setup.py  # OPS-4
├── models/        preferences.py, menu.py (Menu, MenuSlot), seasonal.py
├── schemas/       preferences.py, menu.py
├── routers/       preferences.py, menus.py
├── services/
│   ├── preferences.py
│   ├── matching.py      # GEN-1, GEN-2 — pure functions
│   ├── generator.py     # GEN-3…GEN-13 — pure, no DB access
│   ├── menu.py          # loading candidates (GEN-14), persistence, replace
│   └── scaling.py       # SCALE-1…SCALE-3 — pure functions
tests/
├── test_preferences.py
├── test_matching.py
├── test_generator.py    # unit tests on in-memory recipes
├── test_menus.py
├── test_scaling.py
└── test_ops.py
```

`generator.py`, `matching.py` and `scaling.py` take plain data and do no I/O, so the rules are tested without a database.

---

## 13. Definition of Done

- [ ] All decisions in §0 confirmed.
- [ ] Migrations apply on a v0.1.1 database without data loss; existing recipes get `meal_types` and normalised `diet_tags`.
- [ ] Every rule id in this spec is covered by at least one test that names it.
- [ ] Generation and automatic replacement never pick a recipe with a stop-list ingredient (GEN-5); a manually chosen one is saved and flagged with a warning (MENU-6, MENU-9).
- [ ] Same seed → same menu (GEN-9).
- [ ] NFR-1 measured: generation with 10,000 recipes ≤ 2 s; timing recorded in the PR.
- [ ] Users can't see or change other users' menus (MENU-1).
- [ ] v0.1 test suite still passes; ruff clean; CI green including image build and `alembic check`.
- [ ] `docker compose up` works with no manual steps; production image runs as non-root and passes `/readyz`.
- [ ] `/docs` shows all new endpoints; CHANGELOG, README and version (`pyproject.toml`, `app/main.py`) updated to 0.2.0.
