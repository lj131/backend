"""
Embedding Manager

封装 Embedding 函数，支持 provider 切换和模块级缓存单例。

支持的 Provider:
- fastembed (默认): 使用 BGE 中文模型，纯 ONNX 本地运行，免费，零 API 费用
- openai (可选): 使用 OpenAI Embeddings API，需付费
- huggingface (可选): 使用 sentence-transformers，需 PyTorch

环境变量:
- EMBEDDING_PROVIDER: 选择 provider，默认 "fastembed"
- EMBEDDING_MODEL: fastembed 默认 "BAAI/bge-small-zh-v1.5"
- OPENAI_API_KEY: OpenAI provider 需要
- OPENAI_BASE_URL: 可选，自定义 OpenAI 兼容的 base URL
"""

import os
import time

from chromadb.api.types import EmbeddingFunction

_embedding_instance = None
_current_provider = None
_preloaded = False

# ============================================================
# FastEmbed Provider（默认，免费本地）
# ============================================================


class _FastEmbedFunction(EmbeddingFunction):
    """FastEmbed → ChromaDB EmbeddingFunction 适配器"""

    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5"):
        from fastembed import TextEmbedding
        self._model_name = model_name
        self._model = TextEmbedding(model_name=model_name)

    def __call__(self, input: list[str]) -> list[list[float]]:
        embeddings = list(self._model.embed(input))
        return [e.tolist() for e in embeddings]


# ============================================================
# 公开 API
# ============================================================


def preload(provider: str | None = None):
    """
    预热：在应用启动时提前加载 Embedding 模型。

    用法:
        from funcation.embedding_manager import preload
        preload()
    """
    global _preloaded
    if _preloaded:
        return
    try:
        t0 = time.time()
        get_embedding_function(provider)
        elapsed = time.time() - t0
        p = provider or os.getenv("EMBEDDING_PROVIDER", "fastembed")
        print(f"[EmbeddingManager] 预热完成 ({elapsed:.1f}s) — provider={p}")
        _preloaded = True
    except Exception as e:
        print(f"[EmbeddingManager] 预热跳过: {e}")
        print("[EmbeddingManager] 将在首次请求时自动加载")


def get_embedding_function(provider: str | None = None):
    """
    返回缓存的 ChromaDB 兼容的 embedding function 实例。

    参数:
        provider: "fastembed" | "openai" | "huggingface"

    返回:
        chromadb.api.types.EmbeddingFunction 实例
    """
    global _embedding_instance, _current_provider

    if provider is None:
        provider = os.getenv("EMBEDDING_PROVIDER", "fastembed")

    # 缓存命中
    if _embedding_instance is not None and _current_provider == provider:
        return _embedding_instance

    _current_provider = provider
    t0 = time.time()

    if provider == "fastembed":
        model_name = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
        print(f"[EmbeddingManager] 加载 FastEmbed 模型: {model_name} ...")
        _embedding_instance = _FastEmbedFunction(model_name=model_name)
        print(
            f"[EmbeddingManager] FastEmbed 就绪 ({time.time() - t0:.1f}s)"
        )

    elif provider == "openai":
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY 环境变量未设置。"
                "请在 .env 文件中添加 OPENAI_API_KEY=your-key"
            )
        base_url = os.getenv("OPENAI_BASE_URL")
        model_name = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        kwargs = {"api_key": api_key, "model_name": model_name}
        if base_url:
            kwargs["base_url"] = base_url
        _embedding_instance = OpenAIEmbeddingFunction(**kwargs)
        print(
            f"[EmbeddingManager] OpenAI Embedding 就绪 ({time.time() - t0:.1f}s)"
        )

    elif provider == "huggingface":
        from chromadb.utils.embedding_functions import (
            SentenceTransformerEmbeddingFunction,
        )
        model_name = os.getenv(
            "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
        print(f"[EmbeddingManager] 加载 HuggingFace 模型: {model_name} ...")
        _embedding_instance = SentenceTransformerEmbeddingFunction(
            model_name=model_name,
            device="cpu",
            normalize_embeddings=True,
        )
        print(
            f"[EmbeddingManager] HuggingFace 就绪 ({time.time() - t0:.1f}s)"
        )

    else:
        raise ValueError(
            f"不支持的 Embedding provider: {provider}。"
            f"支持: fastembed, openai, huggingface"
        )

    return _embedding_instance


def reset_embedding_cache():
    """清除缓存的 embedding 实例"""
    global _embedding_instance, _current_provider, _preloaded
    _embedding_instance = None
    _current_provider = None
    _preloaded = False


def is_preloaded() -> bool:
    return _preloaded
