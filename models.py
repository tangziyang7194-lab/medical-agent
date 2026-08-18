"""
数据模型模块
定义患者、症状、就诊记录等核心数据模型
使用 dataclass（替代 Pydantic，避免 LangChain 依赖）
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional
from datetime import datetime
import uuid


@dataclass
class Symptom:
    """症状模型 - 描述单个症状的详细信息"""
    name: str               # 症状名称
    duration: str = ""      # 持续时间
    severity: int = 5       # 严重程度 1-10
    description: str = ""   # 详细描述

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> 'Symptom':
        return Symptom(**data)


@dataclass
class VisitRecord:
    """就诊记录模型 - 完整记录一次问诊信息"""
    patient_id: str                 # 患者ID
    visit_id: str = ""              # 就诊ID
    visit_date: str = ""            # 就诊日期
    chief_complaint: str = ""       # 主诉
    symptoms: List[Symptom] = field(default_factory=list)   # 症状列表
    medical_history: List[str] = field(default_factory=list) # 病史
    diagnosis: str = ""             # 诊断结果
    treatment_plan: str = ""        # 治疗方案
    department: str = ""            # 建议科室
    triage_level: str = ""          # 分诊级别
    notes: str = ""                 # 备注

    def __post_init__(self):
        if not self.visit_id:
            self.visit_id = str(uuid.uuid4())[:8]
        if not self.visit_date:
            self.visit_date = datetime.now().strftime("%Y-%m-%d %H:%M")

    def to_dict(self) -> dict:
        return {
            "visit_id": self.visit_id,
            "patient_id": self.patient_id,
            "visit_date": self.visit_date,
            "chief_complaint": self.chief_complaint,
            "symptoms": [s.to_dict() for s in self.symptoms],
            "medical_history": self.medical_history,
            "diagnosis": self.diagnosis,
            "treatment_plan": self.treatment_plan,
            "department": self.department,
            "triage_level": self.triage_level,
            "notes": self.notes,
        }

    @staticmethod
    def from_dict(data: dict) -> 'VisitRecord':
        symptoms = [Symptom.from_dict(s) for s in data.get("symptoms", [])]
        return VisitRecord(
            patient_id=data.get("patient_id", ""),
            visit_id=data.get("visit_id", ""),
            visit_date=data.get("visit_date", ""),
            chief_complaint=data.get("chief_complaint", ""),
            symptoms=symptoms,
            medical_history=data.get("medical_history", []),
            diagnosis=data.get("diagnosis", ""),
            treatment_plan=data.get("treatment_plan", ""),
            department=data.get("department", ""),
            triage_level=data.get("triage_level", ""),
            notes=data.get("notes", ""),
        )


@dataclass
class PatientInfo:
    """患者基本信息"""
    patient_id: str
    surname: str
    age: int
    gender: str
    location: str = ""
    total_visits: int = 0
    known_conditions: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DiagnosisReport:
    """诊断报告 - 结构化的问诊结论"""
    patient_id: str
    patient_name: str
    visit_date: str
    department: str
    chief_complaint: str
    symptom_summary: str
    diagnosis: str
    triage_level: str            # tertiary / secondary / community
    severity_level: str          # red / yellow / green
    recommendation: str
    hospital_suggestion: str
    doctor_suggestion: str = ""
    disclaimer: str = "⚠️ 本报告由AI导诊系统生成，仅供参考，不构成医疗诊断。具体诊疗方案请咨询线下医生。"
