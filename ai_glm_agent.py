"""
DeepSeek V4 智能医学知识体
替代静态 knowledge_base.py 的 AI 驱动版本
"""

import json
import os
import re
from openai import OpenAI

import os

# ========== DeepSeek AI (智谱) 配置 ==========
# 从环境变量读取 API Key（本地使用 .env，云端使用平台环境变量）
# DeepSeek 配置
# 确保 .env 已加载（从环境变量读取 Key）
try:
    from config_loader import load_env
    load_env()
except ImportError:
    pass

API_KEY = os.environ.get("DEEPSEEK_API_KEY") or ""
_MODEL = os.environ.get("DEEPSEEK_MODEL") or "deepseek-v4-flash"
_API_BASE = os.environ.get("DEEPSEEK_API_BASE") or "https://api.deepseek.com/v1"


_MODEL = "deepseek-v4-flash"  # DeepSeek Flash

_client = None


def get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=API_KEY, base_url=_API_BASE)
    return _client


# ====== 系统提示词 ======

SYSTEM_PROMPT = """你是一位经验丰富的三甲医院主治医师，精通全科医学。你的任务是根据患者描述的症状，提供专业、准确的医学分析。

请严格按照以下JSON格式回复，不要输出其他内容：

```json
{
  "analysis": {
    "main_symptom": "主要症状名称",
    "keywords": ["关键词1", "关键词2"],
    "severity": "green/yellow/red",
    "department": "建议科室",
    "triage": "二级医院/三级医院/急诊"
  },
  "questions": [
    "追问问题1，基于患者已描述的内容只问缺失的信息",
    "追问问题2"
  ],
  "diseases": [
    {"name": "疾病名1", "probability": 0-100的整数, "department": "科室"}
  ],
  "knowledge": {
    "possible_causes": ["可能原因1", "可能原因2"],
    "red_flags": ["危险信号"],
    "suggested_exams": ["建议检查1", "建议检查2"],
    "advice": "处理建议"
  }
}
```

规则：
1. severity: green=轻微可观察, yellow=需尽快就医, red=立即急诊
2. triage: 二级医院=常见病, 三级医院=需专科, 急诊=危急
3. questions: 基于患者已说的内容，只追问缺失的关键信息，最多问5个
4. diseases: 按概率从高到低排序，需列出匹配度≥20%的疾病
5. 所有分析和建议必须基于循证医学，不能夸大或误导
6. 患者可能是儿童、成人或老人，考虑年龄因素"""


def call_glm(system_prompt: str, user_message: str, temperature: float = 0.3) -> str:
    """调用通义千问 API（含案例库RAG增强）"""
    # 向量语义检索相似历史案例（RAG增强）
    similar_cases = []
    try:
        if len(user_message) > 10:
            from vector_store import search_similar
            similar_cases = search_similar(user_message[:200], limit=3)
    except Exception:
        pass

    # 如果有相似案例，加入system_prompt
    enhanced_prompt = system_prompt
    if similar_cases:
        case_refs = "\n\n【向量检索相似病例 - RAG增强】（仅供学习参考）:\n"
        for i, c in enumerate(similar_cases, 1):
            sim_pct = int(c.get("similarity", 0) * 100)
            case_refs += f"案例{i} [{c['department']}] (相似度{sim_pct}%): {c['symptoms'][:100]}... → 诊断: {c['diagnosis']}\n"
        enhanced_prompt = system_prompt + case_refs

    try:
        client = get_client()
        resp = client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": enhanced_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=temperature,
            max_tokens=2048,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return json.dumps({"error": str(e)})


