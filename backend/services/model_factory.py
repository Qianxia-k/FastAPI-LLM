import os
from functools import lru_cache

from langchain_community.chat_models import ChatTongyi


def _get_dashscope_key() -> str:
    return os.getenv("DASHSCOPE_API_KEY") or os.getenv("ali_access_key") or ""


@lru_cache(maxsize=1)
def get_chat_model() -> ChatTongyi:
    """Get a singleton LangChain chat model instance (Tongyi/Qwen via DashScope)."""
    api_key = _get_dashscope_key()
    if not api_key:
        raise RuntimeError("服务端未配置 DASHSCOPE_API_KEY，无法初始化 LangChain Chat 模型")

    model_name = os.getenv("DASHSCOPE_CHAT_MODEL", "qwen-max")
    return ChatTongyi(
        model_name=model_name,
        dashscope_api_key=api_key,
        streaming=True,
    )
