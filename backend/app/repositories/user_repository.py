from datetime import datetime
from typing import Any

from app.infrastructure.database.database_pool import DatabasePool


class UserRepository:
    def get_by_username(self, username: str) -> dict[str, Any] | None:
        with DatabasePool.cursor() as cursor:
            cursor.execute(
                """
                SELECT user_id, username, display_name, password_salt, password_hash, is_active,
                       created_at, updated_at
                FROM users
                WHERE username = %s
                LIMIT 1
                """,
                (username,),
            )
            return cursor.fetchone()

    def get_by_id(self, user_id: str) -> dict[str, Any] | None:
        with DatabasePool.cursor() as cursor:
            cursor.execute(
                """
                SELECT user_id, username, display_name, is_active, created_at, updated_at
                FROM users
                WHERE user_id = %s
                LIMIT 1
                """,
                (user_id,),
            )
            return cursor.fetchone()

    def create_user(
        self,
        user_id: str,
        username: str,
        display_name: str,
        password_salt: str,
        password_hash: str,
        now: datetime,
    ) -> None:
        with DatabasePool.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users (
                    user_id, username, display_name, password_salt, password_hash,
                    created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    username,
                    display_name,
                    password_salt,
                    password_hash,
                    now,
                    now,
                ),
            )

    def create_token(
        self,
        token_id: str,
        user_id: str,
        token_hash: str,
        expires_at: datetime,
        now: datetime,
    ) -> None:
        with DatabasePool.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO user_auth_tokens (
                    token_id, user_id, token_hash, expires_at, created_at, last_used_at
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (token_id, user_id, token_hash, expires_at, now, now),
            )

    def get_user_by_token_hash(self, token_hash: str) -> dict[str, Any] | None:
        with DatabasePool.cursor() as cursor:
            cursor.execute(
                """
                SELECT t.token_id, t.user_id, t.expires_at,
                       u.username, u.display_name, u.is_active
                FROM user_auth_tokens t
                INNER JOIN users u ON u.user_id = t.user_id
                WHERE t.token_hash = %s
                LIMIT 1
                """,
                (token_hash,),
            )
            return cursor.fetchone()

    def touch_token(self, token_hash: str, now: datetime) -> None:
        with DatabasePool.cursor() as cursor:
            cursor.execute(
                """
                UPDATE user_auth_tokens
                SET last_used_at = %s
                WHERE token_hash = %s
                """,
                (now, token_hash),
            )

    def delete_token(self, token_hash: str) -> None:
        with DatabasePool.cursor() as cursor:
            cursor.execute(
                "DELETE FROM user_auth_tokens WHERE token_hash = %s",
                (token_hash,),
            )

    def delete_expired_tokens(self, now: datetime) -> None:
        with DatabasePool.cursor() as cursor:
            cursor.execute(
                "DELETE FROM user_auth_tokens WHERE expires_at <= %s",
                (now,),
            )


user_repository = UserRepository()
