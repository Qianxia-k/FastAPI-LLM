from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from services.model_factory import get_chat_model
from utils.create_prompt import load_template_text


RETRIEVAL_PROMPT_TEMPLATE_PATH = "config/retrievel_rag_sysytem.txt"


def get_retrievel_chain():
    retrievel_system_prompt = load_template_text(RETRIEVAL_PROMPT_TEMPLATE_PATH)
    chat_model = get_chat_model()

    retrieval_query_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", retrievel_system_prompt),
            MessagesPlaceholder(variable_name="recent_messages"),
            (
                "human",
                "当前用户问题：{query}",
            ),
        ]
    )

    return retrieval_query_prompt | chat_model | StrOutputParser()