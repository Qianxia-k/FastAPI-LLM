from dataclasses import dataclass
from pathlib import Path
import os

CURRENT_FILE = Path(__file__).resolve()
BACKEND_DIR = CURRENT_FILE.parent.parent

@dataclass
class IngestConfig:
    collection_name: str = "news_rag"
    persist_directory: str = str(BACKEND_DIR / "chroma_db")
    chunk_size: int = 800
    chunk_overlap: int = 120
    db_fetch_batch_size: int = 200
    write_batch_size: int = 100
    recreate_collection: bool = False
    dry_run: bool = False


def load_config_from_env() -> IngestConfig:
    """Load Chroma ingest configuration from environment variables with sane defaults.

    Environment variables:
      - CHROMA_COLLECTION_NAME
      - CHROMA_PERSIST_DIR
      - CHROMA_CHUNK_SIZE
      - CHROMA_CHUNK_OVERLAP
      - CHROMA_DB_FETCH_BATCH_SIZE
      - CHROMA_WRITE_BATCH_SIZE
      - CHROMA_RECREATE_COLLECTION
      - CHROMA_DRY_RUN
    """
    return IngestConfig(
        collection_name=os.getenv("CHROMA_COLLECTION_NAME", "news_rag"),
        persist_directory=os.getenv("CHROMA_PERSIST_DIR", str(BACKEND_DIR / "chroma_db")),
        chunk_size=int(os.getenv("CHROMA_CHUNK_SIZE", "500")),
        chunk_overlap=int(os.getenv("CHROMA_CHUNK_OVERLAP", "100")),
        db_fetch_batch_size=int(os.getenv("CHROMA_DB_FETCH_BATCH_SIZE", "5")),#一次从数据库读取的新闻chunks数。
        write_batch_size = int(os.getenv("CHROMA_WRITE_BATCH_SIZE", "5")),
        recreate_collection = os.getenv("CHROMA_RECREATE_COLLECTION", "false").lower() in ("1", "true", "yes"),
        dry_run=os.getenv("CHROMA_DRY_RUN", "false").lower() in ("1", "true", "yes"),
    )
