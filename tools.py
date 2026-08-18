"""
工具系统 - 智能体的"感官"与"手脚"
6类医疗工具，每个工具包含：名称、描述、参数定义、执行逻辑、错误处理
替代 LangChain 的 @tool 装饰器
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass, field
import traceback

from models import Symptom, VisitRecord, DiagnosisReport
from memory import get_memory_manager, LongTermMemoryManager
from knowledge_base import get_symptom_checklist, query_medical_knowledge as kb_query


# ========== 工具元数据 ==========

@dataclass
class ToolMeta:
    """工具元数据定义——供智能体知道何时调用此工具"""
    name: str
    description: str
    parameters: Dict[str, Dict[str, Any]] = field(default_factory=dict)


# ========== 工具基类 ==========

class MedicalTool:
    """所有医疗工具的基类"""
    name: str = ""
    description: str = ""
    parameters: Dict[str, Dict] = {}

    def get_tool_meta(self) -> ToolMeta:
        return ToolMeta(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )

    def get_tool_prompt(self) -> str:
        """生成给大模型看的工具说明"""
        params_desc = []
        for pname, pinfo in self.parameters.items():
            required = pinfo.get("required", False)
            desc = pinfo.get("description", "")
            params_desc.append(f"  - {pname} ({'必填' if required else '可选'}): {desc}")
        return f"""
