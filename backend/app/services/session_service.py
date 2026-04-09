from datetime import UTC, datetime
from json import JSONDecodeError
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from app.infrastructure.logging.logger import logger
from app.infrastructure.memory.langchain_session_memory import langchain_session_memory
from app.repositories.chat_session_repository import chat_session_repository
from app.repositories.session_repository import session_repository


class SessionService:
    DEFAULT_SESSION_ID = "default_session"

    def __init__(self) -> None:
        self._legacy_repo = session_repository
        self._session_repo = chat_session_repository
        self._memory_store = langchain_session_memory

    def prepare_history(
        self, user_id: str, session_id: str | None, user_input: str, max_turn: int = 3
    ) -> list[dict[str, Any]]:
        target_session_id = self._normalize_session_id(session_id)
        self._migrate_legacy_session_if_needed(user_id, target_session_id)
        self._ensure_session_metadata(
            user_id=user_id,
            session_id=target_session_id,
            preview=self._build_preview(user_input),
            total_messages=len(self._memory_store.get_messages(target_session_id)),
        )
        return self._memory_store.build_context(
            session_id=target_session_id,
            system_prompt=self._build_system_prompt(target_session_id),
            user_input=user_input,
            max_turn=max_turn,
        )

    def load_history(self, user_id: str, session_id: str | None) -> list[dict[str, Any]]:
        target_session_id = self._normalize_session_id(session_id)
        self._migrate_legacy_session_if_needed(user_id, target_session_id)
        messages = self._memory_store.to_serializable_messages(target_session_id)
        return [
            {"role": "system", "content": self._build_system_prompt(target_session_id)},
            *messages,
        ]

    def save_history(
        self, user_id: str, session_id: str | None, chat_history: list[dict[str, Any]] | None
    ) -> None:
        if not chat_history:
            return

        target_session_id = self._normalize_session_id(session_id)
        self._migrate_legacy_session_if_needed(user_id, target_session_id)

        latest_user = self._extract_latest_message(chat_history, "user")
        latest_assistant = self._extract_latest_message(chat_history, "assistant")
        if not latest_user or not latest_assistant:
            return

        if not self._memory_store.has_matching_tail(
            target_session_id, latest_user, latest_assistant
        ):
            self._memory_store.append_messages(
                target_session_id, latest_user, latest_assistant
            )

        total_messages = len(self._memory_store.get_messages(target_session_id))
        self._ensure_session_metadata(
            user_id=user_id,
            session_id=target_session_id,
            preview=self._build_preview(latest_user),
            total_messages=total_messages,
        )

    def record_user_message(self, user_id: str, session_id: str | None, user_message: str) -> None:
        if not user_message or not user_message.strip():
            return

        target_session_id = self._normalize_session_id(session_id)
        self._migrate_legacy_session_if_needed(user_id, target_session_id)
        messages = self._memory_store.get_messages(target_session_id)
        if messages and isinstance(messages[-1], HumanMessage):
            if str(messages[-1].content).strip() == user_message.strip():
                return

        self._memory_store.append_user_message(target_session_id, user_message.strip())
        self._ensure_session_metadata(
            user_id=user_id,
            session_id=target_session_id,
            preview=self._build_preview(user_message),
            total_messages=len(messages) + 1,
        )

    def record_assistant_message(
        self, user_id: str, session_id: str | None, assistant_message: str
    ) -> None:
        if not assistant_message or not assistant_message.strip():
            return

        target_session_id = self._normalize_session_id(session_id)
        self._migrate_legacy_session_if_needed(user_id, target_session_id)
        messages = self._memory_store.get_messages(target_session_id)
        if messages and isinstance(messages[-1], AIMessage):
            if str(messages[-1].content).strip() == assistant_message.strip():
                return

        self._memory_store.append_ai_message(target_session_id, assistant_message.strip())
        latest_user = self._extract_latest_message(
            self._memory_store.to_serializable_messages(target_session_id), "user"
        ) or assistant_message
        self._ensure_session_metadata(
            user_id=user_id,
            session_id=target_session_id,
            preview=self._build_preview(latest_user),
            total_messages=len(messages) + 1,
        )

    def get_all_sessions_memory(self, user_id: str) -> list[dict[str, Any]]:
        self._migrate_legacy_sessions_for_user(user_id)

        formatted_sessions: list[dict[str, Any]] = []
        for session in self._session_repo.list_by_user(user_id):
            session_id = session["session_id"]
            memory = [
                message
                for message in self._memory_store.to_serializable_messages(session_id)
                if message.get("role") != "system"
            ]

            formatted_sessions.append(
                {
                    "session_id": session_id,
                    "create_time": self._format_datetime(session["created_at"]),
                    "update_time": self._format_datetime(session["updated_at"]),
                    "memory": memory,
                    "total_messages": len(memory),
                    "preview": session.get("last_message_preview")
                    or self._build_preview(memory[0]["content"] if memory else ""),
                }
            )

        return formatted_sessions

    def _migrate_legacy_sessions_for_user(self, user_id: str) -> None:
        raw_sessions = self._legacy_repo.get_all_sessions_metadata(user_id)
        for session_id, create_time, data_or_error in raw_sessions:
            if isinstance(data_or_error, Exception):
                logger.error("Legacy session %s load failed: %s", session_id, data_or_error)
                continue
            self._hydrate_legacy_session(user_id, session_id, create_time, data_or_error)

    def _migrate_legacy_session_if_needed(self, user_id: str, session_id: str) -> None:
        if self._session_repo.exists(user_id, session_id):
            return

        try:
            legacy_history = self._legacy_repo.load_session(user_id, session_id)
        except JSONDecodeError as exc:
            logger.error("Legacy session %s decode failed: %s", session_id, exc)
            return

        if legacy_history is None:
            return

        file_path = self._legacy_repo._get_file_path(user_id, session_id)
        create_time = datetime.fromtimestamp(file_path.stat().st_ctime, tz=UTC).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        self._hydrate_legacy_session(user_id, session_id, create_time, legacy_history)

    def _hydrate_legacy_session(
        self,
        user_id: str,
        session_id: str,
        create_time: str,
        legacy_history: list[dict[str, Any]],
    ) -> None:
        if self._session_repo.exists(user_id, session_id):
            return

        migrated_messages = [
            {"role": message.get("role"), "content": message.get("content", "")}
            for message in legacy_history
            if message.get("role") in {"user", "assistant"} and message.get("content")
        ]

        self._memory_store.hydrate_session(session_id, migrated_messages)
        migrated_at = self._parse_legacy_time(create_time)
        self._session_repo.upsert_session(
            user_id=user_id,
            session_id=session_id,
            preview=self._build_preview(
                migrated_messages[0]["content"] if migrated_messages else ""
            ),
            total_messages=len(migrated_messages),
            created_at=migrated_at,
            updated_at=migrated_at,
        )

    def _ensure_session_metadata(
        self,
        user_id: str,
        session_id: str,
        preview: str,
        total_messages: int,
    ) -> None:
        now = datetime.now(UTC)
        created_at = now
        existing_sessions = self._session_repo.list_by_user(user_id)
        for existing in existing_sessions:
            if existing["session_id"] == session_id:
                created_at = existing["created_at"]
                break

        self._session_repo.upsert_session(
            user_id=user_id,
            session_id=session_id,
            preview=preview,
            total_messages=total_messages,
            created_at=created_at,
            updated_at=now,
        )

    @staticmethod
    def _normalize_session_id(session_id: str | None) -> str:
        return session_id or SessionService.DEFAULT_SESSION_ID

    @staticmethod
    def _build_system_prompt(session_id: str) -> str:
        return (
            "娴ｇ姵妲告稉鈧稉顏呮箒鐠佹澘绻傞懗钘夊閻ㄥ嫭娅ら懗钘夋暛閸氬骸濮幍瀣剁礉鐠囬绮ㄩ崥鍫濈秼閸撳秳绱扮拠婵呯瑐娑撳鏋冮崶鐐电摕閻€劍鍩涢梻顕€顣介妴?"
            f"瑜版挸澧犳导姘崇樈ID: {session_id}"
        )

    @staticmethod
    def _extract_latest_message(
        chat_history: list[dict[str, Any]], role: str
    ) -> str | None:
        for message in reversed(chat_history):
            if message.get("role") == role and message.get("content"):
                return str(message["content"]).strip()
        return None

    @staticmethod
    def _parse_legacy_time(value: str) -> datetime:
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
        except ValueError:
            return datetime.now(UTC)

    @staticmethod
    def _format_datetime(value: datetime) -> str:
        if value.tzinfo is None:
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _build_preview(content: str, limit: int = 80) -> str:
        preview = " ".join((content or "").split())
        return preview[:limit]


session_service = SessionService()
