"""
统一配置管理模块 - 从.env文件加载所有配置
"""
import os
from pathlib import Path

# 项目根目录
ROOT_DIR = Path(__file__).parent.absolute()

def load_env():
    """加载.env文件（手动解析，不依赖第三方库）"""
    env_path = ROOT_DIR / ".env"
    if not env_path.exists():
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            # 只在环境变量未设置时使用.env的值
            if key not in os.environ:
                os.environ[key] = value

# 启动时自动加载
load_env()

# ========== 便捷访问 ==========
def get(key: str, default: str = "") -> str:
    return os.environ.get(key, default)

def get_int(key: str, default: int = 0) -> int:
    try:
        return int(os.environ.get(key, str(default)))
    except ValueError:
        return default

def get_bool(key: str, default: bool = False) -> bool:
    val = os.environ.get(key, "").lower()
    if val in ("true", "1", "yes"):
        return True
    if val in ("false", "0", "no"):
        return False
    return default

# ========== 数据库 ==========
DB_HOST = get("DB_HOST", "localhost")
DB_PORT = get_int("DB_PORT", 3306)
DB_USER = get("DB_USER", "root")
DB_PASSWORD = get("DB_PASSWORD", "123456")
DB_NAME = get("DB_NAME", "患者病历库")
MYSQL_URI = f"host={DB_HOST},port={DB_PORT},user={DB_USER},password={DB_PASSWORD},database={DB_NAME}"

def get_db_conn_kwargs():
    return {
        "host": DB_HOST, "port": DB_PORT,
        "user": DB_USER, "password": DB_PASSWORD,
        "database": DB_NAME, "charset": "utf8mb4"
    }

# ========== 大模型（阿里云通义千问，兼容层保留旧变量名） ==========
ZHIPUAI_API_KEY = get("DASHSCOPE_API_KEY", get("ZHIPUAI_API_KEY", ""))
ZHIPUAI_MODEL = get("QWEN_MODEL", get("ZHIPUAI_MODEL", "qwen-plus"))
ZHIPUAI_API_BASE = get("QWEN_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")

# ========== Flask ==========
FLASK_HOST = get("FLASK_HOST", "0.0.0.0")
FLASK_PORT = get_int("FLASK_PORT", 5000)
FLASK_DEBUG = get_bool("FLASK_DEBUG", True)

# ========== 向量库 ==========
VECTOR_DB_DIR = get("VECTOR_DB_DIR", ".vector_db")
VECTOR_COLLECTION = get("VECTOR_COLLECTION", "medical_cases")
VECTOR_EMBED_MODEL = get("VECTOR_EMBED_MODEL", "embedding-2")

# ========== 学习模块 ==========
LEARN_INTERVAL_DAYS = get_int("LEARN_INTERVAL_DAYS", 2)
LEARN_CASES_PER_RUN = get_int("LEARN_CASES_PER_RUN", 50)

# ========== 管理员 ==========
ADMIN_USERNAME = get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = get("ADMIN_PASSWORD", "admin123")
