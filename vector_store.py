"""
向量数据库模块 - 基于ChromaDB的语义检索
用于存储和学习病例的向量表示，实现RAG增强检索
"""
import os
import json
import chromadb
from chromadb.config import Settings
from chromadb import EmbeddingFunction

# ========== 配置 ==========
VECTOR_DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".vector_db")
COLLECTION_NAME = "medical_cases"
EMBEDDING_MODEL = "local-tf-hash"  # 本地哈希向量（jieba分词，免费无API）

# ========== 嵌入函数（本地计算，无需任何 API） ==========
EMBED_DIM = 512

def glm_embedding(texts):
    """本地文本向量化：jieba 分词 + 哈希词频向量（免费、离线、无需余额）"""
    import jieba
    import hashlib
    if isinstance(texts, str):
        texts = [texts]
    results = []
    for t in texts:
        vec = [0.0] * EMBED_DIM
        for word in jieba.cut(t or ""):
            word = word.strip()
            if not word or len(word) < 2:
                continue
            h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
            vec[h % EMBED_DIM] += 1.0
        # L2 归一化
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        results.append(vec)
    return results

class ChromaDBEmbeddingFunction(EmbeddingFunction):
    """ChromaDB自定义嵌入函数 - 使用智谱AI"""
    def __init__(self):
        self._name = "qwen_embedding"
    
    def __call__(self, input):
        result = glm_embedding(input)
        if result is None:
            return [[0.0] * EMBED_DIM] * len(input)
        return result
    
    def name(self):
        return self._name
    # ========== ChromaDB 管理 ==========

_client = None
_collection = None

def get_client():
    global _client
    if _client is None:
        os.makedirs(VECTOR_DB_DIR, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=VECTOR_DB_DIR,
            settings=Settings(anonymized_telemetry=False)
        )
    return _client

def get_collection():
    global _collection
    if _collection is None:
        emb_fn = ChromaDBEmbeddingFunction()
        client = get_client()
        try:
            _collection = client.get_collection(
                name=COLLECTION_NAME,
                embedding_function=emb_fn
            )
        except Exception:
            _collection = client.create_collection(
                name=COLLECTION_NAME,
                embedding_function=emb_fn
            )
    return _collection

# ========== 核心操作 ==========

def add_case(case_id, case_text, diagnosis, department, severity, metadata=None):
    """添加一条病例到向量库"""
    try:
        col = get_collection()
        doc_id = f"case_{case_id}"
        text = f"症状：{case_text} 诊断：{diagnosis} 科室：{department}"
        meta = {
            "case_id": case_id,
            "diagnosis": diagnosis,
            "department": department,
            "severity": severity,
            "source": metadata.get("source", "AI生成") if metadata else "AI生成",
            "source_url": metadata.get("source_url", "") if metadata else ""
        }
        col.add(
            documents=[text],
            metadatas=[meta],
            ids=[doc_id]
        )
        return True
    except Exception as e:
        print(f"[向量] 添加病例失败: {e}")
        return False

def delete_case(case_id):
    """从向量库删除病例"""
    try:
        col = get_collection()
        col.delete(ids=[f"case_{case_id}"])
        return True
    except Exception:
        return False

def search_similar(query, limit=5):
    """语义搜索相似病例"""
    try:
        col = get_collection()
        total = col.count()
        if total == 0:
            return []
        results = col.query(
            query_texts=[query],
            n_results=min(limit, total),
            include=["documents", "metadatas", "distances"]
        )
        if not results["ids"][0]:
            return []
        cases = []
        for i in range(len(results["ids"][0])):
            doc = results["documents"][0][i]
            meta = results["metadatas"][0][i]
            dist = results["distances"][0][i]
            cases.append({
                "id": meta.get("case_id", 0),
                "symptoms": doc.split("诊断：")[0].replace("症状：", "") if "诊断：" in doc else doc[:100],
                "diagnosis": meta.get("diagnosis", ""),
                "department": meta.get("department", ""),
                "severity": meta.get("severity", "green"),
                "similarity": round(1 - dist, 4) if dist else 0,
                "source": meta.get("source", ""),
                "source_url": meta.get("source_url", "")
            })
        return cases
    except Exception as e:
        print(f"[向量] 搜索失败: {e}")
        return []

def count_cases():
    """获取向量库中的病例总数"""
    try:
        col = get_collection()
        return col.count()
    except Exception:
        return 0

def sync_from_mysql():
    """从MySQL同步所有病例到向量库"""
    try:
        import pymysql
        conn = pymysql.connect(
            host="localhost", port=3306, user="root",
            password="123456", database="患者病历库", charset="utf8mb4"
        )
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT id, case_text, diagnosis, department, severity, source, source_url FROM learned_cases ORDER BY id")
            rows = cur.fetchall()
        conn.close()

        added = 0
        for r in rows:
            try:
                ok = add_case(
                    case_id=r["id"],
                    case_text=r["case_text"] or "",
                    diagnosis=r["diagnosis"] or "",
                    department=r["department"] or "",
                    severity=r["severity"] or "green",
                    metadata={"source": r.get("source", ""), "source_url": r.get("source_url", "")}
                )
                if ok:
                    added += 1
            except Exception:
                continue
        return {"total": len(rows), "added": added, "vector_count": count_cases()}
    except Exception as e:
        return {"error": str(e)}

def clear_all():
    """清空向量库"""
    try:
        client = get_client()
        client.delete_collection(COLLECTION_NAME)
        global _collection
        _collection = None
        return True
    except Exception:
        return False
