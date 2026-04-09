from urllib.parse import quote_plus

from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from sqlalchemy import create_engine

from app.config.settings import settings


class LangChainSessionMemory:
    """MySQL-backed chat memory adapter built on LangChain."""

    TABLE_NAME = "langchain_chat_messages"

    def __init__(self) -> None:
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
        history_messages = self.get_messages(session_id)[-(max_turn * 2) :]

        context = [{"role": "system", "content": system_prompt}]
        context.extend(self._message_to_payload(message) for message in history_messages)
        context.append({"role": "user", "content": user_input})
        return context

    def get_messages(self, session_id: str) -> list[BaseMessage]:
        return list(self.get_history(session_id).messages)

    def append_messages(self, session_id: str, user_message: str, assistant_message: str) -> None:
        history = self.get_history(session_id)
        history.add_user_message(user_message)
        history.add_ai_message(assistant_message)

    def append_user_message(self, session_id: str, user_message: str) -> None:
        self.get_history(session_id).add_user_message(user_message)

    def append_ai_message(self, session_id: str, assistant_message: str) -> None:
        self.get_history(session_id).add_ai_message(assistant_message)

    def hydrate_session(self, session_id: str, messages: list[dict[str, str]]) -> None:
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
        return [self._message_to_payload(message) for message in self.get_messages(session_id)]

    @staticmethod
    def _message_to_payload(message: BaseMessage) -> dict[str, str]:
        if isinstance(message, HumanMessage):
            role = "user"
        elif isinstance(message, AIMessage):
            role = "assistant"
        else:
            role = "system"

        content = message.content
        if isinstance(content, list):
            content = "\n".join(str(item) for item in content)

        return {"role": role, "content": str(content)}


langchain_session_memory = LangChainSessionMemory()
