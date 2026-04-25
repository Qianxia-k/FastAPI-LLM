from typing import Literal, Optional

from pydantic import BaseModel, Field

class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str
    


class AIChatRequest(BaseModel):
    model: str = "qwen3-max-preview"
    messages: list[ChatMessage] = Field(default_factory=list)
    stream: bool = True
    session_id: Optional[str] = Field(default=None, comment="对话ID")

class ChatSessionResponse(BaseModel):
    session_id: str
    title: Optional[str] = None
    summary: Optional[str] = None

class ChatSessionMessagesResponse(BaseModel):
    session_id: str
    messages: list[ChatMessage] = Field(default_factory=list)