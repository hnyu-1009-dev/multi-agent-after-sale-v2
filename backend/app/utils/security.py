import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from app.config.settings import settings


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    actual_salt = salt or secrets.token_hex(16)
    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        actual_salt.encode("utf-8"),
        settings.PASSWORD_HASH_ITERATIONS,
    )
    return actual_salt, derived_key.hex()


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    _, actual_hash = hash_password(password, salt)
    return hmac.compare_digest(actual_hash, expected_hash)


def generate_auth_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def build_token_expiration() -> datetime:
    return datetime.now(UTC) + timedelta(hours=settings.AUTH_TOKEN_EXPIRE_HOURS)
