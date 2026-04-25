import json
import os

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

from config.db_conf import get_db
from crud import ai_chat as ai_chat_crud
from models.users import User
from utils.response import success_response
from utils.auth import get_current_user
from utils.create_prompt import (
    extract_latest_user_query,
    load_template_text,
    build_langchain_summary_history
)
from schemas.ai_chat import AIChatRequest, ChatMessage, ChatSessionResponse, ChatSessionMessagesResponse
from services.update_summary import refresh_session_summary_if_needed
from services.retriever_factory import get_news_retriever
from services.model_factory import get_chat_model
from services.get_retrievel import get_retrievel_chain

from utils.create_prompt import SYSTEM_PROMPT_TEMPLATE_PATH, USER_PROMPT_TEMPLATE_PATH


load_dotenv()

router = APIRouter(prefix="/api/ai", tags=["ai"])

def _get_dashscope_key() -> str:
    # 兼容不同环境变量命名，意义不大，只写自己写死的那个就可以了，主要是为了演示在不同环境变量命名之间切换的逻辑
    return os.getenv("DASHSCOPE_API_KEY") or os.getenv("ali_access_key") or ""

@router.get("/sessions")
async def get_chat_sessions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sessions = await ai_chat_crud.get_user_chat_sessions(db, user.id, limit=100)
    data = [
        ChatSessionResponse(
            session_id=s.session_id,
            title=s.title,
            summary=s.summary
        )
        for s in sessions
    ]
    return success_response(message="获取用户会话记录成功", data=data)


