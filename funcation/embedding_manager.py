"""
Embedding Manager

封装 Embedding 函数，支持 provider 切换和模块级缓存单例。

支持的 Provider:
- openai (默认): 使用 OpenAI Embeddings API（纯 HTTP，无需本地 GPU/库）
- huggingface: 使用 sentence-transformers 本地运行（需要 PyTorch 或 ONNX Runtime）

环境变量:
- EMBEDDING_PROVIDER: 选择 provider，默认 "openai"
- EMBEDDING_MODEL: 模型名，openai 默认 "text-embedding-3-small"
- OPENAI_API_KEY: OpenAI provider 需要
- OPENAI_BASE_URL: 可选，自定义 OpenAI 兼容的 base URL
"""

import os

_embedding_instance = None
_current_provider = None


def get_embedding_function(provider: str | None = None):
    """
    返回缓存的 ChromaDB 兼容的 embedding function 实例。

    参数:
        provider: "openai" | "huggingface"，默认从 EMBEDDING_PROVIDER 环境变量读取

    返回:
        chromadb.api.types.EmbeddingFunction 实例
    """
    global _embedding_instance, _current_provider

    if provider is None:
        provider = os.getenv("EMBEDDING_PROVIDER", "openai")

    # 如果 provider 没变且已有缓存实例，直接返回
    if _embedding_instance is not None and _current_provider == provider:
        return _embedding_instance

    _current_provider = provider

    if provider == "openai":
        from chromadb.utils.embedding_functions import (
            OpenAIEmbeddingFunction,
        )

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY 环境变量未设置。"
                "请在 .env 文件中添加 OPENAI_API_KEY=your-key"
            )

        base_url = os.getenv("OPENAI_BASE_URL")
        model_name = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

        print(f"[EmbeddingManager] 使用 OpenAI Embedding: {model_name}")
        kwargs = {
            "api_key": api_key,
            "model_name": model_name,
        }
        if base_url:
            kwargs["base_url"] = base_url
        _embedding_instance = OpenAIEmbeddingFunction(**kwargs)

    elif provider == "huggingface":
        from chromadb.utils.embedding_functions import (
            SentenceTransformerEmbeddingFunction,
        )

        model_name = os.getenv(
            "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
        print(f"[EmbeddingManager] 加载 HuggingFace 模型: {model_name}")
        _embedding_instance = SentenceTransformerEmbeddingFunction(
            model_name=model_name,
            device="cpu",
            normalize_embeddings=True,
        )
        print("[EmbeddingManager] 加载完成")

    else:
        raise ValueError(
            f"不支持的 Embedding provider: {provider}。"
            f"支持: openai, huggingface"
        )

    return _embedding_instance


def reset_embedding_cache():
    """清除缓存的 embedding 实例，强制下次调用重新初始化"""
    global _embedding_instance, _current_provider
    _embedding_instance = None
    _current_provider = None
