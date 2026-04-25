from datetime import datetime

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from models.history import History
from models.news import News


async def add_history(db: AsyncSession, user_id: int, news_id: int):
    """
    添加历史记录
    """
    query = select(History).where(History.user_id == user_id, History.news_id == news_id)
    result = await db.execute(query)
    existing_history = result.scalar_one_or_none()
    if existing_history:
        existing_history.view_time = datetime.now()
        await db.commit()
        await db.refresh(existing_history)
        return existing_history
    else:
        history = History(user_id=user_id, news_id=news_id)
        db.add(history)
        await db.commit()
        await db.refresh(history)
        return history


async def get_history_list(db: AsyncSession, user_id: int, page: int = 1, page_size: int = 10):
    offset = (page - 1) * page_size
    count_query = select(func.count(History.id)).where(History.user_id == user_id)
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()
    # 联表查询：查询历史记录 + 新闻数据
    # select(查询主体模型类, 字段别名).join(联合查询的模型类, 联合查询的条件).where().order_by().offset().limit()
    # 别名： History.view_time.label("view_time")
    # [
    #   (新闻对象, 浏览时间, 历史记录id)
    # ]

    query = (select(News, History.view_time.label("view_time"), History.id.label("history_id"))
             .join(History, History.news_id == News.id)
             .where(History.user_id == user_id)
             .order_by(History.view_time.desc())
             .offset(offset).limit(page_size))

    result = await db.execute(query)
    rows = result.all()
    return rows, total


async def delete_history(db: AsyncSession, user_id: int, news_id: int):
    """
    删除历史记录
    """
    query = delete(History).where(History.user_id == user_id, History.news_id == news_id)
    result = await db.execute(query)
    await db.commit()

    return result.rowcount > 0


async def clear_history(db: AsyncSession, user_id: int):
    """
    清空历史记录
    """
    query = delete(History).where(History.user_id == user_id)
    result = await db.execute(query)
    await db.commit()

    return result.rowcount or 0