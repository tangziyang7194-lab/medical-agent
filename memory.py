"""
双层记忆系统
- 短期记忆：滑动窗口 + Token压缩（替代InMemorySaver）
- 长期记忆：命名空间隔离 + 单例模式（替代InMemoryStore）
无需 LangGraph / LangChain
"""

from typing import List, Dict, Optional
from datetime import datetime
from models import VisitRecord
from config import MEMORY
import threading


# ========== Token估算工具 ==========

def count_tokens(text: str) -> int:
    """粗略估算中英文混合文本的Token数"""
    if not text:
        return 0
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars * 1.5 + other_chars / 3.5)


# ========== 消息类型（替代LangChain的BaseMessage） ==========

class Message:
    """简单的消息类型替代 LangChain 的 BaseMessage"""
    ROLE_SYSTEM = "system"
    ROLE_HUMAN = "human"
    ROLE_AI = "ai"
    ROLE_TOOL = "tool"

    def __init__(self, role: str, content: str, tool_call_id: str = ""):
        self.role = role
        self.content = content
        self.tool_call_id = tool_call_id

    @property
    def token_count(self) -> int:
        return count_tokens(self.content)

    def __repr__(self) -> str:
        return f"[{self.role}] {self.content[:60]}..."

    @staticmethod
    def system(content: str) -> 'Message':
        return Message(Message.ROLE_SYSTEM, content)

    @staticmethod
    def human(content: str) -> 'Message':
        return Message(Message.ROLE_HUMAN, content)

    @staticmethod
    def ai(content: str) -> 'Message':
        return Message(Message.ROLE_AI, content)


# ========== 短期记忆管理器 ==========

class ShortTermMemoryManager:
    """
    短期记忆管理器 - 负责当前对话上下文的存储与修剪
    替代 LangGraph 的 InMemorySaver + Checkpointer
    """

    def __init__(self):
        # 线程消息存储: thread_id -> Message列表
        self._sessions: Dict[str, List[Message]] = {}
        self._lock = threading.Lock()

    def get_messages(self, thread_id: str) -> List[Message]:
        """获取某线程的消息列表"""
        with self._lock:
            return list(self._sessions.get(thread_id, []))

    def add_message(self, thread_id: str, message: Message):
        """添加消息并自动修剪"""
        with self._lock:
            if thread_id not in self._sessions:
                self._sessions[thread_id] = []
            self._sessions[thread_id].append(message)
        self.trim_messages(thread_id)

    def add_messages(self, thread_id: str, messages: List[Message]):
        """批量添加消息"""
        for msg in messages:
            self.add_message(thread_id, msg)

    def trim_messages(self, thread_id: str) -> List[Message]:
        """
        修剪消息 - 滑动窗口策略
        保留最新的消息，直到总Token数低于上限
        """
        with self._lock:
            messages = self._sessions.get(thread_id, [])
            if not messages:
                return []

            # 分离系统消息（必须保留）
            system_msg = None
            non_system = []
            for msg in messages:
                if msg.role == Message.ROLE_SYSTEM and system_msg is None:
                    system_msg = msg
                else:
                    non_system.append(msg)

            # 检查是否需要修剪
            total_tokens = sum(m.token_count for m in non_system)
            total_msgs = len(non_system)

            if total_tokens <= MEMORY.MAX_SHORT_TERM_TOKENS and total_msgs <= MEMORY.MAX_SHORT_TERM_MESSAGES:
                return messages

            # 滑动窗口：从尾部保留，确保从 human 开始、以 human/ai 结束
            trimmed = []
            for msg in reversed(non_system):
                trimmed.insert(0, msg)
                # 检查是否超出
                current_tokens = sum(m.token_count for m in trimmed)
                if current_tokens > MEMORY.MAX_SHORT_TERM_TOKENS * 0.9 or len(trimmed) > MEMORY.MAX_SHORT_TERM_MESSAGES * 0.9:
                    break

            # 确保从 human 消息开始
            while trimmed and trimmed[0].role not in (Message.ROLE_HUMAN, Message.ROLE_AI):
                trimmed.pop(0)
            if trimmed and trimmed[0].role == Message.ROLE_AI:
                trimmed.pop(0)

            # 组装最终消息
            result = [system_msg] + trimmed if system_msg else trimmed
            self._sessions[thread_id] = result
            return result

    def clear_session(self, thread_id: str):
        """清除会话"""
        with self._lock:
            self._sessions.pop(thread_id, None)


# ========== 长期记忆管理器（单例模式） ==========

_instance = None
_lock = threading.Lock()


