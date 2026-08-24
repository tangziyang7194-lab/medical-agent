"""
管理员认证模块 - 支持注册、登录、短信验证
"""
import hashlib
import random
import re
import json
import time
import os
from datetime import datetime

# ========== 密码处理 ==========

def hash_password(password: str) -> str:
    """对密码进行哈希处理"""
    salt = "medical_agent_salt_2026"
    return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()

def verify_password(password: str, password_hash: str) -> bool:
    """验证密码"""
    return hash_password(password) == password_hash

# ========== 手机号验证 ==========

def validate_phone(phone: str) -> bool:
    """验证中国大陆手机号格式"""
    return bool(re.match(r"^1[3-9]\d{9}$", phone.strip()))

# ========== 短信验证码（内存存储，开发用）==========

_sms_codes = {}  # phone -> {code, expires_at, verified}

def generate_sms_code() -> str:
    """生成6位短信验证码"""
    return str(random.randint(100000, 999999))

def send_sms_code(phone: str) -> dict:
    """发送短信验证码
    
    开发阶段：直接返回验证码（不实际发送）
    生产环境：需对接短信服务商（如腾讯云、阿里云）
    """
    code = generate_sms_code()
    expires_at = time.time() + 300  # 5分钟有效
    
    _sms_codes[phone] = {
        "code": code,
        "expires_at": expires_at,
        "verified": False,
        "sent_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # 开发模式：返回验证码用于测试
    print(f"[SMS] 发送验证码 {code} 到手机 {phone}")
    return {
        "success": True,
        "message": f"验证码已发送到 {phone}",
        "dev_code": code  # 仅开发环境返回
    }

def verify_sms_code(phone: str, code: str) -> bool:
    """验证短信验证码"""
    record = _sms_codes.get(phone)
    if not record:
        return False
    if time.time() > record["expires_at"]:
        return False  # 已过期
    if record["code"] != code:
        return False
    # 标记已验证
    record["verified"] = True
    return True

def is_phone_verified(phone: str) -> bool:
    """检查手机号是否已验证"""
    record = _sms_codes.get(phone)
    return record and record.get("verified", False)

# ========== 管理员用户存储 ==========

# 使用JSON文件存储（轻量级，无需数据库表）
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".medical_agent_admin")
USERS_FILE = os.path.join(CONFIG_DIR, "admin_users.json")

def _ensure_config_dir():
    """确保配置目录存在"""
    os.makedirs(CONFIG_DIR, exist_ok=True)

def _load_users() -> list:
    """加载所有管理员用户"""
    _ensure_config_dir()
    if not os.path.exists(USERS_FILE):
        return []
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def _save_users(users: list):
    """保存管理员用户列表"""
    _ensure_config_dir()
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def register_admin(username: str, password: str, phone: str = "") -> dict:
    """注册管理员账号（手机号可选，与用户端注册方式一致）"""
    # 参数验证
    if not username or len(username) < 2:
        return {"success": False, "error": "用户名至少2个字符"}
    if not password or len(password) < 6:
        return {"success": False, "error": "密码至少6个字符"}
    if phone and not validate_phone(phone):
        return {"success": False, "error": "请输入有效的手机号"}
    if phone and not is_phone_verified(phone):
        return {"success": False, "error": "手机号未验证，请先获取验证码"}

    users = _load_users()
    
    # 检查用户名重复（管理员之间）
    for u in users:
        if u["username"] == username:
            return {"success": False, "error": "管理员用户名已存在"}
    # 检查是否与普通用户重名
    try:
        from user_auth import _load_users as _load_regular_users
        regular = _load_regular_users()
        if username in regular:
            return {"success": False, "error": "该用户名已被普通用户注册"}
    except:
        pass

    for u in users:
        if u["username"] == username:
            return {"success": False, "error": "用户名已存在"}
        if phone and u["phone"] == phone:
            return {"success": False, "error": "该手机号已注册"}
    
    # 创建用户
    new_user = {
        "id": len(users) + 1,
        "username": username,
        "password_hash": hash_password(password),
        "phone": phone,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "is_active": True,
        "role": "admin",
        "last_login": ""
    }
    users.append(new_user)
    _save_users(users)
    
    # 清除验证码记录
    _sms_codes.pop(phone, None)
    
    return {"success": True, "message": "注册成功"}


def reset_admin_password(username, new_password):
    """重置管理员密码（忘记密码找回，无需认证）"""
    username = username.strip()
    if not username:
        return {"success": False, "error": "请输入用户名"}
    if len(new_password) < 6:
        return {"success": False, "error": "密码至少6个字符"}
    users = _load_users()
    for u in users:
        if u.get("username") == username:
            u["password_hash"] = hash_password(new_password)
            _save_users(users)
            return {"success": True, "message": "密码已重置，请用新密码登录"}
    return {"success": False, "error": "管理员账号不存在，请检查用户名"}

def login_admin(username_or_phone: str, password: str = None, sms_code: str = None) -> dict:
    """管理员登录（支持密码登录或短信验证码登录）"""
    users = _load_users()
    
    for u in users:
        if u["username"] == username_or_phone or u["phone"] == username_or_phone:
            if password:
                # 密码登录
                if not verify_password(password, u["password_hash"]):
                    return {"success": False, "error": "密码错误"}
            elif sms_code:
                # 短信验证码登录
                if not verify_sms_code(u["phone"], sms_code):
                    return {"success": False, "error": "验证码错误或已过期"}
            else:
                return {"success": False, "error": "请输入密码或验证码"}
            
            if not u.get("is_active", True):
                return {"success": False, "error": "账号已被禁用"}
            
            # 更新最后登录时间
            u["last_login"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _save_users(users)
            
            return {
                "success": True,
                "user": {
                    "id": u["id"],
                    "username": u["username"],
                    "phone": u["phone"],
                    "role": u.get("role", "admin")
                }
            }
    
    return {"success": False, "error": "账号不存在"}

def get_admin_user(username: str = None, phone: str = None) -> dict:
    """获取管理员信息"""
    users = _load_users()
    for u in users:
        if username and u["username"] == username:
            return u
        if phone and u["phone"] == phone:
            return u
    return None

def has_admin_users() -> bool:
    """检查是否已有管理员用户"""
    return len(_load_users()) > 0

def get_all_admins() -> list:
    """获取所有管理员列表（不含密码哈希）"""
    users = _load_users()
    result = []
    for u in users:
        result.append({
            "id": u["id"],
            "username": u["username"],
            "phone": u["phone"],
            "role": u.get("role", "admin"),
            "created_at": u.get("created_at", ""),
            "last_login": u.get("last_login", ""),
            "is_active": u.get("is_active", True)
        })
    return result
