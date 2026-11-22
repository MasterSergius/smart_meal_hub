import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.dependencies import DbSession
from app.exceptions import AppError
from app.logging_setup import configure_logging
from app.routers import auth, menus, preferences, ratings, recipes

configure_logging(settings.log_format)
logger = logging.getLogger(__name__)
request_logger = logging.getLogger("app.request")

app = FastAPI(
    title="SmartMeal Hub",
    version="0.2.0",
    description=(
        "Recipe catalog and weekly menu planning API.\n\n"
        "Excluded ingredients are matched as whole words, with simple plurals "
        "(`egg` matches `eggs`, not `eggplant`); synonyms and allergen groups are "
        "not recognised, so list each ingredient to avoid."
    ),
)

if settings.cors_origin_list:  # OPS-3
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(recipes.router, prefix="/api/v1/recipes", tags=["recipes"])
app.include_router(ratings.router, prefix="/api/v1/recipes", tags=["ratings"])
app.include_router(preferences.router, prefix="/api/v1/users/me/preferences", tags=["preferences"])
app.include_router(menus.router, prefix="/api/v1/menus", tags=["menus"])


@app.middleware("http")
async def log_requests(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """OPS-4: log method, path, status and duration of every request."""
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 1)
    request_logger.info(
        "%s %s %s %.1fms",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        extra={
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


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


@app.get("/readyz", tags=["ops"])
async def ready(db: DbSession) -> JSONResponse:
    """OPS-1: readiness probe for the load balancer; checks the database with ``SELECT 1``.

    Returns 503 when the database can't be reached, so traffic is held back until it can.
    """
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Readiness check failed")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"status": "unavailable"}
        )
    return JSONResponse(content={"status": "ok"})
