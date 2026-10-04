from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.auth import decode_token, get_user_by_id

bearer_scheme = HTTPBearer()
optional_bearer_scheme = HTTPBearer(auto_error=False)

# Reusable dependency-typed aliases, so endpoints can declare ``db: DbSession``
# instead of repeating ``db: AsyncSession = Depends(get_db)`` everywhere.
DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: DbSession,
) -> User:
    """Resolve the authenticated user from the ``Authorization: Bearer <jwt>`` header.

    ``HTTPBearer`` extracts the token (and itself answers 403 when the header is
    missing), ``decode_token`` verifies the signature and expiry and yields the user
    id, and the user is then loaded from the database.

    Raises:
        UnauthorizedError: the token is malformed, tampered with or expired.
        NotFoundError: the token is valid but the user no longer exists.
    """
    user_id = decode_token(credentials.credentials)
    return await get_user_by_id(db, user_id)


async def get_current_user_optional(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(optional_bearer_scheme)],
    db: DbSession,
) -> User | None:
    """Like ``get_current_user``, but for endpoints that also work anonymously.

    Returns ``None`` when no ``Authorization`` header is sent. If a token *is* sent it
    must still be valid, so a bad token is rejected rather than silently ignored.
    """
    if credentials is None:
        return None
    user_id = decode_token(credentials.credentials)
    return await get_user_by_id(db, user_id)


CurrentUser = Annotated[User, Depends(get_current_user)]
