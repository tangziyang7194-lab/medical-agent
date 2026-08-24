"""
对话式AI导诊助手
实现真正的对话式问诊，而非表单式
"""

import json
import os
import re

# 确保 .env 已加载（避免模块导入顺序导致 key 为空）
try:
    from config_loader import load_env
    load_env()
except ImportError:
    pass

from openai import OpenAI

# ========== DeepSeek AI 配置 ==========
API_KEY = os.environ.get("DEEPSEEK_API_KEY") or ""
_MODEL = os.environ.get("DEEPSEEK_MODEL") or "deepseek-v4-flash"
_API_BASE = os.environ.get("DEEPSEEK_API_BASE") or "https://api.deepseek.com/v1"

_client = None


def get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=API_KEY, base_url=_API_BASE)
    return _client


CHAT_SYSTEM_PROMPT = """你是一位资深主治医师，正在通过在线问诊系统与患者进行完整的线上问诊。你的目标是像真实医生一样，系统性地完成一次充分、细致的问诊，**不要急于下结论、不要过早结束问诊**。

问诊流程（请按顺序逐步采集信息，每一轮只问1-2个问题）：
第1轮：热情问候，询问主要症状是什么、从什么时候开始的（持续时间）
第2轮：追问严重程度（能否忍受、是否影响日常活动）、不适的性质（刺痛/胀痛/绞痛/隐痛等）
第3轮：追问伴随症状（发热、恶心、乏力、头晕等）与诱发因素（饮食、劳累、情绪、受凉等）
第4轮：追问既往病史、过敏史、近期用药情况
第5轮：根据前面回答补充问诊（作息习惯、家族史、女性月经情况等），并确认没有遗漏后再做分析

关键规则：
- **至少要完成4轮以上追问**，覆盖上述5个方面后再考虑给出分析；信息不足时继续追问，绝不提前收尾
- 每次回复只问1-2个问题，不要一次问太多
- 不要重复患者已提供的信息，基于已有内容只追问缺失的部分
- 语气温和专业，用通俗语言解释医学概念
- 每次回复不超过120字，要简洁自然
- 如果患者提到紧急症状（胸痛、呼吸困难、大出血、意识障碍等），立即建议急诊，不要继续常规问诊
- 当且仅当5个方面的关键信息都已收集到（或患者明确表示没有/不知道）时，才在回复末尾添加标记：__READY_FOR_REPORT__
- 给出分析前加一句"根据您的描述，我初步分析如下："

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
        "  本报告由AI智能体（DeepSeek）自动生成，仅供参考。",
        "=" * 60,
    ]

    return "\n".join(lines)
