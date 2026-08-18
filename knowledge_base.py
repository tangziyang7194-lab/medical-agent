"""
医学知识库（AI 智能体版）
使用 GLM-4.5 驱动，静态数据作为备用
"""

import os
import sys

# 导入 AI 智能体（实时 API 调用）
from ai_glm_agent import (
    get_dynamic_questions,
    get_symptom_checklist,
    query_medical_knowledge,
    calculate_disease_probability,
)

# 导出静态版符号供旧代码调用
_static = __import__('knowledge_base_static', fromlist=[
    'DEPT_SYMPTOMS', 'SYMPTOM_CHECKLISTS', 'RED_FLAGS',
    'DISEASE_DB', 'analyze_existing_info', 'SYMPTOM_INFO_PATTERNS',
])
DEPT_SYMPTOMS = _static.DEPT_SYMPTOMS
SYMPTOM_CHECKLISTS = _static.SYMPTOM_CHECKLISTS
RED_FLAGS = _static.RED_FLAGS
DISEASE_DB = _static.DISEASE_DB
analyze_existing_info = _static.analyze_existing_info
SYMPTOM_INFO_PATTERNS = _static.SYMPTOM_INFO_PATTERNS
