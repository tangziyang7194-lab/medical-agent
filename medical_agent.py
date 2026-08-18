#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三甲医院智能导诊系统 v3.0
架构：双层记忆 + 5步状态机工作流 + 6类医疗工具
技术栈：纯 Python（无 LangGraph/LangChain 依赖）
"""

import re
import os
import json
import uuid
from typing import Optional, List

from models import Symptom, VisitRecord, PatientInfo, DiagnosisReport
from memory import (
    ShortTermMemoryManager, LongTermMemoryManager,
    get_memory_manager, Message, count_tokens
)
from workflow import WorkflowEngine, StepTracker, DynamicPromptBuilder
from tools import (
    get_all_tools, get_tool_by_name,
    GetPatientSummary, RetrievePatientHistory,
    GetSymptomChecklist, QueryMedicalKnowledge,
    GenerateDiagnosisReport, SuggestNextSteps,
)
from config import STEP_NAMES
from knowledge_base import DEPT_SYMPTOMS as KB_DEPT_MAP
from regions import get_provinces, get_cities, get_districts, is_municipality, format_location
from datetime import datetime
from email_pdf import validate_email, get_email_provider_name, generate_pdf, send_report_email


class MedicalConsultationAgent:
    """
    医疗问诊 Agent — 核心控制器
    协调记忆管理、工作流引擎、工具系统
    """

    def __init__(self, use_llm: bool = False):
        self.short_term_mem = ShortTermMemoryManager()
        self.long_term_mem = get_memory_manager()
        self.workflow = WorkflowEngine()
        self.use_llm = use_llm  # 是否使用LLM（默认用规则引擎）

        # 患者计数器（自动生成ID）
        self._patient_counter = 0

    def _generate_patient_id(self) -> str:
        """生成患者ID（持久化递增：001, 002, 003...）"""
        mem = self.long_term_mem
        counter = mem.get("system", "patient_counter")
        if counter is None:
            counter = {"value": 0}
        counter["value"] += 1
        mem.put("system", "patient_counter", counter)
        return f"{counter['value']:03d}"

    # ==================== 问诊流程 ====================

    def start_consultation(self, thread_id: str, patient: dict) -> str:
        """
        开始新的问诊会话
        STEP 1: 获取患者信息
        """
        # 注册患者
        patient_id = patient.get("patient_id", self._generate_patient_id())
        self.long_term_mem.register_patient(
            patient_id=patient_id,
            surname=patient["surname"],
            age=patient["age"],
            gender=patient["gender"],
            location=patient.get("location", ""),
        )

        # 重置工作流
        self.workflow.reset(thread_id)
        self.workflow.tracker.update_step_data(thread_id, patient_id=patient_id)

        # 构建上下文
        context = f"患者: {patient['surname']}{patient['gender']}, {patient['age']}岁"
        if patient.get("location"):
            context += f", 所在地: {patient['location']}"

        # 生成系统提示
        system_prompt = self.workflow.get_system_prompt(thread_id, context)

        # 保存到短期记忆
        self.short_term_mem.add_message(thread_id, Message.system(system_prompt))

        # 执行STEP 1: 获取患者摘要和历史
        tools_output = []
        t1 = GetPatientSummary()
        result1 = t1.execute(patient_id)
        tools_output.append(result1)

        t2 = RetrievePatientHistory()
        result2 = t2.execute(patient_id)
        tools_output.append(result2)

        # 保存工具结果
        for r in tools_output:
            self.short_term_mem.add_message(thread_id, Message("tool", r))

        # 推进到STEP 2
        self.workflow.tracker.advance_step(thread_id)
        self.workflow.tracker.update_step_data(thread_id,
                                               patient_context=context,
                                               patient_summary=result1,
                                               patient_history=result2)

        return f"""
✅ 已获取患者 {patient['surname']} 的信息。

{result1}

{result2}

