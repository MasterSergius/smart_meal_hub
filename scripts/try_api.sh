#!/usr/bin/env bash
# Walk through the SmartMeal Hub API with curl: recipes, preferences, menus.
#
# Needs a running API with seed data:  make docker-run && make docker-seed
# Usage:  scripts/try_api.sh            (BASE=http://host:port scripts/try_api.sh for another server)
#
# Each step prints the request and a pretty-printed response. Requires curl and python3.

set -euo pipefail

BASE="${BASE:-http://localhost:8000}"
BODY_FILE=$(mktemp)
trap 'rm -f "$BODY_FILE"' EXIT

# ── helpers ───────────────────────────────────────────────────────────────────

step() { printf '\n\033[1;36m── %s\033[0m\n' "$*"; }

# call METHOD PATH [JSON_BODY] — prints "METHOD PATH → status" and the response body.
# Uses $TOKEN when set. The body is kept in $BODY for json_get.
call() {
    local method=$1 path=$2 data=${3:-}
    local args=(-s -o "$BODY_FILE" -w '%{http_code}' -X "$method" "$BASE$path")
    [[ -n "${TOKEN:-}" ]] && args+=(-H "Authorization: Bearer $TOKEN")
    [[ -n "$data" ]] && args+=(-H "Content-Type: application/json" -d "$data")
    local status
    status=$(curl "${args[@]}")
    BODY=$(cat "$BODY_FILE")
    printf '\033[33m%s %s → %s\033[0m\n' "$method" "$path" "$status"
    [[ -n "$BODY" ]] && python3 -m json.tool <<<"$BODY" 2>/dev/null | head -n "${LINES_MAX:-40}" || true
}

# json_get EXPR — evaluate a Python expression on the last response, bound to `r`.
json_get() { python3 -c "import json,sys; r=json.loads(sys.stdin.read()); print($1)" <<<"$BODY"; }

# print_menu — one line per slot of the last menu response, then its warnings.
print_menu() {
    BODY="$BODY" python3 - <<'PY'
import json, os
r = json.loads(os.environ["BODY"])
for s in r["slots"]:
    title = s["recipe"]["title"] if s["recipe"] else "— empty —"
    print(f"day {s['day']} {s['meal_type']:9} {title}")
print("warnings:", r["warnings"])
PY
}

login() {
    TOKEN=""
    call POST /api/v1/auth/login "{\"email\":\"$1\",\"password\":\"$2\"}"
    TOKEN=$(json_get 'r["access_token"]')
}

# ── health ────────────────────────────────────────────────────────────────────

step "Health: liveness and readiness (database check)"
call GET /healthz
call GET /readyz

# ── recipes (public) ──────────────────────────────────────────────────────────

step "Search: vegetarian breakfasts"
LINES_MAX=25 call GET "/api/v1/recipes/search?meal_type=breakfast&diet_tags=vegetarian&limit=3"

step "Search: quick dinners (≤ 30 min) by text"
LINES_MAX=25 call GET "/api/v1/recipes/search?meal_type=dinner&max_total_time=30&q=chicken"

step "Search: Ukrainian cuisine, page 1 of 5 per page"
call GET "/api/v1/recipes/search?cuisine=ukrainian&limit=5"
RECIPE_ID=$(json_get 'r["items"][0]["id"]')

step "One recipe by id"
LINES_MAX=60 call GET "/api/v1/recipes/$RECIPE_ID"

# ── a fresh user ──────────────────────────────────────────────────────────────

EMAIL="demo-$(date +%s)@example.com"
step "Register $EMAIL and log in"
call POST /api/v1/auth/register "{\"email\":\"$EMAIL\",\"password\":\"password123\",\"display_name\":\"Demo\"}"
login "$EMAIL" password123
call GET /api/v1/auth/me

step "Rate a seed recipe 5 stars"
call POST "/api/v1/recipes/$RECIPE_ID/ratings" '{"score":5,"comment":"Tasty!"}'

# ── preferences ───────────────────────────────────────────────────────────────

step "Preferences before saving (defaults)"
call GET /api/v1/users/me/preferences

step "Save preferences: vegetarian, no mushrooms, 3 people, Ukraine"
call PUT /api/v1/users/me/preferences \
    '{"diets":["vegetarian"],"excluded_ingredients":["Mushroom"],"household_size":3,"region":"ua"}'

# ── menus ─────────────────────────────────────────────────────────────────────

step "Generate a weekly menu from preferences (seed 42 = reproducible)"
LINES_MAX=0 call POST /api/v1/menus/generate '{"seed":42}'
MENU_ID=$(json_get 'r["id"]')
print_menu

step "Same request again gives the same dishes (GEN-9)"
LINES_MAX=0 call POST /api/v1/menus/generate '{"seed":42}'
json_get '", ".join(s["recipe"]["title"] for s in r["slots"][:3] if s["recipe"])'

step "Generate with overrides (not saved): keto, 2 people, next Monday, no region"
NEXT_MONDAY=$(python3 -c 'import datetime as d; t=d.date.today(); print(t + d.timedelta(days=(7 - t.weekday()) % 7 or 7))')
LINES_MAX=0 call POST /api/v1/menus/generate \
    "{\"diets\":[\"keto\"],\"servings\":2,\"start_date\":\"$NEXT_MONDAY\",\"region\":null}"
echo "start_date: $(json_get 'r["start_date"]')  warnings: $(json_get 'r["warnings"]')"

step "My menus"
call GET "/api/v1/menus?limit=5"

step "Day 1 dinner with ingredients scaled to 3 people"
LINES_MAX=0 call GET "/api/v1/menus/$MENU_ID"
json_get 'json.dumps(r["slots"][2], indent=2)'

step "Replace day 1 dinner automatically (FR-1.2)"
LINES_MAX=12 call POST "/api/v1/menus/$MENU_ID/slots/1/dinner/replace"

step "Put a recipe with mushrooms into day 2 lunch on purpose → kept, with a warning"
LINES_MAX=0 call GET "/api/v1/recipes/search?q=mushroom&limit=1"
MUSHROOM_ID=$(json_get 'r["items"][0]["id"]')
call POST "/api/v1/menus/$MENU_ID/slots/2/lunch/replace" "{\"recipe_id\":\"$MUSHROOM_ID\"}"

step "Cook for 6 instead of 3 (FR-1.3)"
LINES_MAX=0 call PATCH "/api/v1/menus/$MENU_ID" '{"servings":6}'
json_get 'json.dumps(r["slots"][0]["scaled_ingredients"], indent=2)'
echo "warnings: $(json_get 'r["warnings"]')"

# ── errors ────────────────────────────────────────────────────────────────────

step "Errors: invalid diet (422), bad meal type (422), no token (403)"
LINES_MAX=6 call POST /api/v1/menus/generate '{"diets":["paleo"]}'
LINES_MAX=6 call POST "/api/v1/menus/$MENU_ID/slots/1/brunch/replace"
SAVED=$TOKEN; TOKEN=""
call GET /api/v1/menus
TOKEN=$SAVED

step "Another user can't see this menu (404)"
login chef@example.com password123
call GET "/api/v1/menus/$MENU_ID"

step "Delete the menu (as its owner)"
login "$EMAIL" password123
call DELETE "/api/v1/menus/$MENU_ID"
call GET "/api/v1/menus/$MENU_ID"

printf '\n\033[1;32mDone.\033[0m Interactive docs: %s/docs\n' "$BASE"
