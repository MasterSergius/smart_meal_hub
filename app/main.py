from fastapi import FastAPI

from app.routers import auth, ratings, recipes

app = FastAPI(
    title="SmartMeal Hub",
    version="0.1.0",
    description="Recipe Catalog API",
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(recipes.router, prefix="/api/v1/recipes", tags=["recipes"])
app.include_router(ratings.router, prefix="/api/v1/recipes", tags=["ratings"])


@app.get("/healthz", tags=["ops"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
