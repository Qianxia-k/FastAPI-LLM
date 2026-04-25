import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.ai_chat import ChatMessage, UserChatSession

# 创建一个新的聊天会话，返回 session_id
async def create_chat_session(db: AsyncSession, user_id: int, title: str | None = None):
    """
    创建一个新的聊天会话，返回 session_id。
    """
    session_id = str(uuid.uuid4())
    new_session = UserChatSession(
        user_id=user_id,
        session_id=session_id,
        title=title,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)
    return new_session#返回orm对象，路由层再转换成pydantic对象响应给前端

# 获取某个用户的某个会话
async def get_chat_session(db: AsyncSession, user_id: int, session_id: str):
    query = select(UserChatSession).where(
        UserChatSession.session_id == session_id,
        UserChatSession.user_id == user_id,
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()#返回orm对象，路由层再转换成pydantic对象响应给前端


#获取某个用户的所有会话列表
async def user_has_chat_sessions(db: AsyncSession, user_id: int) -> bool:
    query = select(UserChatSession).where(
        UserChatSession.user_id == user_id
    )
    result = await db.execute(query)
    return result.scalar_one_or_none() is not None



#对于某个用户，获取最新的一个会话
async def get_latest_chat_session(db: AsyncSession, user_id: int):
    query = (
        select(UserChatSession)
        .where(UserChatSession.user_id == user_id)
        .order_by(UserChatSession.updated_at.desc())
        .limit(1)
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_user_chat_sessions(db: AsyncSession, user_id: int, limit: int = 50):
    query = (
        select(UserChatSession)
        .where(UserChatSession.user_id == user_id)
        .order_by(UserChatSession.updated_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    return result.scalars().all()


#对于某个会话，添加一条消息记录
async def add_chat_message(
    db: AsyncSession,
    user_id: int,
    session_id: str,
    role: str,
    content: str,
    model_name: str | None = None,
    finish_reason: str | None = None,
):
    max_index_query = select(func.max(ChatMessage.message_index)).where(
        ChatMessage.user_id == user_id,
        ChatMessage.session_id == session_id,
    )
    max_index_result = await db.execute(max_index_query)
    current_max_index = max_index_result.scalar_one_or_none() or 0

    message = ChatMessage(
        user_id=user_id,
        session_id=session_id,
        role=role,
        content=content,
        message_index=current_max_index + 1,
        model_name=model_name,
        finish_reason=finish_reason,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message#返回orm对象，路由层再转换成pydantic对象响应给前端


#获取某个会话的所有聊天内容
async def get_chat_content_by_session(db: AsyncSession, user_id: int, session_id: str):
    query = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id, ChatMessage.user_id == user_id)
        .order_by(ChatMessage.message_index.asc(), ChatMessage.created_at.asc())
    )
    result = await db.execute(query)
    return result.scalars().all()
#获取某个会话的summary，现获取当前会话的所有消息内容，取最后一条消息的content作为summary，后续可以改成调用模型接口生成一个总结文本，更新到UserChatSession的summary字段里
async def get_chat_session_summary(db: AsyncSession, user_id: int, session_id: str):
    query = select(UserChatSession.summary).where(
        UserChatSession.session_id == session_id,
        UserChatSession.user_id == user_id,
    )
    result = await db.execute(query)
    return result.scalar_one_or_none() or ""


# 更新会话摘要
async def update_chat_session_summary(db: AsyncSession, user_id: int, session_id: str, summary: str, last_summary_index: int):
    query = select(UserChatSession).where(
        UserChatSession.session_id == session_id,
        UserChatSession.user_id == user_id,
    )
    result = await db.execute(query)
    session = result.scalar_one_or_none()#当前orm的会话
    if not session:
        return None

    session.summary = summary
    session.updated_at = datetime.now()
    session.last_summary_index = last_summary_index
    await db.commit()
    await db.refresh(session)
    return session


#获取某个对话的近期{x}条消息，返回近期消息列表
async def get_recent_chat_messages(db: AsyncSession, user_id: int, session_id: str, limit: int = 10):
    query = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id, ChatMessage.user_id == user_id)
        .order_by(ChatMessage.message_index.desc(), ChatMessage.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    return result.scalars().all()#orm