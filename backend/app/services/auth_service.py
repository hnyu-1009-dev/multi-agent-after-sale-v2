from datetime import UTC, datetime
from uuid import uuid4

from app.repositories.user_repository import user_repository
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserProfile
from app.utils.security import (
    build_token_expiration,
    generate_auth_token,
    hash_password,
    hash_token,
    verify_password,
)


class AuthServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class AuthService:
    def register(self, payload: RegisterRequest) -> AuthResponse:
        username = payload.username.strip()
        if user_repository.get_by_username(username):
            raise AuthServiceError("用户名已存在", status_code=409)

        now = datetime.now(UTC)
        display_name = (payload.display_name or username).strip() or username
        salt, password_hash = hash_password(payload.password)
        user_id = username

        user_repository.create_user(
            user_id=user_id,
            username=username,
            display_name=display_name,
            password_salt=salt,
            password_hash=password_hash,
            now=now,
        )

        return self._issue_token(
            {
                "user_id": user_id,
                "username": username,
                "display_name": display_name,
            }
        )

    def login(self, payload: LoginRequest) -> AuthResponse:
        username = payload.username.strip()
        user = user_repository.get_by_username(username)
        if not user or not user.get("is_active"):
            raise AuthServiceError("用户名或密码错误", status_code=401)

        if not verify_password(
            payload.password,
            user["password_salt"],
            user["password_hash"],
        ):
            raise AuthServiceError("用户名或密码错误", status_code=401)

        return self._issue_token(user)

    def authenticate_token(self, token: str) -> UserProfile:
        now = datetime.now(UTC)
        token_hash_value = hash_token(token)
        user_repository.delete_expired_tokens(now)

        token_record = user_repository.get_user_by_token_hash(token_hash_value)
        if not token_record or not token_record.get("is_active"):
            raise AuthServiceError("登录状态已失效，请重新登录", status_code=401)

        expires_at = token_record["expires_at"]
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= now:
            user_repository.delete_token(token_hash_value)
            raise AuthServiceError("登录状态已失效，请重新登录", status_code=401)

        user_repository.touch_token(token_hash_value, now)
        return UserProfile(
            user_id=token_record["user_id"],
            username=token_record["username"],
            display_name=token_record["display_name"],
        )

    def logout(self, token: str) -> None:
        user_repository.delete_token(hash_token(token))

    def get_user(self, user_id: str) -> UserProfile:
        user = user_repository.get_by_id(user_id)
        if not user or not user.get("is_active"):
            raise AuthServiceError("用户不存在", status_code=404)
        return UserProfile(
            user_id=user["user_id"],
            username=user["username"],
            display_name=user["display_name"],
        )

    def _issue_token(self, user: dict) -> AuthResponse:
        token = generate_auth_token()
        token_expiration = build_token_expiration()
        now = datetime.now(UTC)

        user_repository.create_token(
            token_id=str(uuid4()),
            user_id=user["user_id"],
            token_hash=hash_token(token),
            expires_at=token_expiration,
            now=now,
        )

        return AuthResponse(
            token=token,
            expires_at=token_expiration.isoformat(),
            user=UserProfile(
                user_id=user["user_id"],
                username=user["username"],
                display_name=user["display_name"],
            ),
        )


auth_service = AuthService()