📌 现在进入症状问诊阶段。请描述您的主要症状。
"""

    def process_symptom(self, thread_id: str, symptom_text: str) -> str:
        """
        处理症状描述
        STEP 2: 症状检查与问诊（逐题问答）
        """
        step = self.workflow.tracker.get_step(thread_id)
        step_data = self.workflow.tracker.get_step_data(thread_id)

        if step < 2:
            return "⚠️ 请先完成患者信息登记（调用 start_consultation）。"

        self.short_term_mem.add_message(thread_id, Message.human(symptom_text))
        keywords = self._extract_keywords(symptom_text)

        # ====== STEP 2: 症状检查与问诊 ======
        if step == 2:
            checklist_shown = step_data.get("checklist_shown", False)

            if not checklist_shown:
                # --- 第1次：展示检查清单，解析出逐题列表 ---
                main_symptom = keywords[0] if keywords else "症状"
                patient_id = step_data.get("patient_id", "")
                patient_info = self.long_term_mem.get_patient_info(patient_id)
                gender = patient_info.get("gender", "男") if patient_info else "男"

                t3 = GetSymptomChecklist()
                raw_checklist = t3.execute(main_symptom).split('\n')

                # 性别过滤
                filtered = [l for l in raw_checklist if not (gender != "女" and "女性患者" in l)]
                # 改用智能追问：根据已有描述只问缺失信息
                from knowledge_base import get_dynamic_questions
                questions = get_dynamic_questions(main_symptom, symptom_text)
                if not questions:
                    questions = [f"关于「{main_symptom}」还有其他需要补充的吗？"]

                self.short_term_mem.add_message(thread_id, Message("tool", '\n'.join(filtered)))
                self.workflow.tracker.update_step_data(thread_id,
                    keywords=keywords,
                    symptom_text=symptom_text,
                    main_symptom=main_symptom,
                    checklist_shown=True,
                    questions=questions or ["请描述您的主要症状"],
                    q_index=0,
                    q_answers=[],
                    gender=gender)

                if not questions:
                    questions = ["请描述您的主要症状"]

                return f"""
🔍 识别到症状关键词: {'、'.join(keywords) if keywords else '（暂无明确匹配）'}

