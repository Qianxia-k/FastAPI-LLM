import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Iterable, Sequence

from dotenv import load_dotenv
import shutil
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import DashScopeEmbeddings

CURRENT_FILE = Path(__file__).resolve()
BACKEND_DIR = CURRENT_FILE.parents[2]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _load_env() -> None: #加载环境变量，优先加载 backend/.env 文件，同时兼容从 backend 目录直接执行时的默认行为。这样可以确保在运行脚本时能够正确加载所需的环境变量，例如数据库连接URL、API密钥等，从而保证脚本的正常运行。
    # 优先加载 backend/.env，同时兼容从 backend 目录直接执行时的默认行为
    load_dotenv(BACKEND_DIR / ".env")
    load_dotenv()

_load_env()

from config.db_conf import AsyncSessionLocal
from config.chroma_conf import IngestConfig, load_config_from_env
from models.news import News



def _setup_logging() -> None:#设置日志配置，指定日志级别、格式等。这样可以确保在运行脚本时能够输出有用的日志信息，帮助开发者了解脚本的执行过程和调试问题。
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )



def _get_dashscope_api_key() -> str:
    # 与项目现有 ai_chat 模块保持一致：兼容两种变量名
    return os.getenv("DASHSCOPE_API_KEY") or os.getenv("ali_access_key") or ""


def _build_embedding_model() -> DashScopeEmbeddings:
    api_key = _get_dashscope_api_key()
    if not api_key:
        raise RuntimeError("未检测到 DashScope API Key，请在 .env 中配置 DASHSCOPE_API_KEY 或 ali_access_key")

    return DashScopeEmbeddings(
        model=os.getenv("DASHSCOPE_EMBEDDING_MODEL", "text-embedding-v3"),#默认使用 DashScope 的 text-embedding-v3 模型，这个模型在文本向量化方面表现良好，适合大多数应用场景。如果需要使用其他模型，可以通过环境变量 DASHSCOPE_EMBEDDING_MODEL 来指定，例如 "text-embedding-v2" 或 "text-embedding-3-small" 等。这样可以根据实际需求选择不同的模型，以获得更好的性能或更快的速度。
        dashscope_api_key=api_key,
        max_retries=3,#增加重试机制，提升稳定性，尤其是在批量处理大量文本时，偶尔可能遇到网络问题或API限制导致请求失败，重试可以帮助自动恢复并完成任务
    )


def _build_vector_store(config: IngestConfig) -> Chroma:#构建 Chroma 向量库实例，使用 DashScopeEmbeddings 作为嵌入模型，并配置持久化目录和集合名称。如果指定了 recreate_collection 参数为 True，则会先删除已存在的同名集合，再创建一个新的集合。这确保了在每次运行脚本时都能从一个干净的状态开始，避免旧数据的干扰。同时，通过 collection_metadata 设置 HNSW 索引的空间类型为 cosine，以优化基于余弦相似度的向量搜索性能。
    embedding_model = _build_embedding_model()

    # 如果要求重建集合，删除持久化目录以确保从干净状态开始（兼容不同 Chroma 客户端实现）
    persist_dir = Path(config.persist_directory)
    if config.recreate_collection and persist_dir.exists():
        logging.info("删除旧持久化目录: %s", config.persist_directory)
        shutil.rmtree(persist_dir)

    vector_store = Chroma(
        collection_name=config.collection_name,
        embedding_function=embedding_model,
        persist_directory=config.persist_directory,
        collection_metadata={"hnsw:space": "cosine"},
    )
    return vector_store


def _build_text_splitter(config: IngestConfig) -> RecursiveCharacterTextSplitter:
    if config.chunk_overlap >= config.chunk_size:
        raise ValueError("chunk_overlap 必须小于 chunk_size")

    return RecursiveCharacterTextSplitter(
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
        separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
    )


def _compose_news_text(news: News) -> str:
    parts = [
        f"标题: {news.title}",
    ]
    if news.description:
        parts.append(f"摘要: {news.description}")
    if news.author:
        parts.append(f"作者: {news.author}")
    parts.append("正文:")
    parts.append(news.content)
    return "\n".join(parts)


def _build_documents_for_news(news: News, splitter: RecursiveCharacterTextSplitter) -> tuple[list[Document], list[str]]:
    raw_text = _compose_news_text(news)
    chunks = splitter.split_text(raw_text)
    total_chunks = len(chunks)
    documents: list[Document] = []
    ids: list[str] = []

    publish_time = news.publish_time.isoformat() if news.publish_time else None

    for idx, chunk in enumerate(chunks):
        doc_id = f"news-{news.id}-chunk-{idx}"
        doc = Document(
            page_content=chunk,
            metadata={
                "news_id": news.id,
                "chunk_index": idx,
                "chunk_total": total_chunks,
                "title": news.title,
                "category_id": news.category_id,
                "author": news.author or "",
                "publish_time": publish_time or "",
                "source": "mysql.news",
            },
        )
        documents.append(doc)
        ids.append(doc_id)

    return documents, ids


async def _fetch_news_batch(db: AsyncSession, offset: int, limit: int) -> Sequence[News]:
    stmt: Select[tuple[News]] = select(News).order_by(News.id.asc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


def _iter_slices(items: Sequence, size: int) -> Iterable[Sequence]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


async def ingest_news_to_chroma(config: IngestConfig) -> None:
    logger = logging.getLogger("news_rag_ingest")
    splitter = _build_text_splitter(config)
    vector_store = _build_vector_store(config)

    total_news = 0
    total_chunks = 0
    offset = 0

    async with AsyncSessionLocal() as db:
        while True:
            news_batch = await _fetch_news_batch(db, offset=offset, limit=config.db_fetch_batch_size)
            if not news_batch:
                break

            logger.info("读取新闻批次: offset=%s, size=%s", offset, len(news_batch))

            for news in news_batch:
                documents, ids = _build_documents_for_news(news, splitter)
                if not documents:
                    logger.warning("新闻无有效内容，跳过: news_id=%s", news.id)
                    continue

                if config.dry_run:
                    total_news += 1
                    total_chunks += len(documents)
                    continue

                # 幂等更新：先按 news_id 删除，再写入当前最新切片。
                vector_store.delete(where={"news_id": news.id})#

                for doc_slice, id_slice in zip(
                    _iter_slices(documents, config.write_batch_size),
                    _iter_slices(ids, config.write_batch_size),
                ):
                    vector_store.add_documents(list(doc_slice), ids=list(id_slice))

                total_news += 1
                total_chunks += len(documents)

            offset += len(news_batch)

    logger.info(
        "入库完成: collection=%s, total_news=%s, total_chunks=%s, persist_dir=%s",
        config.collection_name,
        total_news,
        total_chunks,
        config.persist_directory,
    )
if __name__ == "__main__":
    _setup_logging()
    _load_env()
    config = load_config_from_env()
    # 确保在脚本退出前优雅关闭 SQLAlchemy async engine，避免析构期间尝试在已关闭的 event loop 上调度回调
    from config.db_conf import async_engine

    async def _main():
        try:
            await ingest_news_to_chroma(config)
        finally:
            try:
                await async_engine.dispose()
            except Exception:
                pass

    asyncio.run(_main())


