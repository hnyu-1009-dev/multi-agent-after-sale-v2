from typing import Literal

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    user_id: str
    username: str
    display_name: str


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    display_name: str | None = Field(default=None, max_length=64)


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class AuthResponse(BaseModel):
    token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_at: str
    user: UserProfile


class LogoutResponse(BaseModel):
    success: bool = True