工具名称: {self.name}
描述: {self.description}
参数:
{chr(10).join(params_desc) if params_desc else '  无'}
"""


# ========== 工具1: 患者摘要 ==========

class GetPatientSummary(MedicalTool):
    """获取患者基本统计信息"""
    name = "get_patient_summary"
    description = "获取患者基本信息和就诊统计（总就诊次数、已知病史等）"
    parameters = {
        "patient_id": {"type": "string", "description": "患者ID (如 P001, P002)", "required": True}
    }

    def execute(self, patient_id: str) -> str:
        try:
            mem = get_memory_manager()
            summary = mem.get_patient_summary(patient_id)
            if not summary:
                return f"患者 {patient_id} 暂无档案信息。"
            return summary
        except Exception as e:
            return f"[工具错误] 获取患者摘要失败: {str(e)}"


# ========== 工具2: 历史记录检索 ==========

class RetrievePatientHistory(MedicalTool):
    """检索患者的历史就诊记录"""
    name = "retrieve_patient_history"
    description = "检索患者的历史就诊记录，用于诊断参考。返回格式化的就诊历史文本。"
    parameters = {
        "patient_id": {"type": "string", "description": "患者ID (格式: P001, P002)", "required": True},
        "limit": {"type": "integer", "description": "返回最多的历史记录数，默认5条", "required": False},
    }

    def execute(self, patient_id: str, limit: int = 5) -> str:
        try:
            mem = get_memory_manager()
            visits = mem.get_patient_visits(patient_id, limit)

            if not visits:
                return f"患者 {patient_id} 暂无就诊历史记录。"

            lines = [f"📋 患者 {patient_id} 的就诊历史记录 (共 {len(visits)} 条):\n"]
            for i, v in enumerate(visits, 1):
                visit_date = v.get("visit_date", "未知")
                complaint = v.get("chief_complaint", "未记录")
                diagnosis = v.get("diagnosis", "待诊断")
                dept = v.get("department", "未记录")

                lines.append(f"  就诊 #{i}")
                lines.append(f"    📅 日期: {visit_date}")
                lines.append(f"    🗣️ 主诉: {complaint}")
                lines.append(f"    🏥 科室: {dept}")
                lines.append(f"    🩺 诊断: {diagnosis}")
                lines.append("")

            return "\n".join(lines)

        except Exception as e:
            return f"[工具错误] 检索患者历史失败: {str(e)}"


# ========== 工具3: 症状检查清单 ==========

class GetSymptomChecklist(MedicalTool):
    """获取系统化的症状检查清单"""
    name = "get_symptom_checklist"
    description = "获取针对特定症状的系统化检查清单，用于指导问诊。返回该症状需要详细了解的关键问题列表。"
    parameters = {
        "symptom_name": {"type": "string", "description": "症状名称 (如'头痛'、'咳嗽'、'腹痛')", "required": True},
    }

    def execute(self, symptom_name: str) -> str:
        try:
            checklist = get_symptom_checklist(symptom_name)
            result = f"📋 针对「{symptom_name}」的检查清单:\n\n"
            for i, item in enumerate(checklist, 1):
                result += f"  {i}. {item}\n"
            return result
        except Exception as e:
            return f"[工具错误] 获取症状检查清单失败: {str(e)}"


# ========== 工具4: 医学知识查询 ==========

class QueryMedicalKnowledge(MedicalTool):
    """查询与症状相关的医学知识"""
    name = "query_medical_knowledge"
    description = "查询与给定症状相关的医学知识，包括可能病因、危险信号和建议检查项目。"
    parameters = {
        "symptom_names": {"type": "list", "description": "症状名称列表，如 ['头痛', '发热']", "required": True},
    }

    def execute(self, symptom_names: List[str]) -> str:
        try:
            knowledge = kb_query(symptom_names)

            lines = [f"📚 医学知识查询结果:\n"]

            # 可能病因
            causes = knowledge.get("possible_causes", [])
            if causes:
                lines.append("  可能病因:")
                for c in causes:
                    lines.append(f"  • {c}")

            # 危险信号
            red_flags = knowledge.get("red_flags", [])
            if red_flags:
                lines.append(f"\n  ⚠️ 注意以下危险信号:")
                for flag, advice in red_flags:
                    lines.append(f"  • {flag}")
                    lines.append(f"    建议: {advice}")

            # 建议检查
            exams = knowledge.get("suggested_exams", [])
            if exams:
                lines.append(f"\n  🔬 建议检查项目:")
                for e in exams:
                    lines.append(f"  • {e}")

            return "\n".join(lines)

        except Exception as e:
            return f"[工具错误] 查询医学知识失败: {str(e)}"


# ========== 工具5: 生成诊断报告 ==========

class GenerateDiagnosisReport(MedicalTool):
    """生成结构化的诊断报告"""
    name = "generate_diagnosis_report"
    description = "基于收集的病史、症状和医学知识，生成结构化的诊断报告。"
    parameters = {
        "patient_id": {"type": "string", "description": "患者ID", "required": True},
        "patient_name": {"type": "string", "description": "患者姓氏", "required": True},
        "department": {"type": "string", "description": "建议科室", "required": True},
        "chief_complaint": {"type": "string", "description": "主诉", "required": True},
        "symptom_summary": {"type": "string", "description": "症状总结", "required": True},
        "diagnosis": {"type": "string", "description": "诊断结论", "required": True},
        "triage_level": {"type": "string", "description": "分诊级别: tertiary/secondary/community", "required": True},
        "severity_level": {"type": "string", "description": "严重度: red/yellow/green", "required": True},
        "recommendation": {"type": "string", "description": "处理建议", "required": True},
        "hospital_suggestion": {"type": "string", "description": "建议医院", "required": True},
        "doctor_suggestion": {"type": "string", "description": "建议专家", "required": False},
    }

    def execute(self, **kwargs) -> str:
        try:
            report = DiagnosisReport(
                patient_id=kwargs.get("patient_id", ""),
                patient_name=kwargs.get("patient_name", ""),
                visit_date=datetime.now().strftime("%Y-%m-%d %H:%M"),
                department=kwargs.get("department", ""),
                chief_complaint=kwargs.get("chief_complaint", ""),
                symptom_summary=kwargs.get("symptom_summary", ""),
                diagnosis=kwargs.get("diagnosis", ""),
                triage_level=kwargs.get("triage_level", "secondary"),
                severity_level=kwargs.get("severity_level", "green"),
                recommendation=kwargs.get("recommendation", ""),
                hospital_suggestion=kwargs.get("hospital_suggestion", ""),
                doctor_suggestion=kwargs.get("doctor_suggestion", ""),
            )

            # 保存到长期记忆
            mem = get_memory_manager()
            try:
                visit = VisitRecord(
                    patient_id=report.patient_id,
                    chief_complaint=report.chief_complaint,
                    diagnosis=report.diagnosis,
                    department=report.department,
                    triage_level=report.triage_level,
                )
                mem.save_visit(visit)
                if report.diagnosis:
                    mem.update_conditions(report.patient_id, [report.department])
            except Exception as e:
                pass  # 记忆保存失败不影响报告展示

            # 格式化输出
            level_icons = {"red": "🔴", "yellow": "🟡", "green": "🟢"}
            triage_names = {"tertiary": "三级甲等医院", "secondary": "二级医院", "community": "社区卫生中心"}
            sv_icon = level_icons.get(report.severity_level, "⚪")
            triage_name = triage_names.get(report.triage_level, "综合医院")

            lines = [
                "=" * 60,
                f"  🏥 诊断报告",
                "=" * 60,
                f"  📅 就诊日期: {report.visit_date}",
                f"  👤 患者: {report.patient_name}",
                f"  🏥 建议科室: {report.department}",
                f"  {sv_icon} 严重度: {report.severity_level.upper()}",
                f"  📊 分诊等级: {triage_name}",
                "",
                f"  📋 主诉: {report.chief_complaint}",
                f"  🔍 症状总结: {report.symptom_summary}",
                f"  🩺 诊断结论: {report.diagnosis}",
                "",
                "─" * 60,
                f"  💡 处理建议: {report.recommendation}",
                "",
                f"  🏪 建议就诊: {report.hospital_suggestion}",
                f"  🌟 建议专家: {report.doctor_suggestion}" if report.doctor_suggestion else "",
                "",
                f"  ⚕️ {report.disclaimer}",
                "=" * 60,
            ]
            return "\n".join(filter(None, lines))

        except Exception as e:
            return f"[工具错误] 生成诊断报告失败: {str(e)}\n{traceback.format_exc()}"


# ========== 工具6: 建议后续步骤 ==========

class SuggestNextSteps(MedicalTool):
    """根据诊断结果提供后续行动建议"""
    name = "suggest_next_steps"
    description = "根据诊断结论的紧迫程度，生成分级后续行动建议。"
    parameters = {
        "triage_level": {"type": "string", "description": "分诊级别: tertiary/secondary/community", "required": True},
        "severity_level": {"type": "string", "description": "严重度: red/yellow/green", "required": True},
        "department": {"type": "string", "description": "建议科室", "required": True},
        "location": {"type": "string", "description": "患者所在地", "required": True},
        "special_notes": {"type": "string", "description": "特殊情况说明", "required": False},
    }

    def execute(self, **kwargs) -> str:
        try:
            triage = kwargs.get("triage_level", "secondary")
            severity = kwargs.get("severity_level", "green")
            dept = kwargs.get("department", "内科")
            location = kwargs.get("location", "当地")
            notes = kwargs.get("special_notes", "")

            lines = [
                "=" * 60,
                "  📌 后续行动建议",
                "=" * 60,
            ]

            if triage == "tertiary" or severity == "red":
                lines.extend([
                    "  ⚠️ 紧急程度：高",
                    "",
                    "  🚑 建议立即采取以下行动:",
                    "    1. 如症状严重，请立即拨打120",
                    f"    2. 尽快前往{location}的三级甲等医院【{dept}】就诊",
                    "    3. 建议提前通过医院APP或电话预约挂号",
                    "    4. 就诊时请携带身份证和既往病历资料",
                    "",
                    "  ⚕️ 注意:",
                    "    • 不要自行驾车前往医院，建议由他人陪同",
                    "    • 不要随意服用止痛药或退烧药，以免掩盖病情",
                ])
                if notes:
                    lines.append(f"    • {notes}")

            elif triage == "tertiary" or severity == "yellow":
                lines.extend([
                    "  ⚡ 紧急程度：中等",
                    "",
                    "  📋 建议行动:",
                    f"    1. 建议前往{location}的三级甲等医院【{dept}】就诊",
                    "    2. 建议提前预约挂号，避免长时间等待",
                    "    3. 就诊前记录好症状变化情况",
                    "",
                    "  💊 注意事项:",
                    "    • 如症状突然加重，请立即就医",
                    "    • 就诊前保持正常饮食和休息",
                ])

            else:
                lines.extend([
                    "  ✅ 紧急程度：低",
                    "",
                    "  📋 建议行动:",
                    f"    1. 可前往{location}的二级医院【{dept}】或社区卫生中心就诊",
                    "    2. 如症状轻微，可先观察1-3天",
                    "    3. 必要时可在线问诊或去药店咨询",
                    "",
                    "  💊 居家护理建议:",
                    "    • 保持充足休息，多饮水",
                    "    • 注意症状变化，如加重及时就医",
                    "    • 避免自行服用处方药",
                ])

            lines.extend([
                "",
                "─" * 60,
                "  ⚕️ 本建议由AI导诊系统生成，仅供参考，不构成医疗诊断。",
                "  📞 如有紧急情况请立即拨打120。",
                "=" * 60,
            ])

            return "\n".join(lines)

        except Exception as e:
            return f"[工具错误] 生成后续建议失败: {str(e)}"


# ========== 工具注册表 ==========

def get_all_tools() -> List[MedicalTool]:
    """获取所有已注册的医疗工具"""
    return [
        GetPatientSummary(),
        RetrievePatientHistory(),
        GetSymptomChecklist(),
        QueryMedicalKnowledge(),
        GenerateDiagnosisReport(),
        SuggestNextSteps(),
    ]


def get_tool_by_name(name: str) -> Optional[MedicalTool]:
    """根据名称查找工具"""
    for tool in get_all_tools():
        if tool.name == name:
            return tool
    return None


def get_tools_prompt_for_step(step: int) -> str:
    """生成当前步骤允许的工具说明"""
    if step == 1:
        return GetPatientSummary().get_tool_prompt() + "\n" + RetrievePatientHistory().get_tool_prompt()
    elif step == 2:
        return GetSymptomChecklist().get_tool_prompt()
    elif step == 3:
        return QueryMedicalKnowledge().get_tool_prompt()
    elif step == 4:
        return GenerateDiagnosisReport().get_tool_prompt()
    elif step == 5:
        return SuggestNextSteps().get_tool_prompt()
    return ""
