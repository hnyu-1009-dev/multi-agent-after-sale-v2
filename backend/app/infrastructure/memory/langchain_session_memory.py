from urllib.parse import quote_plus

from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from sqlalchemy import create_engine

from app.config.settings import settings


class LangChainSessionMemory:
    """基于 LangChain + MySQL 的消息记忆适配器。

    这个类只负责“消息正文”的持久化与读取，不负责用户身份、会话列表、
    会话预览、创建时间等元数据。后者由 ``SessionService`` 和
    ``ChatSessionRepository`` 处理。

    这里的职责很聚焦：
    1. 把一条 user / assistant 消息写入 ``langchain_chat_messages``
    2. 根据 session_id 读取某个会话的历史消息
    3. 把 LangChain 的消息对象转换成项目内统一使用的 role/content 结构
    4. 为旧版 JSON 会话迁移提供一次性导入能力
    """

    TABLE_NAME = "langchain_chat_messages"

    def __init__(self) -> None:
        # 统一构造 SQLAlchemy engine，后续所有会话都复用这一套数据库连接工厂。
        #
        # 这里不用每次读写消息都临时拼接一次数据库连接对象，否则开销更大，
        # 也不利于连接池复用。
        self._connection_string = (
            "mysql+pymysql://"
            f"{quote_plus(settings.MYSQL_USER or '')}:"
            f"{quote_plus(settings.MYSQL_PASSWORD or '')}@"
            f"{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/"
            f"{settings.MYSQL_DATABASE}"
            f"?charset={settings.MYSQL_CHARSET}"
        )
        self._engine = create_engine(self._connection_string, pool_pre_ping=True)

    def get_history(self, session_id: str) -> SQLChatMessageHistory:
        # LangChain 的 SQLChatMessageHistory 会把 session_id 作为会话分区键，
        # 相同 session_id 的消息会被归到同一条历史链路中。
        return SQLChatMessageHistory(
            session_id=session_id,
            connection=self._engine,
            table_name=self.TABLE_NAME,
        )

    def build_context(
        self,
        session_id: str,
        system_prompt: str,
        user_input: str,
        max_turn: int = 3,
    ) -> list[dict[str, str]]:
        # 一个完整轮次通常是“1 条 user + 1 条 assistant”，
        # 所以保留最近 max_turn 轮，等价于截取最近 max_turn * 2 条消息。
        #
        # 这样可以在保持短期上下文的同时，控制 prompt 长度，避免历史太长。
        history_messages = self.get_messages(session_id)[-(max_turn * 2) :]

        context = [{"role": "system", "content": system_prompt}]
        context.extend(self._message_to_payload(message) for message in history_messages)
        context.append({"role": "user", "content": user_input})
        return context

    def get_messages(self, session_id: str) -> list[BaseMessage]:
        # 这里主动转成 list，方便上层做长度判断、尾部去重、序列化输出。
        return list(self.get_history(session_id).messages)

    def append_messages(self, session_id: str, user_message: str, assistant_message: str) -> None:
        # 兼容“整轮一起写入”的调用方式。
        history = self.get_history(session_id)
        history.add_user_message(user_message)
        history.add_ai_message(assistant_message)

    def append_user_message(self, session_id: str, user_message: str) -> None:
        # 用户消息在请求进入后立即写库。
        #
        # 这样即使 assistant 还没回答完、服务重启、页面刷新，用户刚刚输入的
        # 内容也不会丢。
        self.get_history(session_id).add_user_message(user_message)

    def append_ai_message(self, session_id: str, assistant_message: str) -> None:
        # assistant 消息在最终答案生成完成后写库。
        self.get_history(session_id).add_ai_message(assistant_message)

    def hydrate_session(self, session_id: str, messages: list[dict[str, str]]) -> None:
        # 旧版 JSON -> MySQL 的一次性迁移入口。
        #
        # 如果当前 session 在 SQL 表里已经有消息，就直接跳过，
        # 避免重复迁移导致消息翻倍。
        history = self.get_history(session_id)
        if history.messages:
            return

        for message in messages:
            role = message.get("role")
            content = (message.get("content") or "").strip()
            if not content:
                continue
            if role == "user":
                history.add_user_message(content)
            elif role == "assistant":
                history.add_ai_message(content)

    def has_matching_tail(
        self, session_id: str, user_message: str, assistant_message: str
    ) -> bool:
        # 用最后两条消息判断当前“user + assistant”这一轮是否已经存在。
        #
        # 这个判断主要用于兼容旧保存逻辑，防止某些路径重复把同一轮对话写两次。
        messages = self.get_messages(session_id)
        if len(messages) < 2:
            return False

        tail = messages[-2:]
        return (
            isinstance(tail[0], HumanMessage)
            and isinstance(tail[1], AIMessage)
            and tail[0].content == user_message
            and tail[1].content == assistant_message
        )

    def to_serializable_messages(self, session_id: str) -> list[dict[str, str]]:
        # 给 API 返回和会话列表恢复使用，把 LangChain 对象转成普通字典。
        return [self._message_to_payload(message) for message in self.get_messages(session_id)]

    @staticmethod
    def _message_to_payload(message: BaseMessage) -> dict[str, str]:
        # LangChain 内部是 HumanMessage / AIMessage 这样的强类型对象，
        # 但前后端交互、Agent 输入一般都使用 role/content 结构。
        # 这里统一做一次格式转换。
        if isinstance(message, HumanMessage):
            role = "user"
        elif isinstance(message, AIMessage):
            role = "assistant"
        else:
            role = "system"

        content = message.content
        if isinstance(content, list):
            # 某些 LangChain 消息实现会把 content 组织成块列表。
            # 当前项目接口只需要文本，因此这里把它们拼成单个字符串。
            content = "\n".join(str(item) for item in content)

        return {"role": role, "content": str(content)}


langchain_session_memory = LangChainSessionMemory()
