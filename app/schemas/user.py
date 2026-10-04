import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    """Request body for ``POST /auth/register``.

    Constraints mirror the ``users`` table so invalid input gets a 422 from validation
    instead of a database error: ``display_name`` is ``String(100)``.
    """

    email: EmailStr
    password: str = Field(min_length=8)
    display_name: str = Field(min_length=1, max_length=100)


class UserLogin(BaseModel):
    """Request body for ``POST /auth/login``.

    No length rules on purpose: a login attempt should simply fail with 401, not
    reveal the password policy.
    """

    email: EmailStr
    password: str


class UserOut(BaseModel):
    """Public view of a user. Built from the ORM ``User``; never exposes ``password_hash``."""

    id: uuid.UUID
    email: str
    display_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    """Response of ``POST /auth/login``: a JWT to send as ``Authorization: Bearer <token>``."""

    access_token: str
    token_type: str = "bearer"
