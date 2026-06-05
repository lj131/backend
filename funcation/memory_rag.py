"""
Memory RAG — 长期记忆向量检索系统

基于 ChromaDB 实现，6 个独立集合按角色隔离：
- profile: 用户画像
- long_memory: 长期记忆
- story: 剧情记录
- events: 世界/角色事件
- relationship: 关系变化
- chat_summary: 聊天摘要

持久化目录: data/chroma/
"""

import hashlib
import os
import uuid

import chromadb
from chromadb.config import Settings

from funcation.embedding_manager import get_embedding_function

# ============================================================
# 常量
# ============================================================

PERSIST_DIR = os.path.join("data", "chroma")
COLLECTION_TYPES = [
    "profile",
    "long_memory",
    "story",
    "events",
    "relationship",
    "chat_summary",
]

COLLECTION_LABELS = {
    "profile": "用户信息",
    "long_memory": "长期记忆",
    "story": "剧情",
    "events": "事件",
    "relationship": "关系",
    "chat_summary": "聊天摘要",
}

# ============================================================
# 模块级单例
# ============================================================

_chroma_client = None


def _get_client() -> chromadb.PersistentClient:
    """返回持久化 ChromaDB 客户端单例"""
    global _chroma_client
    if _chroma_client is None:
        os.makedirs(PERSIST_DIR, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(
            path=PERSIST_DIR,
            settings=Settings(anonymized_telemetry=False),
        )
    return _chroma_client


# ============================================================
# 集合管理
# ============================================================


def _get_collection(character_id: str, collection_type: str):
    """
    获取指定角色和类型的 ChromaDB 集合（懒创建）。

    集合命名: {character_id}_{collection_type}
    """
    if collection_type not in COLLECTION_TYPES:
        raise ValueError(
            f"不支持的集合类型: {collection_type}。支持: {COLLECTION_TYPES}"
        )

    collection_name = f"{character_id}_{collection_type}"
    client = _get_client()
    ef = get_embedding_function()

    return client.get_or_create_collection(
        name=collection_name,
        embedding_function=ef,
        metadata={"character_id": character_id, "type": collection_type},
    )


# ============================================================
# CRUD 操作
# ============================================================


def add_memory(
    character_id: str,
    collection_type: str,
    text: str,
    metadata: dict | None = None,
) -> str:
    """
    添加一条记忆到向量库。

    返回:
        doc_id: 文档 ID
    """
    collection = _get_collection(character_id, collection_type)
    meta = metadata or {}
    meta.setdefault("character_id", character_id)

    doc_id = str(uuid.uuid4())
    collection.add(
        ids=[doc_id],
        documents=[text],
        metadatas=[meta],
    )
    return doc_id


def upsert_memory(
    character_id: str,
    collection_type: str,
    text: str,
    doc_id: str,
    metadata: dict | None = None,
) -> str:
    """
    插入或更新一条记忆（相同 doc_id 会覆盖）。

    返回:
        doc_id
    """
    collection = _get_collection(character_id, collection_type)
    meta = metadata or {}
    meta.setdefault("character_id", character_id)

    collection.upsert(
        ids=[doc_id],
        documents=[text],
        metadatas=[meta],
    )
    return doc_id


def update_memory(
    character_id: str,
    collection_type: str,
    old_text: str,
    new_text: str,
    metadata: dict | None = None,
) -> str | None:
    """
    更新一条记忆：相似度定位旧文档 → 删除 → 插入新文档。

    返回:
        新 doc_id，如果旧文档未找到则返回 None
    """
    collection = _get_collection(character_id, collection_type)

    # 相似度搜索定位旧文档
    try:
        results = collection.query(
            query_texts=[old_text],
            n_results=3,
            include=["documents", "metadatas"],
        )
    except Exception:
        # 集合为空时 query 可能抛异常
        return None

    if not results["ids"] or not results["ids"][0]:
        return None

    # 精确匹配内容
    old_id = None
    for i, doc in enumerate(results["documents"][0]):
        if doc.strip() == old_text.strip():
            old_id = results["ids"][0][i]
            break

    if old_id:
        collection.delete(ids=[old_id])

    # 插入新文档
    return add_memory(character_id, collection_type, new_text, metadata)


def delete_memory(
    character_id: str,
    collection_type: str,
    text: str,
) -> bool:
    """
    从向量库删除一条记忆（按文本精确匹配）。

    返回:
        True 如果找到并删除，False 如果未找到
    """
    collection = _get_collection(character_id, collection_type)

    try:
        results = collection.query(
            query_texts=[text],
            n_results=5,
            include=["documents"],
        )
    except Exception:
        return False

    if not results["ids"] or not results["ids"][0]:
        return False

    ids_to_delete = []
    for i, doc in enumerate(results["documents"][0]):
        if doc.strip() == text.strip():
            ids_to_delete.append(results["ids"][0][i])

    if ids_to_delete:
        collection.delete(ids=ids_to_delete)
        return True

    return False


# ============================================================
# 检索操作
# ============================================================


def _retrieve_single(
    character_id: str,
    collection_type: str,
    query: str,
    top_k: int = 3,
    world_id: str | None = None,
) -> list[dict]:
    """
    单个集合检索。

    参数:
        character_id: 角色 ID
        collection_type: 集合类型
        query: 查询文本
        top_k: 返回数量
        world_id: 可选的 world 过滤

    返回:
        [{"text": str, "collection": str, "score": float, "metadata": dict}, ...]
    """
    collection = _get_collection(character_id, collection_type)

    # 构建 where 过滤条件
    where_filter = None
    if world_id:
        where_filter = {"world_id": world_id}

    try:
        results = collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as e:
        print(f"[memory_rag] 检索 {collection_type} 失败: {e}")
        return []

    if not results["ids"] or not results["ids"][0]:
        return []

    items = []
    for i, doc_id in enumerate(results["ids"][0]):
        distance = (
            results["distances"][0][i]
            if results.get("distances")
            else 1.0
        )
        metadata = (
            results["metadatas"][0][i]
            if results.get("metadatas")
            else {}
        )
        items.append({
            "text": results["documents"][0][i],
            "collection": collection_type,
            "score": round(distance, 4),
            "metadata": metadata,
        })

    # 按距离升序（越小越相关）
    items.sort(key=lambda x: x["score"])
    return items


def retrieve_memories(
    character_id: str,
    query: str,
    top_k: int = 5,
    world_id: str | None = None,
) -> list[dict]:
    """
    跨所有 4 个集合检索，合并排序后返回 top_k 结果。

    返回:
        [{"text": str, "collection": str, "score": float, "metadata": dict}, ...]
    """
    all_items = []
    for ctype in COLLECTION_TYPES:
        items = _retrieve_single(character_id, ctype, query, top_k=top_k, world_id=world_id)
        all_items.extend(items)

    # 全局按距离排序
    all_items.sort(key=lambda x: x["score"])
    return all_items[:top_k]


def retrieve_profile(
    character_id: str,
    query: str,
    top_k: int = 3,
) -> list[dict]:
    """仅检索 profile 集合"""
    return _retrieve_single(character_id, "profile", query, top_k=top_k)


def retrieve_story(
    character_id: str,
    query: str,
    top_k: int = 3,
) -> list[dict]:
    """仅检索 story 集合"""
    return _retrieve_single(character_id, "story", query, top_k=top_k)


def retrieve_events(
    character_id: str,
    query: str,
    top_k: int = 3,
) -> list[dict]:
    """仅检索 events 集合"""
    return _retrieve_single(character_id, "events", query, top_k=top_k)


def retrieve_relationship(
    character_id: str,
    query: str,
    top_k: int = 3,
) -> list[dict]:
    """仅检索 relationship 集合"""
    return _retrieve_single(character_id, "relationship", query, top_k=top_k)


# ============================================================
# 全量读取
# ============================================================


def list_all_memories(
    character_id: str,
    collection_type: str,
    where_filter: dict | None = None,
    limit: int = 200,
) -> list[dict]:
    """
    列出集合中的所有文档（不进行语义检索）。

    参数:
        character_id: 角色 ID
        collection_type: 集合类型
        where_filter: 可选的元数据过滤
        limit: 最大返回数

    返回:
        [{"text": str, "metadata": dict}, ...]
    """
    collection = _get_collection(character_id, collection_type)
    try:
        results = collection.get(
            where=where_filter,
            limit=limit,
            include=["documents", "metadatas"],
        )
    except Exception:
        return []

    if not results["ids"]:
        return []

    items = []
    for i, doc_id in enumerate(results["ids"]):
        items.append({
            "id": doc_id,
            "text": results["documents"][i] if results["documents"] else "",
            "metadata": results["metadatas"][i] if results["metadatas"] else {},
        })
    return items


def delete_by_id(
    character_id: str,
    collection_type: str,
    doc_id: str,
) -> bool:
    """按 doc_id 删除文档"""
    collection = _get_collection(character_id, collection_type)
    try:
        collection.delete(ids=[doc_id])
        return True
    except Exception:
        return False


# ============================================================
# 统计
# ============================================================


def get_collection_stats(character_id: str) -> dict[str, int]:
    """返回各集合文档数量"""
    stats = {}
    for ctype in COLLECTION_TYPES:
        try:
            collection = _get_collection(character_id, ctype)
            stats[ctype] = collection.count()
        except Exception:
            stats[ctype] = 0
    return stats


# ============================================================
# 工具
# ============================================================


def purge_character(character_id: str) -> dict[str, int]:
    """删除指定角色的所有集合（用于重置）"""
    client = _get_client()
    deleted = {}
    for ctype in COLLECTION_TYPES:
        collection_name = f"{character_id}_{ctype}"
        try:
            client.delete_collection(collection_name)
            deleted[ctype] = 1
        except Exception:
            deleted[ctype] = 0
    return deleted


def purge_collection(character_id: str, collection_type: str) -> int:
    """清空指定集合的所有文档，返回删除数量"""
    collection = _get_collection(character_id, collection_type)
    try:
        count = collection.count()
        all_ids = collection.get(limit=count, include=[])["ids"]
        if all_ids:
            collection.delete(ids=all_ids)
        return len(all_ids)
    except Exception:
        return 0
