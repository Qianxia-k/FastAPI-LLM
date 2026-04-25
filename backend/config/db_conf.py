import os

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession, create_async_engine
#AsyncSession：异步会话对象，用于执行数据库操作。
#async_sessionmaker：异步会话工厂，用于创建异步会话对象。
#create_async_engine：创建异步数据库引擎，用于连接数据库和执行SQL语
# 数据库URL
from dotenv import load_dotenv
# Load environment variables from backend/.env (if present) and the environment
load_dotenv()

ASYNC_DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/news_db"
)
# 创建异步引擎
#管理连接池，设置连接池大小和最大溢出连接数，连接池是为了提高数据库连接的效率和性能，
# 避免每次请求都创建和销毁连接。通过设置pool_size和max_overflow参数，
# 可以控制连接池中保持的持久连接数和允许创建的额外连接数，从而优化数据库连接的管理。
#防止同时操作数据库的连接数过多，导致数据库连接过载，影响数据库的正常运行。
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=True,  # 可选：输出SQL日志
    pool_size=10,  # 设置连接池中保持的持久连接数
    max_overflow=20  # 设置连接池允许创建的额外连接数
)

# 创建异步会话工厂，是为了管理异步数据库会话的创建和配置。通过使用async_sessionmaker，可以定义会话的行为和属性，
# 例如绑定引擎、设置会话类、配置提交行为等。这样可以确保在应用程序中使用一致的方式来创建和管理数据库会话，提高代码的可维护性和效率。
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


# 依赖项，用于获取数据库会话
#是为了在应用程序中提供一个统一的方式来获取数据库会话。通过定义一个依赖项函数get_db，可以在需要数据库会话的地方使用它来获取一个异步会话对象。
#这个函数使用了async with语句来确保会话的正确管理，包括提交事务、回滚事务和关闭会话。通过使用yield关键字，可以在需要数据库会话的地方获取到一个有效的会话对象，并且在使用完成后自动处理事务和资源的释放。
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