class LongTermMemoryManager:
    """
    长期记忆管理器 - 管理患者历史就诊记录
    替代 LangChain 的 InMemoryStore
    使用单例模式确保所有Agent实例共享同一个管理器
    """

    def __init__(self):
        # 存储: (namespace, key) -> data
        self._store: Dict[tuple, dict] = {}
        # 患者索引: patient_id -> [visit_id列表]
        self._patient_index: Dict[str, List[str]] = {}
        # 患者基本信息: patient_id -> PatientInfo dict
        self._patient_info: Dict[str, dict] = {}

    def _get_namespace_key(self, namespace: str, patient_id: str) -> tuple:
        """获取命名空间键"""
        return (namespace, patient_id)

    def put(self, namespace: str, key: str, data: dict):
        """存储数据到命名空间"""
        self._store[(namespace, key)] = data

    def get(self, namespace: str, key: str) -> Optional[dict]:
        """从命名空间读取数据"""
        return self._store.get((namespace, key))

    def search(self, namespace: str, patient_id: str) -> List[dict]:
        """搜索某命名空间下某患者的所有记录"""
        prefix = (namespace, patient_id)
        results = []
        for (ns, key), data in self._store.items():
            if ns == namespace and key.startswith(f"visit_{patient_id}"):
                results.append(data)
        # 按日期排序（如果有visit_date字段）
        results.sort(key=lambda x: x.get("visit_date", ""), reverse=True)
        return results

    # ====== 患者信息管理 ======

    def register_patient(self, patient_id: str, surname: str, age: int,
                          gender: str, location: str = "") -> dict:
        """注册或更新患者基本信息"""
        info = {
            "patient_id": patient_id,
            "surname": surname,
            "age": age,
            "gender": gender,
            "location": location,
            "total_visits": self._patient_info.get(patient_id, {}).get("total_visits", 0),
            "known_conditions": self._patient_info.get(patient_id, {}).get("known_conditions", []),
        }
        self._patient_info[patient_id] = info
        return info

    def get_patient_info(self, patient_id: str) -> Optional[dict]:
        """获取患者基本信息"""
        return self._patient_info.get(patient_id)

    def update_conditions(self, patient_id: str, conditions: List[str]):
        """更新患者已知病史"""
        if patient_id in self._patient_info:
            existing = set(self._patient_info[patient_id].get("known_conditions", []))
            existing.update(conditions)
            self._patient_info[patient_id]["known_conditions"] = list(existing)

    # ====== 就诊记录管理 ======

    def save_visit(self, visit: VisitRecord) -> str:
        """保存就诊记录到长期记忆"""
        namespace = MEMORY.LONG_TERM_NAMESPACE
        key = f"visit_{visit.patient_id}_{visit.visit_id}"
        self.put(namespace, key, visit.to_dict())

        # 更新患者索引
        if visit.patient_id not in self._patient_index:
            self._patient_index[visit.patient_id] = []
        self._patient_index[visit.patient_id].append(key)

        # 更新就诊计数
        if visit.patient_id in self._patient_info:
            self._patient_info[visit.patient_id]["total_visits"] += 1

        return visit.visit_id

    def get_patient_visits(self, patient_id: str, limit: int = 5) -> List[dict]:
        """获取患者历史就诊记录"""
        namespace = MEMORY.LONG_TERM_NAMESPACE
        results = self.search(namespace, patient_id)
        return results[:limit]

    def get_patient_summary(self, patient_id: str) -> str:
        """生成患者摘要文本"""
        info = self._patient_info.get(patient_id)
        visits = self.get_patient_visits(patient_id)

        if not info:
            return f"患者 {patient_id} 无档案记录。"

        gender_symbol = info.get('gender', '')
        lines = [f"📋 {info['surname']}（{gender_symbol}）编号：{patient_id}"]
        lines.append(f"  年龄: {info['age']} | 性别: {info['gender']} | 所在地: {info['location']}")
        lines.append(f"  总就诊次数: {info.get('total_visits', 0)}")

        conditions = info.get("known_conditions", [])
        if conditions:
            lines.append(f"  已知病史: {'、'.join(conditions)}")
        else:
            lines.append(f"  已知病史: 无")

        if visits:
            lines.append(f"\n  最近 {len(visits)} 次就诊记录:")
            for i, v in enumerate(visits, 1):
                lines.append(f"    #{i} {v.get('visit_date','')} | 主诉: {v.get('chief_complaint','')} | 诊断: {v.get('diagnosis','待诊')}")

        return "\n".join(lines)


def get_memory_manager() -> LongTermMemoryManager:
    """
    获取单例长期记忆管理器实例
    替代模块级单例模式
    """
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = LongTermMemoryManager()
    return _instance