@router.get("/sessions/{session_id}/messages")
async def get_chat_session_messages(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await ai_chat_crud.get_chat_session(db, user.id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在或不属于当前用户")

    messages = await ai_chat_crud.get_chat_content_by_session(db, user.id, session_id)
    response_data = ChatSessionMessagesResponse(
        session_id=session_id,
        messages=[
            ChatMessage(role=m.role, content=m.content)
            for m in messages
        ],
    )
    return success_response(data=response_data)


def _format_rag_docs(docs) -> str:#
    if not docs:
        return ""
    return "\n\n".join(
        "\n".join(
            [
                f"【标题】{doc.metadata.get('title', '未知标题')}",
                f"【发布时间】{doc.metadata.get('publish_time', '')}",
                f"【内容】{doc.page_content}",
            ]
        )
        for doc in docs
    )

def get_to_check(x):#将输入原封不动的输出，作为一个检查点，方便调试时查看数据流经过这个节点时的内容，类似于在代码中打一个断点观察变量值，但这个是在线上环境也可以使用的，输出会显示在模型生成的日志里
    print("****************当前数据流经过检查点，内容为：", x, "*****************")
    return x

@router.post("/chat")
async def ai_chat(
    payload: AIChatRequest,#前端传来的参数，是pydantic对象，路由层直接使用，调用payload里面的属性
    user: User = Depends(get_current_user),#根据传入的Token查询用户，获取当前用户信息
    db: AsyncSession = Depends(get_db),
):
    _ = user  # 保留鉴权依赖，后续可用于用户级限流、审计、记忆

    if payload.session_id:#这是是否创建新会话的逻辑，AIChatRequest里面有个session_id（可选参数），如果前端传了说明已经有会话，
        #用这个session_id去数据库查这个会话是否存在且属于当前用户，如果不存在就报错，如果存在就继续后续的聊天逻辑；
        #如果前端没传session_id，就创建一个新的会话，生成一个新的session_id，后续的聊天逻辑使用这个新的session_id
        current_session = await ai_chat_crud.get_chat_session(db, user.id, payload.session_id)
        if not current_session:#如果不存在这个会话，或者这个会话不属于当前用户，就报错
            raise HTTPException(status_code=404, detail="会话不存在或不属于当前用户")
        session_id = payload.session_id#存在会话则继续
    else:#没有传入会话id则直接创建新会话
        current_session = await ai_chat_crud.create_chat_session(db, user.id)
        session_id = current_session.session_id

    api_key = _get_dashscope_key()
    if not api_key:
        raise HTTPException(status_code=500, detail="服务端未配置 DASHSCOPE_API_KEY")

    api_endpoint = os.getenv(
        "DASHSCOPE_API_ENDPOINT",
        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    )

    system_prompt_text = load_template_text(SYSTEM_PROMPT_TEMPLATE_PATH)
    user_prompt_text = load_template_text(USER_PROMPT_TEMPLATE_PATH)

    # 获取当前用户本轮真正的问题：默认取最后一条 user 消息
    try:
        current_question = extract_latest_user_query(payload.messages)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # 获取 summary 和近期上下文（历史消息）
    summary = await ai_chat_crud.get_chat_session_summary(db, user.id, session_id)
    recent_context = await ai_chat_crud.get_recent_chat_messages(db, user.id, session_id, limit=10)

    try:
        # 1) 获取全局 LangChain Retriever（复用模式，不重复初始化）
        retriever = get_news_retriever()

        # 2) 准备历史消息（用于检索改写和回答生成）
        recent_messages = build_langchain_summary_history(summary, recent_context)
        print("=== 构建的历史消息（summary + recent messages） ===")
        print(recent_messages)
        # 3) 构建“历史感知检索语句链”：把当前问题 + recent_messages 改写成更可检索的 query
        retrieval_query_chain = get_retrievel_chain()
        chat_model = get_chat_model()

        # 4) 用 LangChain 统一组织生成 prompt（system + history + 当前用户输入）
        generation_prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt_text),
            MessagesPlaceholder(variable_name="recent_messages"),
            ("human", user_prompt_text if user_prompt_text.strip() else "{query}")
        ])

        # 5) 构建完整 RAG 生成链：检索改写 -> retriever -> 格式化 -> prompt -> model
        retrieval_input_chain = {
            "query": RunnablePassthrough(),
            "recent_messages": RunnableLambda(lambda _: recent_messages),
        } | retrieval_query_chain

        generation_chain = {
            "query": RunnablePassthrough(),
            "recent_messages": RunnableLambda(lambda _: recent_messages),
            "RAG_results": retrieval_input_chain | get_to_check | retriever | get_to_check | RunnableLambda(_format_rag_docs),
        } | generation_prompt | get_to_check | chat_model
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"RAG链初始化失败: {exc}")

    # 先保存当前用户消息，后续用于短期记忆
    await ai_chat_crud.add_chat_message(
        db=db,
        user_id=user.id,
        session_id=session_id,
        role="user",
        content=current_question,
        model_name=payload.model,
    )

    if payload.stream:
        async def stream_generator():
            assistant_text_parts: list[str] = []
            try:
                async for chunk in generation_chain.astream(current_question):
                    content = getattr(chunk, "content", "") or ""
                    if not content:
                        continue
                    assistant_text_parts.append(content)
                    sse_payload = {
                        "choices": [
                            {
                                "delta": {"content": content}
                            }
                        ]
                    }
                    yield f"data: {json.dumps(sse_payload, ensure_ascii=False)}\n\n".encode("utf-8")
            except Exception as exc:
                error_payload = {
                    "code": 502,
                    "message": "上游模型服务错误",
                    "data": None,
                    "error": {"message": str(exc)},
                }
                yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n".encode("utf-8")
                yield b"data: [DONE]\n\n"
                return

            yield b"data: [DONE]\n\n"

            assistant_text = "".join(assistant_text_parts).strip()
            if assistant_text:
                new_chat_message = await ai_chat_crud.add_chat_message(
                    db=db,
                    user_id=user.id,
                    session_id=session_id,
                    role="assistant",
                    content=assistant_text,
                    model_name=payload.model,
                    finish_reason="stop",
                )
                await refresh_session_summary_if_needed(db, user.id, session_id,current_session.last_summary_index, new_chat_message.message_index, api_endpoint, api_key, payload.model)

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={"X-Session-Id": session_id},
        )

    try:
        ai_message = await generation_chain.ainvoke(current_question)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"上游模型服务错误: {exc}")

    assistant_text = getattr(ai_message, "content", "") or ""
    resp_json = {
        "choices": [
            {
                "message": {"role": "assistant", "content": assistant_text},
                "finish_reason": "stop",
            }
        ]
    }

    if assistant_text:
        new_chat_message = await ai_chat_crud.add_chat_message(
            db=db,
            user_id=user.id,
            session_id=session_id,
            role="assistant",
            content=assistant_text,
            model_name=payload.model,
            finish_reason="stop",
        )
        await refresh_session_summary_if_needed(
            db,
            user.id,
            session_id,
            current_session.last_summary_index,
            new_chat_message.message_index,
            api_endpoint,
            api_key,
            payload.model,
        )

    return success_response(
        message="聊天成功",
        data={
            "session_id": session_id,
            "result": resp_json,
        },
    )
