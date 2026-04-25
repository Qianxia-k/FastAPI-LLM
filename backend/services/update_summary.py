import logging
from pathlib import Path

from utils.create_prompt import load_template_text
from crud import ai_chat as ai_chat_crud
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
SUMMARY_PROMPT_TEMPLATE_PATH = BASE_DIR / "config" / "summary_system_prompt.txt"

def _extract_assistant_text(response_json: dict) -> str:#从模型接口的响应中提取助手回复文本，兼容不同接口的响应格式
    return (
        response_json.get("choices", [{}])[0].get("message", {}).get("content", "")
        or response_json.get("output", {}).get("text", "")
        or ""
    ).strip()


def _format_recent_messages_for_summary(recent_messages: list) -> str:
    # get_recent_chat_messages 默认是倒序，这里反转成时间正序
    lines: list[str] = []
    for msg in reversed(recent_messages):
        role = getattr(msg, "role", "unknown")
        content = getattr(msg, "content", "")
        if content:
            lines.append(f"[{role}] {content}")
    return "\n".join(lines)


async def refresh_session_summary_if_needed(
    db: AsyncSession,
    user_id: int,
    session_id: str,
    last_summary_index: int,
    current_index: int,
    api_endpoint: str,
    api_key: str,
    model_name: str,
) -> None:
    # 简化策略：message_index 超过 10 即触发一次更新
    if current_index <= 10:
        return
    if current_index - last_summary_index <= 10:
        return

    last_summary_index = current_index
    old_summary = await ai_chat_crud.get_chat_session_summary(db, user_id, session_id)
    recent_messages = await ai_chat_crud.get_recent_chat_messages(db, user_id, session_id, limit=10)
    recent_dialogue_text = _format_recent_messages_for_summary(recent_messages)  # orm对象转换成文本格式，作为生成摘要的输入

    if not recent_dialogue_text:
        return

    system_prompt_text = load_template_text(SUMMARY_PROMPT_TEMPLATE_PATH)

    final_messages: list[dict[str, str]] = []
    clean_system_prompt = system_prompt_text.strip()
    if clean_system_prompt:
        final_messages.append({"role": "system", "content": clean_system_prompt})
    # 旧摘要和新增对话放在 user 消息中，避免把业务输入全部塞到 system 造成模型行为偏移
    payload_text_parts: list[str] = []
    if old_summary and old_summary.strip():
        payload_text_parts.append(f"【旧摘要】\n{old_summary.strip()}")
    payload_text_parts.append(f"【近期对话】\n{recent_dialogue_text.strip()}")
    #payload_text_parts.append("请基于以上内容输出整合后的新会话摘要")

    final_messages.append({"role": "user", "content": "\n\n".join(payload_text_parts)})

    req_json = {  # 请求参数，最终会转换成json字符串发送给上游模型服务
        "model": model_name,
        "messages": final_messages,
        "stream": False,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "X-DashScope-SSE": "enable",
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(api_endpoint, headers=headers, json=req_json)
            if resp.status_code >= 400:
                logger.warning(
                    "summary refresh upstream returned error status",
                    extra={
                        "user_id": user_id,
                        "session_id": session_id,
                        "status_code": resp.status_code,
                        "current_index": current_index,
                    },
                )
                return

            resp_json = resp.json()
            new_summary = _extract_assistant_text(resp_json)
            if new_summary:
                await ai_chat_crud.update_chat_session_summary(
                    db,
                    user_id,
                    session_id,
                    new_summary,
                    last_summary_index,
                )
    except httpx.RequestError as exc:
        logger.exception(
            "summary refresh request failed",
            extra={
                "user_id": user_id,
                "session_id": session_id,
                "current_index": current_index,
                "error": str(exc),
            },
        )
    except ValueError as exc:
        logger.exception(
            "summary refresh parse failed",
            extra={
                "user_id": user_id,
                "session_id": session_id,
                "current_index": current_index,
                "error": str(exc),
            },
        )
    except Exception as exc:
        # 摘要更新失败不影响主链路
        logger.exception(
            "summary refresh unexpected error",
            extra={
                "user_id": user_id,
                "session_id": session_id,
                "current_index": current_index,
                "error": str(exc),
            },
        )