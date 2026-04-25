from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from chromadb import PersistentClient

CURRENT_FILE = Path(__file__).resolve()
BACKEND_DIR = CURRENT_FILE.parents[2]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config.chroma_conf import load_config_from_env


def _load_env() -> None:
    # 与 add_to_chroma.py 保持一致：优先读取 backend/.env
    load_dotenv(BACKEND_DIR / ".env")
    load_dotenv()


def _build_parser() -> argparse.ArgumentParser:
    cfg = load_config_from_env()
    parser = argparse.ArgumentParser(description="Inspect ChromaDB contents")
    parser.add_argument(
        "--persist-dir",
        default=cfg.persist_directory,
        help="Chroma persist directory (default: from config.chroma_conf.load_config_from_env)",
    )
    parser.add_argument(
        "--collection",
        default=cfg.collection_name,
        help="Collection name to inspect (default: from config.chroma_conf.load_config_from_env)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="How many rows to fetch for sample output (default: 10)",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Offset for sampling (default: 0)",
    )
    parser.add_argument(
        "--news-id",
        type=int,
        default=None,
        help="Filter rows by metadata.news_id",
    )
    parser.add_argument(
        "--show-doc-len",
        type=int,
        default=200,
        help="Preview length for each document (default: 200 chars)",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Only list collections and counts, do not print sample rows",
    )
    return parser


def _safe_get_collection_count(client: PersistentClient, name: str) -> int | None:
    try:
        col = client.get_collection(name)
        return col.count()
    except Exception:
        return None


def _print_collection_overview(client: PersistentClient) -> list[str]:
    cols = client.list_collections()
    names = [c.name for c in cols]
    print("=== Collections ===")
    if not names:
        print("(none)")
        return names

    for n in names:
        cnt = _safe_get_collection_count(client, n)
        cnt_str = str(cnt) if cnt is not None else "?"
        print(f"- {n} (count={cnt_str})")
    return names


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def _fetch_rows(collection: Any, *, limit: int, offset: int, news_id: int | None) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "include": ["documents", "metadatas"],
        "limit": limit,
        "offset": offset,
    }
    if news_id is not None:
        kwargs["where"] = {"news_id": news_id}
    return collection.get(**kwargs)


def _print_rows(rows: dict[str, Any], show_doc_len: int) -> None:
    ids = rows.get("ids", []) or []
    docs = rows.get("documents", []) or []
    metas = rows.get("metadatas", []) or []

    print(f"\n=== Sample Rows ({len(ids)}) ===")
    if not ids:
        print("(no matched rows)")
        return

    for idx, row_id in enumerate(ids, start=1):
        doc = docs[idx - 1] if idx - 1 < len(docs) else ""
        meta = metas[idx - 1] if idx - 1 < len(metas) else {}

        print(f"\n[{idx}] id={row_id}")
        print("metadata:", json.dumps(meta, ensure_ascii=False))
        doc_preview = _truncate((doc or "").replace("\n", " "), show_doc_len)
        print("document:", doc_preview)


def main() -> None:
    _load_env()
    parser = _build_parser()
    args = parser.parse_args()

    persist_dir = Path(args.persist_dir).expanduser().resolve()
    print(f"Persist dir: {persist_dir}")

    if not persist_dir.exists():
        raise SystemExit(f"Persist dir not found: {persist_dir}")

    client = PersistentClient(path=str(persist_dir))
    names = _print_collection_overview(client)

    if args.list_only:
        return

    if args.collection not in names:
        raise SystemExit(
            f"Collection '{args.collection}' not found. Existing: {', '.join(names) if names else '(none)'}"
        )

    collection = client.get_collection(args.collection)
    print(f"\nUsing collection: {args.collection}")
    print(f"Total rows: {collection.count()}")

    rows = _fetch_rows(
        collection,
        limit=max(args.limit, 0),
        offset=max(args.offset, 0),
        news_id=args.news_id,
    )
    _print_rows(rows, show_doc_len=max(args.show_doc_len, 1))


if __name__ == "__main__":
    main()
