import os
from functools import lru_cache

from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.vectorstores import Chroma

from config.chroma_conf import load_config_from_env


def _get_dashscope_key() -> str:
    return os.getenv("DASHSCOPE_API_KEY") or os.getenv("ali_access_key") or ""


@lru_cache(maxsize=1)
def get_news_retriever():
    """
    获取全局单一的 Chroma Retriever 实例，避免每次请求重复初始化和加载模型参数。
    使用 LRU 缓存保证整个应用生命周期内只实例化一次。
    """
    api_key = _get_dashscope_key()
    if not api_key:
        raise RuntimeError("服务端未配置 DASHSCOPE_API_KEY，无法初始化检索器")

    chroma_config = load_config_from_env()
    
    embeddings = DashScopeEmbeddings(
        model=os.getenv("DASHSCOPE_EMBEDDING_MODEL", "text-embedding-v3"),
        dashscope_api_key=api_key
    )
    
    vector_store = Chroma(
        collection_name=chroma_config.collection_name,
        persist_directory=chroma_config.persist_directory,
        embedding_function=embeddings
    )
    
    # 默认返回最相关的5条新闻切片，避免过长的 context 导致大模型崩溃或计费过高
    # 可以根据您的实际需要修改 k 的值
    return vector_store.as_retriever(search_kwargs={"k": 5})
