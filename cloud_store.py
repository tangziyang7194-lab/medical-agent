"""
云端 JSON 文件版咨询记录存储
（PythonAnywhere 等无 MySQL 环境使用；本地仍走 mysql_store）
"""
import os
import json
import time
import threading
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DATA_FILE = os.path.join(DATA_DIR, "consultations.json")
_lock = threading.Lock()


def _ensure():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False)


def _load():
    _ensure()
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _next_id(records):
    ids = [r.get("id", 0) for r in records]
    return (max(ids) + 1) if ids else 1


def save_consultation(surname, gender, symptom, diagnosis, dept, report):
    """保存咨询记录到 JSON 文件，返回记录 id"""
    with _lock:
        records = _load()
        rid = _next_id(records)
        pid = f"W{int(time.time()) % 1000000000}"
        records.append({
            "id": rid,
            "patient_id": pid,
            "symptom_text": (symptom or "")[:100],
            "department": dept or "",
            "diagnosis": diagnosis or "",
            "report": report or "",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False)
        return rid


def get_consultations(limit=50):
    """获取咨询记录列表（最新在前）"""
    records = _load()
    records = list(reversed(records))
    return records[:limit]
