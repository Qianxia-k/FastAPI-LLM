from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UserChatSession(Base):
    """
    用户对话会话表
    """

    __tablename__ = "user_chat_session"

    __table_args__ = (
        Index("idx_user_chat_session_user_id", "user_id"),
        Index("idx_user_chat_session_session_id", "session_id", unique=True),
        Index("idx_user_chat_session_updated_at", "updated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="会话主键ID")
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="用户ID")
    session_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, comment="会话UUID")
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="会话标题")
    summary: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="会话摘要")
    last_summary_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="摘要更新时的消息索引")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, comment="更新时间")

    def __repr__(self):
        return f"<UserChatSession(id={self.id}, user_id={self.user_id}, session_id='{self.session_id}')>"


class ChatMessage(Base):
    """
    用户对话消息表
    """

    __tablename__ = "chat_message"

    __table_args__ = (
        Index("idx_chat_message_user_id", "user_id"),
        Index("idx_chat_message_session_id", "session_id"),
        Index("idx_chat_message_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="消息主键ID")
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="用户ID")
    session_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        comment="会话UUID",
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, comment="角色：user/assistant/system/tool")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="消息内容")
    message_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="会话内消息顺序")
    model_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="模型名称")
    finish_reason: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="结束原因")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, comment="更新时间")

    def __repr__(self):
        return f"<ChatMessage(id={self.id}, user_id={self.user_id}, session_id='{self.session_id}', role='{self.role}')>"
