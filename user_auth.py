"""
普通用户认证模块 - 账号+密码注册登录
"""
import json, hashlib, os, secrets
from pathlib import Path

USER_FILE = Path(__file__).parent / "users.json"

def _load_users():
    if not USER_FILE.exists():
        return {}
    with open(USER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_users(users):
    with open(USER_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    return hashlib.sha256((password + salt).encode()).hexdigest(), salt

def register_user(username, password):
    """注册普通用户"""
    username = username.strip().lower()
    if not username or len(username) < 2:
        return {"success": False, "error": "用户名至少2个字符"}
    if len(password) < 4:
        return {"success": False, "error": "密码至少4个字符"}
    users = _load_users()
    if username in users:
        return {"success": False, "error": "用户名已存在"}
    # 检查是否与管理员同名
    from admin_auth import _load_users as _load_admin_users
    admins = _load_admin_users()
    if any(u.get("username") == username for u in admins):
        return {"success": False, "error": "该用户名为管理员账号，无法注册"}
    pw_hash, salt = hash_password(password)
    users[username] = {"password": pw_hash, "salt": salt, "role": "user", "created": str(Path(__file__).stat().st_mtime)}
    _save_users(users)
    return {"success": True}

def verify_user(username, password):
    """验证用户登录"""
    username = username.strip().lower()
    # 检查是否与管理员用户名冲突
    from admin_auth import _load_users as _load_admin_users
    admins = _load_admin_users()
    if any(u.get("username") == username for u in admins):
        return False  # 管理员用户名不允许从用户端登录

    users = _load_users()
    user = users.get(username)
    if not user:
        return False
    pw_hash, _ = hash_password(password, user["salt"])
    return pw_hash == user["password"]


def reset_user_password(username, new_password):
    """重置用户密码（忘记密码找回，无需认证）"""
    username = username.strip().lower()
    if not username:
        return {"success": False, "error": "请输入用户名"}
    if len(new_password) < 4:
        return {"success": False, "error": "密码至少4个字符"}
    users = _load_users()
    if username not in users:
        return {"success": False, "error": "用户不存在，请检查用户名"}
    pw_hash, salt = hash_password(new_password)
    users[username]["password"] = pw_hash
    users[username]["salt"] = salt
    _save_users(users)
    return {"success": True, "message": "密码已重置，请用新密码登录"}
