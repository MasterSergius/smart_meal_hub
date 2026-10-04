from fastapi import APIRouter, status

from app.dependencies import CurrentUser, DbSession
from app.models.user import User
from app.schemas.user import TokenOut, UserLogin, UserOut, UserRegister
from app.services import auth as auth_service

router = APIRouter()


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(data: UserRegister, db: DbSession) -> User:
    """``POST /auth/register``: create an account (201).

    Returns 422 for an invalid email, a password under 8 characters or a bad display
    name, and 409 if the email is already registered. The response is filtered
    through ``UserOut``, so the password hash is never returned.
    """
    return await auth_service.register_user(db, data)


@router.post("/login", response_model=TokenOut)
async def login(data: UserLogin, db: DbSession) -> TokenOut:
    """``POST /auth/login``: exchange email and password for a JWT access token.

    Returns 401 for an unknown email or a wrong password.
    """
    return await auth_service.authenticate_user(db, data.email, data.password)


@router.get("/me", response_model=UserOut)
async def me(current_user: CurrentUser) -> User:
    """``GET /auth/me``: return the user identified by the Bearer token."""
    return current_user
