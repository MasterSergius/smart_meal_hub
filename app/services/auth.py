import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import TokenOut, UserRegister


def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt."""
    ...


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    ...


def create_access_token(user_id: uuid.UUID) -> str:
    """Sign and return a JWT for the given user ID."""
    ...


def decode_token(token: str) -> uuid.UUID:
    """Decode a JWT and return the user ID. Raises 401 on invalid/expired token."""
    ...


async def register_user(db: AsyncSession, data: UserRegister) -> User:
    """Create a new user. Raises 409 if email already exists."""
    ...


async def authenticate_user(db: AsyncSession, email: str, password: str) -> TokenOut:
    """Verify credentials and return a token. Raises 401 on failure."""
    ...


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User:
    """Fetch a user by ID. Raises 404 if not found."""
    ...
