from datetime import datetime
from typing import Any

from app.infrastructure.database.database_pool import DatabasePool


class ChatSessionRepository:
    """读写 chat_sessions 表。

    这个仓库只管理“会话元数据”，不保存聊天正文。

    chat_sessions 里的数据主要用于：
    - 前端展示会话列表
    - 展示最近一条消息摘要
    - 记录总消息数、创建时间、更新时间

    真正的聊天正文仍然存放在 ``langchain_chat_messages`` 表中。
    """

    def exists(self, user_id: str, session_id: str) -> bool:
        """判断某个用户的某个会话元数据是否已经存在。"""
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
        """插入或更新一条会话元数据。

        设计成 upsert 的原因是：
        - 新会话首次写入时走 insert
        - 同一会话后续追加消息时走 update
        - 调用方不需要自己区分“新增还是更新”
        """
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
        """按更新时间倒序返回某个用户的全部会话元数据。"""
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
