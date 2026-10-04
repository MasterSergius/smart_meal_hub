import uuid
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import ConflictError, NotFoundError, UnauthorizedError
from app.models.user import User
from app.schemas.user import TokenOut, UserRegister

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Hash a plain-text password with bcrypt.

    bcrypt generates a random salt per call and embeds it (plus the cost factor) in
    the returned string, so the same password hashes differently every time and the
    result can be stored as-is in ``users.password_hash``.
    """
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Check a plain-text password against a stored bcrypt hash.

    The salt and cost are read back out of ``hashed``, the candidate is hashed the
    same way, and the two are compared in constant time.
    """
    return _pwd_context.verify(plain, hashed)


def create_access_token(user_id: uuid.UUID) -> str:
    """Issue a signed JWT that identifies ``user_id``.

    The payload carries ``sub`` (the user id as a string) and ``exp`` (now +
    ``settings.jwt_expire_hours``). It is signed with HS256 using
    ``settings.jwt_secret``; it is signed, not encrypted, so it must not hold secrets.
    """
    expire = datetime.now(UTC) + timedelta(hours=settings.jwt_expire_hours)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> uuid.UUID:
    """Verify a JWT produced by ``create_access_token`` and return its user id.

    ``jwt.decode`` checks the HS256 signature and rejects expired tokens; the ``sub``
    claim is then parsed as a UUID.

    Raises:
        UnauthorizedError: bad signature, expired, missing ``sub`` or a non-UUID ``sub``.
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise UnauthorizedError("Invalid or expired token") from None


async def register_user(db: AsyncSession, data: UserRegister) -> User:
    """Create a new user account and return the persisted ``User``.

    Input rules (email format, password length, display name length) are already
    enforced by the ``UserRegister`` schema. The password is hashed before storing.
    Email uniqueness is enforced by the database's unique index rather than a prior
    ``SELECT``, so two concurrent sign-ups with the same email cannot both succeed.

    Raises:
        ConflictError: the email is already registered.
    """
    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        display_name=data.display_name,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        # The only unique constraint on ``users`` is the email; any other DB error
        # propagates to the global SQLAlchemyError handler in app.main.
        await db.rollback()
        raise ConflictError("Email already registered") from None
    await db.refresh(user)  # load server-generated ``created_at``
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> TokenOut:
    """Check an email/password pair and return a fresh access token.

    The same error is returned for an unknown email and for a wrong password, so the
    endpoint cannot be used to discover which emails are registered.

    Raises:
        UnauthorizedError: unknown email or wrong password.
    """
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        raise UnauthorizedError("Invalid credentials")
    return TokenOut(access_token=create_access_token(user.id))


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User:
    """Load a user by primary key.

    Raises:
        NotFoundError: no user with that id exists (e.g. deleted after the token was issued).
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User not found")
    return user
