import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.exceptions import AppError
from app.routers import auth, ratings, recipes

logger = logging.getLogger(__name__)

app = FastAPI(
    title="SmartMeal Hub",
    version="0.1.1",
    description="Recipe Catalog API",
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(recipes.router, prefix="/api/v1/recipes", tags=["recipes"])
app.include_router(ratings.router, prefix="/api/v1/recipes", tags=["ratings"])


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Translate a domain ``AppError`` raised anywhere in a request into an HTTP response.

    The status code and optional headers come from the exception class, and the body
    is ``{"detail": <message>}``, the same shape as FastAPI's built-in errors.
    """
    return JSONResponse(
        status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers
    )


@app.exception_handler(SQLAlchemyError)
async def db_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Catch-all for unexpected database errors (DB down, constraint we did not foresee, ...).

    Logs the full traceback server-side and returns a generic 500 so internal details
    (SQL, table names) never leak to the client. The request's session is rolled back
    automatically when the ``get_db`` dependency closes it.
    """
    logger.exception("Database error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal database error"},
    )


@app.get("/healthz", tags=["ops"])
async def health() -> dict[str, str]:
    """Liveness probe: returns ``{"status": "ok"}`` if the process is serving requests.

    It does not touch the database, so it only reports that the API itself is up.
    """
    return {"status": "ok"}
