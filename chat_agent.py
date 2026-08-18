"""
对话式AI导诊助手
实现真正的对话式问诊，而非表单式
"""

import json
import os
import re
from zhipuai import ZhipuAI

# ========== 质谱AI (智谱) 配置 ==========
# 从环境变量读取 API Key（本地使用 .env，云端使用平台环境变量）
API_KEY = os.environ.get("ZHIPUAI_API_KEY") or ""
_MODEL = os.environ.get("ZHIPUAI_MODEL") or "glm-4-plus"
_API_BASE = os.environ.get("ZHIPUAI_API_BASE") or "https://open.bigmodel.cn/api/paas/v4"


_MODEL = "glm-4-plus"

_client = None


def get_client():
    global _client
    if _client is None:
        _client = ZhipuAI(api_key=API_KEY, base_url=_API_BASE)
    return _client


CHAT_SYSTEM_PROMPT = """你是一位资深主治医师，正在通过在线问诊系统与患者对话。你的任务是模拟真实的医患对话。

对话规则：
1. 首先热情问候患者，询问主要症状
2. 根据患者回答，像真实医生一样自然地追问细节（每次只问1-2个问题）
3. 当患者说了什么，不要重复询问已提供的信息
4. 语气温和专业，用通俗语言解释医学概念
5. 当收集到足够信息时（关键症状+持续时间+严重程度+伴随症状），开始给出分析
6. 在给出的分析前加一句"根据您的描述，我初步分析如下："
7. 始终记住之前的对话内容

重要规则：
- 每次回复不要超过120字，要简洁自然
- 如果患者提到紧急症状（胸痛、呼吸困难、大出血、意识障碍等），立即建议急诊
- 当你认为收集到足够信息可以给出诊断建议时，在末尾添加标记：__READY_FOR_REPORT__
- 不要一次性问太多问题，每次1-2个
- 语气温和自然

你不需要输出JSON，用自然语言回复即可。"""


def chat(messages: list, temperature: float = 0.7) -> str:
    """对话式聊天"""
    try:
        client = get_client()
        system_msg = {"role": "system", "content": CHAT_SYSTEM_PROMPT}
        full_messages = [system_msg] + messages
        resp = client.chat.completions.create(
            model=_MODEL,
            messages=full_messages,
            temperature=temperature,
            max_tokens=1024,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"抱歉，我暂时遇到技术问题，请稍后再试。错误：{str(e)[:50]}"


def get_greeting() -> str:
    """获取问候语"""
    return "您好！我是AI导诊助手👨‍⚕️\n\n请告诉我您哪里不舒服？比如症状、持续多久了、程度如何。我会像医生一样为您分析，并给出就诊建议。"


def check_ready_for_report(response: str) -> bool:
    """检查AI是否准备好生成报告"""
    return "__READY_FOR_REPORT__" in response


def clean_response(response: str) -> str:
    """清理响应中的标记"""
    text = response.replace("__READY_FOR_REPORT__", "").strip()
    # 如果最后一句是"我来整理一下"或类似引导语，保留
    return text


def extract_symptoms_from_conversation(messages: list) -> str:
    """从对话历史中提取症状描述文本"""
    symptom_parts = []
    for msg in messages:
        if msg["role"] == "user":
            symptom_parts.append(msg["content"])
    return " ".join(symptom_parts[-5:])  # 最近5条


def generate_report_from_chat(messages: list, patient_info: dict = None) -> str:
    """从对话历史生成诊断报告"""
    symptom_text = extract_symptoms_from_conversation(messages)

    # 调用ai_analyze_symptoms获取结构化分析
    from ai_glm_agent import ai_analyze_symptoms
    info_str = ""
    if patient_info:
        info_str = f"{patient_info.get('age','')}岁{patient_info.get('gender','')}，所在地{patient_info.get('location','')}"
    result = ai_analyze_symptoms(symptom_text, info_str)

    # 构建报告文本
    analysis = result.get("analysis", {})
    diseases = result.get("diseases", [])
    knowledge = result.get("knowledge", {})

    lines = [
        "=" * 60,
        "  AI 医疗诊断报告",
        "=" * 60,
        f"  建议科室: {analysis.get('department', '内科')}",
        f"  严重度: {analysis.get('severity', 'green').upper()}",
        f"  分诊等级: {analysis.get('triage', '二级医院')}",
        "-" * 60,
        f"  主诉: {symptom_text[:100]}",
        f"  诊断结论: {analysis.get('diagnosis', '建议进一步检查') or '建议就诊' + analysis.get('department', '内科')}",
        "-" * 60,
    ]

    if diseases:
        lines.append("📊 疾病可能性评估（仅供参考）:")
        for d in diseases[:5]:
            bar = "█" * int(d.get("probability", 0) / 10) + "░" * (10 - int(d.get("probability", 0) / 10))
            lines.append(f"  {d.get('name', '未知')} {d.get('probability', 0)}% {bar}")

    if knowledge:
        lines.append("-" * 60)
        causes = knowledge.get("possible_causes", [])
        if causes:
            lines.append(f"  可能原因: {'、'.join(causes[:3])}")
        exams = knowledge.get("suggested_exams", [])
        if exams:
            lines.append(f"  建议检查: {'、'.join(exams[:3])}")
        advice = knowledge.get("advice", "")
        if advice:
            lines.append(f"  处理建议: {advice[:100]}")

    lines += [
        "-" * 60,
        "  本报告由AI智能体（GLM-4.5）自动生成，仅供参考。",
        "=" * 60,
    ]

    return "\n".join(lines)
