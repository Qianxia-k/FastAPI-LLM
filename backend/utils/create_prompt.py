from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

BASE_DIR = Path(__file__).resolve().parent.parent
SYSTEM_PROMPT_TEMPLATE_PATH = BASE_DIR / "config" / "system_prompt.txt"
USER_PROMPT_TEMPLATE_PATH = BASE_DIR / "config" / "user_prompt.txt"

#--------------当不使用langchain组织prompt流时，可以使用以下方法自己组织messages然后输入上游模型
def load_template_text(template_path: str | Path) -> str:
    """
    读取 prompt 模板文本。

    模板文件只负责固定规则，不直接混业务查询逻辑。
    """
    path = Path(template_path)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.read_text(encoding="utf-8").strip()


def load_system_prompt_text() -> str:
    return load_template_text(SYSTEM_PROMPT_TEMPLATE_PATH)


def load_user_prompt_text() -> str:
    return load_template_text(USER_PROMPT_TEMPLATE_PATH)


def extract_latest_user_query(messages: Iterable[Any]) -> str:
    """
    从前端传来的消息中提取最新一条 user 消息作为当前问题。

    支持 Pydantic 对象或 dict，避免路由层直接依赖消息结构细节。
    """
    for message in reversed(list(messages)):
        role = getattr(message, "role", None)
        content = getattr(message, "content", None)
        if role is None and isinstance(message, dict):
            role = message.get("role")
            content = message.get("content")
        if role == "user" and isinstance(content, str) and content.strip():
            return content.strip()
    raise ValueError("未找到有效的用户问题，请检查请求 messages 是否包含 user 消息")


def _normalize_history_message(item: Any) -> dict[str, str] | None:
    """
    将 ORM 对象或 dict 统一转换成上游模型可接收的消息格式。
    """
    role = getattr(item, "role", None)
    content = getattr(item, "content", None)

    if role is None and isinstance(item, dict):
        role = item.get("role")
        content = item.get("content")

    if not role or content is None:
        return None

    return {"role": str(role), "content": str(content)}


def build_chat_messages(
    system_prompt: str,
    summary: str | None,
    history: Iterable[Any],
    question: str,
    user_prompt_template: str | None = None,
) -> list[dict[str, str]]:
    """
    组装最终发给大模型的 messages。

    推荐顺序：
    1. system prompt（固定规则）
    2. 会话摘要（长期上下文）
    3. 最近历史消息（短期上下文）
    4. 当前用户问题（本轮输入）
    """
    final_messages: list[dict[str, str]] = []

    clean_system_prompt = system_prompt.strip()
    if clean_system_prompt:
        final_messages.append({"role": "system", "content": clean_system_prompt})

    if summary and summary.strip():
        final_messages.append({"role": "system", "content": f"【会话摘要】\n{summary.strip()}"})

    # CRUD 默认按倒序取最近消息，这里反转成时间正序后再送给模型
    normalized_history: list[dict[str, str]] = []
    for item in reversed(list(history)):
        normalized_item = _normalize_history_message(item)
        if normalized_item:
            normalized_history.append(normalized_item)

    final_messages.extend(normalized_history)

    question = question.strip()
    if user_prompt_template and user_prompt_template.strip():
        try:
            user_content = user_prompt_template.strip().format(query=question)
        except (KeyError, IndexError, ValueError):
            user_content = f"{user_prompt_template.strip()}\n{question}"
    else:
        user_content = question

    final_messages.append({"role": "user", "content": user_content})
    return final_messages
#----------------------------当使用langchain时组织prompt
def build_langchain_summary_history(summary, recent_context):
    recent_messages= []
    if summary and summary.strip():
        recent_messages.append(SystemMessage(content=f"【会话摘要】\n{summary.strip()}"))

    for item in reversed(list(recent_context)):
        role = getattr(item, "role", "user") if not isinstance(item, dict) else item.get("role")
        content = getattr(item, "content", "") if not isinstance(item, dict) else item.get("content", "")
        if not content:
            continue
        if role == "assistant":
            recent_messages.append(AIMessage(content=content))
        else:
            recent_messages.append(HumanMessage(content=content))
    return recent_messages