def parse_json_from_response(text: str) -> dict:
    """从模型返回文本中提取JSON"""
    # 尝试直接解析
    text = text.strip()
    if text.startswith("```"):
        # 去掉 ```json ... ``` 包裹
        text = re.sub(r'^```\w*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试提取 {} 中的内容
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
        return {"error": "JSON解析失败", "raw": text[:500]}


# ====== 核心功能 ======

def ai_analyze_symptoms(symptom_text: str, patient_info: str = "") -> dict:
    """
    AI分析症状，返回结构化医学分析结果
    patient_info: "45岁男性，所在地北京市朝阳区"
    """
    user_prompt = f"""患者信息：{patient_info or '未知'}
症状描述：{symptom_text}

请分析患者的症状，给出专业的医学分析。"""
    raw = call_glm(SYSTEM_PROMPT, user_prompt)
    result = parse_json_from_response(raw)
    return result


def ai_get_dynamic_questions(symptom_text: str, existing_text: str = "",
                              gender: str = "", age: int = 0) -> list:
    """
    AI动态生成追问问题，基于患者已提供的信息只问缺失的
    """
    user_prompt = f"""患者信息：{'未知' if not age else f'{age}岁'} {'未知' if not gender else gender}
已描述的症状：{symptom_text}

患者已经说了上述内容。请分析哪些信息已经提供了，哪些还需要追问。
只追问最关键且缺失的信息，最多5个问题。"""
    raw = call_glm(SYSTEM_PROMPT, user_prompt)
    result = parse_json_from_response(raw)
    if "error" in result:
        return []
    return result.get("questions", [])


def ai_calculate_disease_probability(symptom_text: str) -> list:
    """
    AI计算各疾病概率，返回排序列表
    """
    user_prompt = f"""症状描述：{symptom_text}

请根据上述症状，分析可能的疾病，计算每种疾病的概率（0-100%）。
只列出概率≥20%的疾病，按概率从高到低排列。"""
    raw = call_glm(SYSTEM_PROMPT, user_prompt)
    result = parse_json_from_response(raw)
    if "error" in result:
        return []
    diseases = result.get("diseases", [])
    if not diseases and "analysis" in result:
        # 兼容老格式
        diseases = result.get("analysis", {}).get("diseases", [])
    return [(d["name"], d["probability"], d.get("department", ""))
            for d in diseases if "name" in d and "probability" in d]


def ai_get_knowledge(symptom_text: str) -> dict:
    """
    AI查询医学知识
    返回：{"possible_causes": [], "red_flags": [], "suggested_exams": [], "advice": ""}
    """
    user_prompt = f"""症状描述：{symptom_text}

请提供相关的医学知识，包括可能原因、危险信号、建议检查和处理建议。"""
    raw = call_glm(SYSTEM_PROMPT, user_prompt)
    result = parse_json_from_response(raw)
    if "error" in result:
        return {"possible_causes": [], "red_flags": [],
                "suggested_exams": [], "advice": str(result.get('raw', ''))}
    knowledge = result.get("knowledge", {})
    if not knowledge:
        # 兼容老格式
        knowledge = result.get("analysis", {}).get("knowledge", {})
    return {
        "possible_causes": knowledge.get("possible_causes", [])[:5],
        "red_flags": knowledge.get("red_flags", [])[:3],
        "suggested_exams": knowledge.get("suggested_exams", [])[:5],
        "advice": knowledge.get("advice", ""),
    }


def ai_match_department(symptom_text: str) -> str:
    """AI匹配科室"""
    result = ai_analyze_symptoms(symptom_text)
    if "error" in result:
        return "内科"
    analysis = result.get("analysis", {})
    dept = analysis.get("department", "内科")
    return dept


# ====== 保持与旧知识库兼容的接口 ======

# 缓存上次结果，避免重复调用
_cache = {"last_questions": [], "last_knowledge": {}, "last_probs": []}


def get_dynamic_questions(symptom_name: str, existing_text: str = "") -> list:
    """动态获取追问问题（兼容旧接口）"""
    questions = ai_get_dynamic_questions(symptom_name, existing_text)
    if questions:
        _cache["last_questions"] = questions
        return questions
    # fallback：静态数据
    from knowledge_base_static import get_dynamic_questions as static_q
    qs = static_q(symptom_name, existing_text)
    _cache["last_questions"] = qs
    return qs


def get_symptom_checklist(symptom_name: str) -> list:
    """获取检查清单（兼容旧接口）"""
    questions = get_dynamic_questions(symptom_name, "")
    if questions:
        return questions
    from knowledge_base_static import get_symptom_checklist as static_cl
    return static_cl(symptom_name)


def query_medical_knowledge(symptom_names: list) -> dict:
    """查询医学知识（兼容旧接口）"""
    text = "、".join(symptom_names)
    knowledge = ai_get_knowledge(text)
    if knowledge.get("possible_causes"):
        _cache["last_knowledge"] = knowledge
        return knowledge
    # fallback
    from knowledge_base_static import query_medical_knowledge as static_kb
    fallback = static_kb(symptom_names)
    _cache["last_knowledge"] = fallback
    return fallback


def calculate_disease_probability(symptom_text: str) -> list:
    """计算疾病概率（兼容旧接口）"""
    probs = ai_calculate_disease_probability(symptom_text)
    if probs:
        _cache["last_probs"] = probs
        return probs
    from knowledge_base_static import calculate_disease_probability as static_prob
    fallback = static_prob(symptom_text)
    _cache["last_probs"] = fallback
    return fallback