📋 针对「{main_symptom}」请回答以下 {len(questions)} 个问题（逐题回答，全部答完方可进入下一步）：

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📌 第 1/{len(questions)} 问: {questions[0]}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

            else:
                # --- 第N次：接收一道题的回答，显示下一题或结束 ---
                questions = step_data.get("questions", [])
                q_index = step_data.get("q_index", 0)
                q_answers = step_data.get("q_answers", [])

                # 保存当前问题的回答
                q_answers.append(symptom_text)
                q_index += 1

                self.workflow.tracker.update_step_data(thread_id,
                    q_index=q_index,
                    q_answers=q_answers,
                    keywords=keywords or step_data.get("keywords", []),
                    symptom_details=' | '.join(q_answers))

                if q_index < len(questions):
                    return f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📌 第 {q_index+1}/{len(questions)} 问: {questions[q_index]}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
                else:
                    # 所有问题回答完毕！推进到STEP 3
                    self.workflow.tracker.advance_step(thread_id)
                    summary = '\n'.join(f"  Q{i+1}: {q}" for i, q in enumerate(questions))
                    answers = '\n'.join(f"  A{i+1}: {a}" for i, a in enumerate(q_answers))
                    return f"""
✅ 全部 {len(questions)} 个问题回答完毕！

📝 回答汇总:
{summary}
{answers}

正在为您查询相关医学知识...
"""

        # STEP 3: 医学知识查询
        elif step == 3:
            t4 = QueryMedicalKnowledge()
            knowledge = t4.execute(keywords if keywords else [symptom_text])

            self.short_term_mem.add_message(thread_id, Message("tool", knowledge))
            self.workflow.tracker.update_step_data(thread_id,
                                                   knowledge_result=knowledge)

            # 推进到STEP 4
            self.workflow.tracker.advance_step(thread_id)
            return f"""
{knowledge}

正在为您生成诊断报告...
"""

        elif step == 4:
            # 已经准备生成报告，但可能需要更多信息
            existing = step_data.get("keywords", [])
            all_keywords = list(set(existing + keywords))
            self.workflow.tracker.update_step_data(thread_id, keywords=all_keywords,
                                                   symptom_text=symptom_text)
            return "正在生成诊断报告，请稍候..."

        else:
            return "问诊已结束。如需重新开始，请使用新会话。"

    def generate_report(self, thread_id: str) -> str:
        """
        生成最终诊断报告
        STEP 4 → 综合所有信息生成报告
        """
        step = self.workflow.tracker.get_step(thread_id)
        if step < 4:
            return "⚠️ 请先完成症状问诊和医学知识查询。"

        step_data = self.workflow.tracker.get_step_data(thread_id)
        patient_id = step_data.get("patient_id", "P001")
        patient_context = step_data.get("patient_context", "")
        keywords = step_data.get("keywords", [])
        symptom_text = step_data.get("symptom_text", "")
        knowledge = step_data.get("knowledge_result", "")

        # 严重度评估
        severity = self._assess_severity(symptom_text, patient_context)

        # 科室匹配
        dept_matches = self._match_department(keywords)
        best_dept = dept_matches[0][0] if dept_matches else "内科"

        # 分诊级别
        triage = self._needs_tertiary(severity["level"], severity["score"])

        # 地名提取（从patient_context）
        location = "当地"
        loc_match = re.search(r'所在地:\s*([^,]+)', patient_context)
        if loc_match:
            location = loc_match.group(1).strip()

        # 医院建议
        if triage == "tertiary":
            hospital_suggestion = f"{location}的三级甲等医院【{best_dept}】"
            doctor_suggestion = self._get_doctor_suggestion(best_dept)
        elif triage == "secondary":
            hospital_suggestion = f"{location}的二级甲等医院【{best_dept}】"
            doctor_suggestion = "建议先挂普通门诊"
        else:
            hospital_suggestion = f"{location}的社区卫生服务中心"
            doctor_suggestion = "社区全科医生"

        # 构建诊断报告——格式：莫（男）编号：001
        step_data = self.workflow.tracker.get_step_data(thread_id)
        p_info = self.long_term_mem.get_patient_info(patient_id)
        if p_info:
            display_name = f"{p_info['surname']}（{p_info['gender']}）编号：{patient_id}"
        else:
            display_name = f"患者编号：{patient_id}"

        t5 = GenerateDiagnosisReport()
        report = t5.execute(
            patient_id=patient_id,
            patient_name=display_name,
            department=best_dept,
            chief_complaint=symptom_text[:100] if symptom_text else "未明确主诉",
            symptom_summary=f"主要症状: {'、'.join(keywords) if keywords else '待明确'}",
            diagnosis=self._build_diagnosis_text(keywords, knowledge, best_dept, symptom_text),
            triage_level=triage,
            severity_level=severity["level"],
            recommendation=self._build_recommendation(triage, severity, best_dept, location),
            hospital_suggestion=hospital_suggestion,
            doctor_suggestion=doctor_suggestion,
        )

        self.short_term_mem.add_message(thread_id, Message("tool", report))
        self.workflow.tracker.update_step_data(thread_id, diagnosis_report=report)

        # 推进到STEP 5
        self.workflow.tracker.advance_step(thread_id)

        return report

    def suggest_next_steps(self, thread_id: str) -> str:
        """
        建议后续步骤
        STEP 5: 最终建议
        """
        step = self.workflow.tracker.get_step(thread_id)
        if step < 5:
            return "⚠️ 请先生成诊断报告。"

        step_data = self.workflow.tracker.get_step_data(thread_id)
        patient_context = step_data.get("patient_context", "")
        keywords = step_data.get("keywords", [])
        symptom_text = step_data.get("symptom_text", "")

        severity = self._assess_severity(symptom_text, patient_context)
        dept_matches = self._match_department(keywords)
        best_dept = dept_matches[0][0] if dept_matches else "内科"
        triage = self._needs_tertiary(severity["level"], severity["score"])

        location = "当地"
        loc_match = re.search(r'所在地:\s*([^,]+)', patient_context)
        if loc_match:
            location = loc_match.group(1).strip()

        t6 = SuggestNextSteps()
        result = t6.execute(
            triage_level=triage,
            severity_level=severity["level"],
            department=best_dept,
            location=location,
            special_notes="",
        )

        self.short_term_mem.add_message(thread_id, Message("tool", result))

        return f"""
{result}

📌 感谢您的信任！如症状有任何变化，请及时就医。
"""

    # ==================== 完整问诊（一键） ====================

    def full_consultation(self, patient: dict, symptom_text: str) -> List[str]:
        """
        一键完成完整问诊流程
        返回各步骤的输出列表
        """
        thread_id = str(uuid.uuid4())[:8]
        outputs = []

        # STEP 1
        out1 = self.start_consultation(thread_id, patient)
        outputs.append(("📋 步骤1: 获取患者信息", out1))
        step = self.workflow.tracker.get_step(thread_id)

        # STEP 2 - 处理症状（两次调用：展示清单→患者填写→推进）
        out2a = self.process_symptom(thread_id, symptom_text)
        outputs.append(("🔍 步骤2: 症状检查清单", out2a))
        step = self.workflow.tracker.get_step(thread_id)

        # 第二次调用 + 循环：模拟患者逐一回答所有检查清单问题
        if step == 2 and self.workflow.tracker.get_step_data(thread_id).get("checklist_shown"):
            questions = self.workflow.tracker.get_step_data(thread_id).get("questions", [])
            # 模拟回答每一个问题
            for qi in range(len(questions)):
                q_answer = f"{symptom_text}，症状{qi+1}"
                out2b = self.process_symptom(thread_id, q_answer)
                step = self.workflow.tracker.get_step(thread_id)
                if step != 2:
                    break
            outputs.append((f"✏️ 步骤2(填写): {len(questions)}题已回答", out2b))

        # STEP 3 - 医学知识查询（如果需要）
        if step == 3:
            out3 = self.process_symptom(thread_id, symptom_text)
            outputs.append(("📚 步骤3: 医学知识查询", out3))
            step = self.workflow.tracker.get_step(thread_id)

        # STEP 4 - 诊断报告
        out4 = self.generate_report(thread_id)
        outputs.append(("🏥 步骤4: 诊断报告", out4))

        # STEP 5 - 后续建议
        out5 = self.suggest_next_steps(thread_id)
        outputs.append(("📌 步骤5: 后续建议", out5))

        return outputs

    # ==================== 内部方法 ====================

    def _extract_keywords(self, text: str) -> list:
        """提取症状关键词（jieba + 全文匹配）"""
        try:
            import jieba.posseg as pseg
            words = pseg.cut(text.lower().strip())
            tokens = [w.word for w in words]
        except ImportError:
            tokens = []

        # 知识库匹配
        found = set()
        for kw, dept in self._build_keyword_index().items():
            if kw in text:
                found.add(kw)
        for token in tokens:
            if token in self._build_keyword_index():
                found.add(token)

        return list(found)

    # 缓存关键词索引（避免每次重新构建）
    _keyword_cache = None

    def _build_keyword_index(self) -> dict:
        """建立关键词索引（带缓存）"""
        if self._keyword_cache is not None:
            return self._keyword_cache

        index = {}
        for dept, keywords in KB_DEPT_MAP.items():
            for kw in keywords:
                index[kw] = dept
        extra = {
            "发烧": "内科", "感冒": "内科", "肚子痛": "内科", "胃痛": "内科",
            "胃不舒服": "内科", "胃胀": "内科", "胀气": "内科", "反酸": "内科",
            "拉肚子": "内科", "咳嗽": "内科", "咳": "内科", "头痛": "内科",
            "头晕": "内科", "乏力": "内科", "胸闷": "内科", "恶心": "内科",
            "呕吐": "内科", "腹泻": "内科", "便秘": "内科", "食欲不振": "内科",
            "消化不良": "内科", "反复发作": "内科",
            "甲亢": "内科", "甲状腺": "内科", "心悸": "内科", "心慌": "内科",
            "多汗": "内科", "手抖": "内科", "消瘦": "内科", "突眼": "内科",
            "多食": "内科", "怕热": "内科", "失眠": "内科", "焦虑": "内科",
            "胸痛": "急诊科", "呼吸困难": "急诊科", "喘不上气": "急诊科",
            "出血": "急诊科", "昏迷": "急诊科", "晕倒": "急诊科",
            "便血": "肛肠科", "大便出血": "肛肠科", "痔疮": "肛肠科",
            "月经": "妇产科", "白带": "妇产科", "怀孕": "妇产科",
            "皮疹": "皮肤科", "皮肤痒": "皮肤科", "红疹": "皮肤科",
            "眼": "眼科", "牙": "口腔科", "牙龈": "口腔科",
            "耳": "耳鼻喉科", "鼻": "耳鼻喉科", "咽喉": "耳鼻喉科",
            "腰疼": "外科", "骨折": "外科", "肿块": "外科",
        }
        index.update(extra)
        type(self)._keyword_cache = index
        return index

    def _match_department(self, keywords: list) -> list:
        """将关键词映射到科室"""
        index = self._build_keyword_index()
        scores = {}
        for kw in keywords:
            dept = index.get(kw)
            if dept:
                scores[dept] = scores.get(dept, 0) + 1
        return sorted(scores.items(), key=lambda x: -x[1])

    def _assess_severity(self, text: str, context: str = "") -> dict:
        """评估病情严重度"""
        text_lower = text.lower()

        # 红色信号
        red_list = ["昏迷", "呼吸困难", "大出血", "剧烈胸痛", "高烧不退",
                     "抽搐", "严重过敏", "咳血", "窒息", "休克",
                     "意识不清", "剧烈头痛", "体重明显下降"]

        # 黄色信号
        yellow_list = ["反复发作", "长期", "慢性", "持续加重", "逐渐加重",
                        "便血", "发热", "咳嗽", "腹痛", "头晕",
                        "反复", "频繁", "久治不愈"]

        red_count = sum(1 for s in red_list if s in text_lower)
        yellow_count = sum(1 for s in yellow_list if s in text_lower)

        # 年龄检查
        age_match = re.search(r'(\d+)岁', context)
        age = int(age_match.group(1)) if age_match else 30

        # 婴幼儿规则
        has_child = any(k in text_lower for k in ["宝宝", "小儿", "幼儿", "婴儿", "孩子"])
        has_fever = any(k in text_lower for k in ["发热", "发烧", "高烧", "38度", "39度"])
        if (age <= 3 or has_child) and has_fever:
            yellow_count += 2

        # 高龄规则
        if age >= 65 and yellow_count >= 1:
            red_count += 1

        if red_count >= 1:
            level = "red"
        elif yellow_count >= 2:
            level = "yellow"
        else:
            level = "green"

        return {
            "level": level,
            "score": red_count * 3 + yellow_count,
            "red_signals": [s for s in red_list if s in text_lower],
            "yellow_signals": [s for s in yellow_list if s in text_lower],
        }

    def _needs_tertiary(self, level: str, score: int) -> str:
        """判断分诊级别"""
        if level == "red":
            return "tertiary"
        elif level == "yellow":
            return "tertiary"
        else:
            return "secondary"

    def _get_doctor_suggestion(self, dept: str) -> str:
        """获取专家建议"""
        experts = {
            "内科": "北京协和医院 张奉春主任医师",
            "外科": "北京协和医院 赵玉沛院士",
            "妇产科": "北京协和医院 郎景和院士",
            "儿科": "北京儿童医院 倪鑫主任医师",
            "急诊科": "北京协和医院 于学忠主任医师",
            "眼科": "北京同仁医院 王宁利主任医师",
            "耳鼻喉科": "北京同仁医院 韩德民院士",
            "皮肤科": "上海华山医院 徐金华主任医师",
            "口腔科": "北大口腔医院 俞光岩主任医师",
            "中医科": "广安门医院 仝小林院士",
            "肛肠科": "北京广安门医院 李华山主任医师",
            "康复科": "中国康复研究中心 李建军主任医师",
            "预防保健科": "北京协和医院 王仲主任医师",
        }
        return experts.get(dept, f"当地三甲医院{dept}专家")

    def _build_diagnosis_text(self, keywords: list, knowledge: str, dept: str,
                               symptom_text: str = "") -> str:
        """构建诊断结论文本（含疾病概率分析）"""
        kw_text = '、'.join(keywords) if keywords else '待明确'
        result = f"根据患者主诉({kw_text})，建议前往{dept}进一步检查以明确诊断。"

        # 添加疾病概率分析
        if symptom_text:
            try:
                from knowledge_base import calculate_disease_probability
                probs = calculate_disease_probability(symptom_text)
                if probs:
                    result += "\n\n📊 疾病可能性评估（仅供参考）:\n"
                    for i, (disease, prob, _) in enumerate(probs[:5], 1):
                        bar = "█" * int(prob / 10) + "░" * (10 - int(prob / 10))
                        result += f"\n  {i}. {disease} {prob}% {bar}"
            except Exception:
                pass

        return result

    def _build_recommendation(self, triage: str, severity: dict,
                               dept: str, location: str) -> str:
        """构建处理建议"""
        if triage == "tertiary" and severity["level"] == "red":
            return f"建议立即前往{location}三甲医院{dept}急诊就诊，必要时拨打120。"
        elif triage == "tertiary":
            return f"建议尽快预约{location}三甲医院{dept}门诊，完善相关检查。"
        else:
            return f"建议前往{location}二级医院{dept}就诊，如症状加重再转诊三甲医院。"


