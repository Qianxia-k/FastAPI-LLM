from fastapi import FastAPI
from routers import news, users, favorite, history, ai_chat
from fastapi.middleware.cors import CORSMiddleware

from services.db_bootstrap import ensure_ai_chat_tables
from utils.exception_handlers import register_exception_handlers

app = FastAPI()


@app.on_event("startup")
async def startup_db_bootstrap():
    # 启动时确保 AI 聊天相关表存在
    await ensure_ai_chat_tables()

# 注册异常处理器
register_exception_handlers(app)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],     # 允许的源，开发阶段允许所有源，生产环境需要指定源
    allow_credentials=True,  # 允许携带cookie
    allow_methods=["*"],     # 允许的请求方法
    allow_headers=["*"],     # 允许的请求头
    expose_headers=["X-Session-Id"],  # 允许前端读取后端返回的会话ID
)


@app.get("/")
async def root():
    return {"message": "Hello World"}

# 挂载路由/注册路由
app.include_router(news.router)
app.include_router(users.router)
app.include_router(favorite.router)
app.include_router(history.router)
app.include_router(ai_chat.router)
