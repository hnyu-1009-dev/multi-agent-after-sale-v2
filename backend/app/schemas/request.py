from typing import Optional

from pydantic import BaseModel, Field


class UserContext(BaseModel):
    user_id: Optional[str] = Field(default=None, description="当前用户ID")
    session_id: Optional[str] = Field(default=None, description="会话ID")


class ChatMessageRequest(BaseModel):
    query: str
    context: UserContext
    flag: bool = True


class UserSessionsRequest(BaseModel):
    user_id: Optional[str] = Field(default=None, description="当前用户ID")
