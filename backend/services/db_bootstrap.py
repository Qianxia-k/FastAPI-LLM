from config.db_conf import async_engine
from models.ai_chat import Base as AIChatBase


async def ensure_ai_chat_tables() -> None:
    """Ensure AI chat related tables exist.

    This only manages `models.ai_chat` metadata so that concerns stay isolated
    from routers and CRUD logic.
    """
    async with async_engine.begin() as conn:
        await conn.run_sync(AIChatBase.metadata.create_all)
