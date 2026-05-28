from datetime import datetime

from dotenv import load_dotenv

from langchain.agents import create_agent
from langchain.tools import tool

from tavily import TavilyClient
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from langchain_core.documents import Document

import uuid

load_dotenv()

# =========================
# Tavily 搜索客户端
# =========================

tavily_client = TavilyClient()

print("正在加载模型success")

# =========================
# Embedding 模型
# =========================

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

print("加载成功")

# =========================
# 向量数据库
# =========================

vector_store = Chroma(
    collection_name="chat_memory",
    embedding_function=embeddings,
    persist_directory="./memory_db"
)


# =========================
# 搜索工具
# =========================

@tool
def search_web(query: str) -> str:
    """联网搜索最新新闻和实时信息"""

    try:

        current_date = datetime.now().strftime("%Y-%m-%d")

        response = tavily_client.search(
            query=f"{query} 最新新闻 {current_date}",
            max_results=5,
            topic="news",
            days=1
        )

        results = []

        for item in response["results"]:
            results.append(
                f"""
标题:
{item['title']}

内容:
{item['content']}

链接:
{item['url']}
                """
            )

        return "\n".join(results)

    except Exception as e:

        return str(e)


# =========================
# 创建 Agent
# =========================

agent = create_agent(
    model="deepseek:deepseek-chat",
    tools=[search_web],
    system_prompt="""
你是一个拥有长期记忆能力的AI助手。

规则：

1. 最新新闻、实时信息：
使用 search_web

2. 你应该结合历史记忆回答用户。
"""
)


# =========================
# 获取历史记忆
# =========================


def get_memory(query: str) -> str:
    docs = vector_store.similarity_search(
        query,
        k=3
    )

    if not docs:
        return ""

    memory_text = []

    for doc in docs:
        memory_text.append(doc.page_content)

    return "\n".join(memory_text)


# =========================
# 保存记忆
# =========================


def save_memory(user_input: str, ai_output: str):
    memory = f"""
用户：{user_input}
AI：{ai_output}
    """

    doc = Document(
        page_content=memory,
        metadata={
            "id": str(uuid.uuid4())
        }
    )

    vector_store.add_documents([doc])


# =========================
# 聊天循环
# =========================

while True:

    question = input("\n请输入问题：")

    if question == "exit":
        break

    # 获取相关历史记忆
    memory = get_memory(question)

    # 拼接上下文
    messages = [
        {
            "role": "system",
            "content": f"""
下面是与你相关的历史记忆：

{memory}
            """
        },
        {
            "role": "user",
            "content": question
        }
    ]

    # 调用 Agent
    response = agent.invoke({
        "messages": messages
    })

    ai_answer = response["messages"][-1].content

    print("\nAI回答：")

    print(ai_answer)

    # 保存长期记忆
    save_memory(question, ai_answer)