# ==================== 交互式启动 ====================

def interactive_mode():
    """交互式问诊入口 - 完整5步流程 + 邮箱发送PDF + 接诊循环"""
    agent = MedicalConsultationAgent()
    banner_shown = False

    while True:
        thread_id = str(uuid.uuid4())[:8]

        if not banner_shown:
            print("\n" + "█" * 60)
            print("""
    ╔═══════════════════════════════════╗
    ║  🏥  医疗问诊智能体 v3.0         ║
    ║  双层记忆 | 5步状态机 | 6类工具   ║
    ╚═══════════════════════════════════╝
            """)
            print("█" * 60)
            print("  📋 覆盖26个标准科室（14临床+12医技）")
            print("  🔄 5步问诊流程：信息→症状→知识→报告→建议")
            print("  📧 支持QQ/163/Gmail/Outlook等主流邮箱发送PDF报告")
            print("=" * 60)
            banner_shown = True

        # ====== 收集患者信息 ======
        print("\n" + "━" * 50)
        print("  📋 患者基本信息登记")
        print("━" * 50)

        surname = input("\n  ❶ 姓氏: ").strip()

        # 出生日期
        print("\n  ❷ 出生日期:")
        while True:
            try:
                y = int(input("     年 (如 1990): ").strip())
                m = int(input("     月 (1-12): ").strip())
                d = int(input("     日 (1-31): ").strip())
                if not (1900 <= y <= 2025) or not (1 <= m <= 12) or not (1 <= d <= 31):
                    print("     ⚠️ 日期超出合理范围，请重新输入")
                    continue
                dob = datetime(y, m, d)
                today = datetime.now()
                age = today.year - y - ((today.month, today.day) < (m, d))
                if age < 0 or age > 150:
                    print("     ⚠️ 计算年龄异常，请重新输入")
                    continue
                dob_raw = f"{y}年{m}月{d}日"
                break
            except ValueError:
                print("     ⚠️ 请输入数字")
        print(f"     ✅ 出生日期: {dob_raw}  →  年龄: {age}岁")

        # 性别
        print("\n  ❸ 性别:")
        while True:
            g = input("     请选择 (1=男, 2=女): ").strip()
            if g == "1": gender = "男"; break
            elif g == "2": gender = "女"; break
            print("     请输入 1 或 2")

        # 所在地 - 三级选择
        print("\n  ❹ 所在地:")
        provinces = get_provinces()
        print("\n     省/自治区/直辖市:")
        for i, p in enumerate(provinces, 1):
            print(f"      {i:2d}. {p:<10s}", end="")
            if i % 3 == 0: print()
        if len(provinces) % 3 != 0: print()
        while True:
            try:
                p_idx = int(input(f"\n     请选择编号 (1-{len(provinces)}): "))
                if 1 <= p_idx <= len(provinces): break
            except ValueError: pass
            print(f"     请输入 1-{len(provinces)} 之间的数字")
        province = provinces[p_idx - 1]

        cities = get_cities(province)
        selected_city = province if not cities else ""
        if cities:
            print(f"\n     {province} - 城市:")
            for i, c in enumerate(cities, 1):
                print(f"      {i:2d}. {c:<10s}", end="")
                if i % 4 == 0: print()
            if len(cities) % 4 != 0: print()
            while True:
                try:
                    c_idx = int(input(f"\n     请选择编号 (1-{len(cities)}): "))
                    if 1 <= c_idx <= len(cities): break
                except ValueError: pass
                print(f"     请输入 1-{len(cities)} 之间的数字")
            selected_city = cities[c_idx - 1]

        districts = get_districts(selected_city)
        selected_district = ""
        if districts:
            print(f"\n     {province}{selected_city} - 区/县:")
            for i, d in enumerate(districts, 1):
                print(f"      {i:2d}. {d}")
            while True:
                try:
                    d_idx = int(input(f"\n     请选择编号 (1-{len(districts)}): "))
                    if 1 <= d_idx <= len(districts): break
                except ValueError: pass
                print(f"     请输入 1-{len(districts)} 之间的数字")
            selected_district = districts[d_idx - 1]

        location = format_location(province, selected_city, selected_district)
        print(f"\n     ✅ 所在地: {location}")

        # 5. 邮箱输入
        print("\n  ❺ 接收报告的邮箱（支持QQ/163/Gmail/Outlook等主流邮箱）:")
        patient_email = ""
        while True:
            email_raw = input("     邮箱地址: ").strip()
            valid, msg = validate_email(email_raw)
            if valid:
                patient_email = email_raw
                provider = get_email_provider_name(email_raw)
                print(f"     ✅ {provider} 格式正确")
                break
            else:
                print(f"     ⚠️ {msg}")
                retry = input("     重新输入(1) 或 跳过(2): ").strip()
                if retry == "2":
                    break

        patient = {
            "surname": surname, "age": age, "gender": gender,
            "location": location, "birth_date": dob_raw,
        }

        # ====== 步骤1: 获取患者信息 ======
        print(f"\n{'='*60}")
        print("  [步骤 1/5] 获取患者信息")
        print(f"{'='*60}")
        out1 = agent.start_consultation(thread_id, patient)
        print(f"\n{out1}")
        step = agent.workflow.tracker.get_step(thread_id)
        print(f"  ✅ 当前进度: {agent.workflow.tracker.get_progress(thread_id)}")

        # ====== 步骤2: 逐题问答 ======
        print(f"\n{'='*60}")
        print("  [步骤 2/5] 症状检查与问诊")
        print(f"{'='*60}")
        print("\n请详细描述您的症状:")
        symptom = input("症状描述: ").strip()

        out2a = agent.process_symptom(thread_id, symptom)
        print(f"\n{out2a}")
        step = agent.workflow.tracker.get_step(thread_id)

        while step == 2 and agent.workflow.tracker.get_step_data(thread_id).get("checklist_shown"):
            answer = input("\n  您的回答: ").strip()
            out_next = agent.process_symptom(thread_id, answer)
            print(f"\n{out_next}")
            step = agent.workflow.tracker.get_step(thread_id)
        print(f"\n  📌 当前进度: {agent.workflow.tracker.get_progress(thread_id)}")

        # ====== 步骤3: 医学知识查询 ======
        if step == 3:
            print(f"\n{'='*60}")
            print("  [步骤 3/5] 医学知识查询")
            print(f"{'='*60}")
            out3 = agent.process_symptom(thread_id, symptom)
            print(f"\n{out3}")
            step = agent.workflow.tracker.get_step(thread_id)
            print(f"\n  📌 当前进度: {agent.workflow.tracker.get_progress(thread_id)}")

        # ====== 步骤4: 生成诊断报告 ======
        print(f"\n{'='*60}")
        print("  [步骤 4/5] 生成诊断报告")
        print(f"{'='*60}")
        out4 = agent.generate_report(thread_id)
        print(f"\n{out4}")

        # ====== 步骤5: 后续建议 ======
        print(f"\n{'='*60}")
        print("  [步骤 5/5] 后续行动建议")
        print(f"{'='*60}")
        out5 = agent.suggest_next_steps(thread_id)
        print(f"\n{out5}")
        print(f"\n{'='*60}")
        print("  ✅ 问诊流程全部完成！")
        print(f"  📌 最终进度: {agent.workflow.tracker.get_progress(thread_id)}")
        print(f"{'='*60}")

        # ====== 生成PDF & 发送邮箱 ======
        if patient_email:
            print("\n" + "━" * 50)
            print("  📧 正在生成PDF报告...")
            # 收集所有输出文本
            all_reports = f"{out4}\n\n{out5}"
            display_name = f"{surname}（{gender}）编号：{patient.get('patient_id', '')}"
            if not display_name.endswith('）'):
                display_name = f"{surname}（{gender}）编号：001"

            try:
                pdf_path = generate_pdf(all_reports, display_name)
                print(f"  ✅ PDF已生成: {pdf_path}")

                # 尝试发送邮件
                success, msg = send_report_email(patient_email, pdf_path)
                print(f"  {msg}")
            except Exception as e:
                print(f"  ⚠️ PDF生成失败: {str(e)}")

        # ====== 询问是否继续接诊 ======
        print("\n" + "━" * 50)
        choice = input("  🔄 是否继续为他人接诊？\n     1. 是（继续接诊）\n     2. 否（退出系统）\n\n     请选择 (1/2): ").strip()
        if choice != "1":
            print("\n  👋 感谢使用！祝您健康！\n")
            break
        print(f"\n{'='*60}")
        print("  开始为下一位患者接诊...")
        print(f"{'='*60}")


# ==================== 快速API模式 ====================

def quick_consult(surname: str, age: int, gender: str, location: str,
                  symptom_text: str, birth_date: str = "") -> dict:
    """快速问诊API"""
    agent = MedicalConsultationAgent()
    patient = {
        "surname": surname, "age": age, "gender": gender, "location": location,
        "birth_date": birth_date,
    }
    outputs = agent.full_consultation(patient, symptom_text)

    # 提取报告
    report_text = ""
    for title, content in outputs:
        if "诊断报告" in title:
            report_text = content
            break

    return {
        "steps": [{"title": t, "content": c} for t, c in outputs],
        "report": report_text,
    }


if __name__ == "__main__":
    interactive_mode()
