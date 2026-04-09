from datetime import UTC, datetime
from json import JSONDecodeError
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from app.infrastructure.logging.logger import logger
from app.infrastructure.memory.langchain_session_memory import langchain_session_memory
from app.repositories.chat_session_repository import chat_session_repository
from app.repositories.session_repository import session_repository


class SessionService:
    """对外提供“会话记忆”能力的服务层。

    这个类是项目里 memory 的总协调者，负责把几块能力串起来：
    1. 兼容旧版 JSON 会话文件
    2. 调用 LangChain + MySQL 存取消息正文
    3. 维护 chat_sessions 表中的会话元数据
    4. 为 Agent 准备裁剪后的上下文
    5. 为前端返回会话列表和历史消息

    可以把它理解成“memory 业务编排层”：
    - ``LangChainSessionMemory`` 只关心消息写库和读库
    - ``ChatSessionRepository`` 只关心会话元数据表
    - ``SessionService`` 负责定义什么时候写、写什么、怎么兼容旧数据
    """

    DEFAULT_SESSION_ID = "default_session"

    def __init__(self) -> None:
        self._legacy_repo = session_repository
        self._session_repo = chat_session_repository
        self._memory_store = langchain_session_memory

    def prepare_history(
        self, user_id: str, session_id: str | None, user_input: str, max_turn: int = 3
    ) -> list[dict[str, Any]]:
        """为一次新的模型调用准备上下文。

        调用时机：
        - 用户刚发送一条消息
        - 在真正执行 Agent 之前

        这里会做三件关键事情：
        1. 规范化 session_id，并按需触发旧数据迁移
        2. 确保 chat_sessions 表里有这次会话的元数据
        3. 从 MySQL 里取最近若干轮历史，拼成模型可直接使用的上下文
        """
        target_session_id = self._normalize_session_id(session_id)
        self._migrate_legacy_session_if_needed(user_id, target_session_id)

        # 这里先写会话元数据，但不写 assistant 回复正文。
        # 正文的用户消息会在 record_user_message 中立即入库。
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
        """读取单个会话的完整历史，供前端恢复页面或调试使用。"""
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
        """兼容旧调用方式：一次性保存整轮 user + assistant 消息。

        当前项目已经优先使用 ``record_user_message`` 和
        ``record_assistant_message`` 做分步写入，但这个方法仍保留，
        以兼容旧逻辑或批量补写路径。
        """
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
        """在用户消息进入系统时立即写入 memory。

        这是当前项目里“记忆实时性”最关键的一步。
        它保证了：
        - 用户发出消息后，即使 assistant 还没回答，消息也已经落库
        - 页面刷新或服务异常时，不会丢掉刚刚输入的用户内容
        """
        if not user_message or not user_message.strip():
            return

        target_session_id = self._normalize_session_id(session_id)
        self._migrate_legacy_session_if_needed(user_id, target_session_id)
        messages = self._memory_store.get_messages(target_session_id)

        # 如果最后一条已经是完全相同的 user 消息，说明这次调用很可能是重放或重复提交，
        # 直接跳过，避免产生连续重复消息。
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
        """在 assistant 最终回复生成完成后写入 memory。"""
        if not assistant_message or not assistant_message.strip():
            return

        target_session_id = self._normalize_session_id(session_id)
        self._migrate_legacy_session_if_needed(user_id, target_session_id)
        messages = self._memory_store.get_messages(target_session_id)

        # 和用户消息一样，这里也做一次尾部去重，避免重复保存相同答案。
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
        """返回某个用户的全部会话及其消息内容。

        前端刷新页面后重新加载历史列表，主要依赖这里。
        返回结构里：
        - ``memory`` 是消息正文列表
        - ``preview`` / ``create_time`` / ``update_time`` 来自 chat_sessions 元数据表
        """
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
        """批量扫描某个用户的旧版 JSON 会话，并按需迁移到 MySQL。"""
        raw_sessions = self._legacy_repo.get_all_sessions_metadata(user_id)
        for session_id, create_time, data_or_error in raw_sessions:
            if isinstance(data_or_error, Exception):
                logger.error("Legacy session %s load failed: %s", session_id, data_or_error)
                continue
            self._hydrate_legacy_session(user_id, session_id, create_time, data_or_error)

    def _migrate_legacy_session_if_needed(self, user_id: str, session_id: str) -> None:
        """按单个会话粒度触发旧数据迁移。

        如果 chat_sessions 中已经存在这条会话，就认为迁移已经完成，直接跳过。
        """
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
        """把旧版 JSON 历史导入到新 memory 体系中。"""
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
        """保证 chat_sessions 里始终有最新的会话元数据。

        这里不会覆盖已有会话的 created_at，只会刷新 updated_at、preview 和消息数。
        """
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
        """把空 session_id 规范成默认值，避免出现空键。"""
        return session_id or SessionService.DEFAULT_SESSION_ID

    @staticmethod
    def _build_system_prompt(session_id: str) -> str:
        return (
            "å¨´ï½‡å§µå¦²å‘Šç¨‰éˆ§î„ç¨‰é¡å‘®ç®’é ä½¹æ¾˜ç»»å‚žæ‡—é’˜å¤Šî”é–»ã„¥å«­å¨…ã‚‰æ‡—é’˜å¤‹æš›é–¸æ°¬éª¸æ¿®îˆå¹ç€£å‰ç¤‰é å›¬î—“ç»®ã„©å´¥é«æ¿ˆç§¼é–¸æ’³ç§³ç»±æ‰®æ‹ å©µå‘¯ç‘å¨‘æ’³îƒ†é‹å†®å´¶éç”µæ‘•é–»â‚¬åŠé©æ¶¢æ¢»é¡•â‚¬é¡£ä»‹å¦´?"
            f"ç‘œç‰ˆæŒ¸æ¾§çŠ³å¯¼å§˜å´‡æ¨ˆID: {session_id}"
        )

    @staticmethod
    def _extract_latest_message(
        chat_history: list[dict[str, Any]], role: str
    ) -> str | None:
        """从历史列表尾部反向查找最近的一条指定角色消息。"""
        for message in reversed(chat_history):
            if message.get("role") == role and message.get("content"):
                return str(message["content"]).strip()
        return None

    @staticmethod
    def _parse_legacy_time(value: str) -> datetime:
        """解析旧版文件时间字符串，失败时退回当前时间。"""
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
        except ValueError:
            return datetime.now(UTC)

    @staticmethod
    def _format_datetime(value: datetime) -> str:
        """统一把时间输出成字符串，便于前端直接展示。"""
        if value.tzinfo is None:
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _build_preview(content: str, limit: int = 80) -> str:
        """把长消息压缩成适合作为会话预览的短文本。"""
        preview = " ".join((content or "").split())
        return preview[:limit]


session_service = SessionService()
