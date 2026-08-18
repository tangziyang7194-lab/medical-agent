"""
配置模块
集中管理所有配置参数
"""

# ========== 记忆系统配置 ==========

class MemoryConfig:
    """记忆系统参数配置"""
    # 短期记忆
    MAX_SHORT_TERM_MESSAGES: int = 20      # 最大消息条数
    MAX_SHORT_TERM_TOKENS: int = 4000      # 最大Token数
    TRIM_STRATEGY: str = "last"            # 修剪策略

    # 长期记忆
    LONG_TERM_NAMESPACE: str = "patients"  # 命名空间名称
    MAX_HISTORY_RECORDS: int = 10          # 最大历史记录数

    # Token估算
    CHARS_PER_TOKEN: float = 1.8           # 中文字符与Token的粗略比例


# ========== 问诊流程步骤配置 ==========

STEP_NAMES = {
    1: "获取患者信息",
    2: "症状检查与问诊",
    3: "医学知识查询",
    4: "生成诊断报告",
    5: "建议后续步骤",
}

STEP_INSTRUCTIONS = {
    1: """【当前任务 - 步骤1/5：获取患者信息】
执行内容：
1. 调用 get_patient_summary() 获取患者基本统计
2. 调用 retrieve_patient_history() 获取历史就诊记录
3. 向患者确认已获取信息，准备进入问诊

⚠️ 此阶段只允许使用上述两个工具，禁止调用其他工具""",

    2: """【当前任务 - 步骤2/5：症状检查与问诊】
执行内容：
1. 调用 get_symptom_checklist() 获取症状检查清单
2. 根据清单向患者提出最关键的问题
3. 收集完成后进入下一步

⚠️ 此阶段只允许使用 get_symptom_checklist 工具""",

    3: """【当前任务 - 步骤3/5：医学知识查询】
执行内容：
1. 调用 query_medical_knowledge() 查询相关医学知识
2. 综合症状信息与知识库进行推理
3. 告知患者分析结果

⚠️ 此阶段只允许使用 query_medical_knowledge 工具""",

    4: """【当前任务 - 步骤4/5：生成诊断报告】
执行内容：
1. 综合所有信息（病史、症状、医学知识）
2. 调用 generate_diagnosis_report() 生成结构化诊断报告
3. 向患者展示诊断结论

⚠️ 此阶段只允许使用 generate_diagnosis_report 工具""",

    5: """【当前任务 - 步骤5/5：建议后续步骤】
执行内容：
1. 调用 suggest_next_steps() 生成后续行动建议
2. 给出分级推荐（三甲/二级/社区）
3. 包含免责声明
4. 这是最终回答，完成后问诊结束

⚠️ 此阶段只允许使用 suggest_next_steps 工具""",
}


# ========== LLM 配置 ==========

class LLMConfig:
    """大模型连接配置"""
    # 使用DeepSeek兼容接口
    provider: str = "deepseek"              # deepseek / openai / ollama
    model: str = "deepseek-chat"           # deepseek-chat / deepseek-reasoner
    api_base: str = "https://api.deepseek.com/v1"
    api_key: str = ""                      # 从环境变量读取
    temperature: float = 0.3
    max_tokens: int = 2048


# ========== 常量 ==========

MEMORY = MemoryConfig()
LLM = LLMConfig()
