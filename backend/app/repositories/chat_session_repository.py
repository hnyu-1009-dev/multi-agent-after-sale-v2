from datetime import datetime
from typing import Any

from app.infrastructure.database.database_pool import DatabasePool


class ChatSessionRepository:
    def exists(self, user_id: str, session_id: str) -> bool:
        with DatabasePool.cursor() as cursor:
            cursor.execute(
                """
                SELECT 1
                FROM chat_sessions
                WHERE user_id = %s AND session_id = %s
                LIMIT 1
                """,
                (user_id, session_id),
            )
            return cursor.fetchone() is not None

    def upsert_session(
        self,
        user_id: str,
        session_id: str,
        preview: str | None,
        total_messages: int,
        created_at: datetime,
        updated_at: datetime,
    ) -> None:
        with DatabasePool.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO chat_sessions (
                    session_id, user_id, last_message_preview, total_messages, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    user_id = VALUES(user_id),
                    last_message_preview = VALUES(last_message_preview),
                    total_messages = VALUES(total_messages),
                    updated_at = VALUES(updated_at)
                """,
                (session_id, user_id, preview, total_messages, created_at, updated_at),
            )

    def list_by_user(self, user_id: str) -> list[dict[str, Any]]:
        with DatabasePool.cursor() as cursor:
            cursor.execute(
                """
                SELECT session_id, user_id, last_message_preview, total_messages, created_at, updated_at
                FROM chat_sessions
                WHERE user_id = %s
                ORDER BY updated_at DESC, created_at DESC
                """,
                (user_id,),
            )
            return list(cursor.fetchall() or [])


chat_session_repository = ChatSessionRepository()
