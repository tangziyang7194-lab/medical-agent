"""
状态机工作流
5步问诊流程 + 步骤追踪器 + 动态提示注入
替代 LangGraph 的 StateGraph
"""

from typing import Dict, Optional, List, Callable, Any
from config import STEP_NAMES, STEP_INSTRUCTIONS
from tools import get_tools_prompt_for_step, get_all_tools
from memory import Message


class StepTracker:
    """
    步骤追踪器 - 状态机核心
    管理每个对话线程的当前步骤，控制流程前进
    替代 LangGraph 的 StateGraph 节点管理
    """

    def __init__(self):
        # thread_id -> current_step (1-5)
        self._steps: Dict[str, int] = {}
        # thread_id -> step_data (当前步骤收集的数据)
        self._data: Dict[str, dict] = {}

    def get_step(self, thread_id: str) -> int:
        """获取当前步骤（默认从第1步开始）"""
        return self._steps.get(thread_id, 1)

    def advance_step(self, thread_id: str) -> int:
        """推进到下一步，最多到第5步"""
        current = self.get_step(thread_id)
        next_step = min(current + 1, 5)
        self._steps[thread_id] = next_step
        return next_step

    def set_step(self, thread_id: str, step: int):
        """手动设置步骤（用于恢复场景）"""
        self._steps[thread_id] = max(1, min(step, 5))

    def get_step_name(self, thread_id: str) -> str:
        """获取当前步骤名称"""
        step = self.get_step(thread_id)
        return STEP_NAMES.get(step, f"未知步骤({step})")

    def get_step_instruction(self, thread_id: str) -> str:
        """获取当前步骤指令"""
        step = self.get_step(thread_id)
        return STEP_INSTRUCTIONS.get(step, "")

    def get_tools_prompt(self, thread_id: str) -> str:
        """获取当前步骤允许的工具说明"""
        step = self.get_step(thread_id)
        return get_tools_prompt_for_step(step)

    def get_step_data(self, thread_id: str) -> dict:
        """获取当前步骤累计的数据"""
        if thread_id not in self._data:
            self._data[thread_id] = {}
        return self._data[thread_id]

    def update_step_data(self, thread_id: str, **kwargs):
        """更新当前步骤收集的数据"""
        if thread_id not in self._data:
            self._data[thread_id] = {}
        self._data[thread_id].update(kwargs)

    def reset(self, thread_id: str):
        """重置追踪器"""
        self._steps.pop(thread_id, None)
        self._data.pop(thread_id, None)

    def is_complete(self, thread_id: str) -> bool:
        """判断问诊是否完成"""
        return self.get_step(thread_id) >= 5

    def get_progress(self, thread_id: str) -> str:
        """获取进度显示"""
        step = self.get_step(thread_id)
        bar = "█" * step + "░" * (5 - step)
        return f"[{bar}] 步骤 {step}/5: {STEP_NAMES.get(step, '')}"


class DynamicPromptBuilder:
    """
    动态提示构建器
    根据当前步骤注入对应的系统提示 + 工具说明
    """

    BASE_SYSTEM_PROMPT = """你是 HermesMed，一名专业的AI医疗导诊系统。你的职责是：
1. 遵循严格的分步问诊流程，不跳步、不遗漏
2. 每次只使用当前步骤允许的工具
3. 用中文与患者交流，语气专业且温和
4. 收集必要的医疗信息，不做无依据的诊断
5. 在最终回答中包含免责声明

【核心原则】
- 禁止给出具体处方药剂量
- 必须包含"此建议仅供参考，请咨询线下医生"的免责声明
- 不应在缺乏充分依据的情况下给出确定性的诊断结论
- 尊重患者隐私，不询问无关的个人信息
"""

    MANDATORY_RULES = """
【安全护栏】
⚠️ 你必须始终遵守以下规则：
1. 禁止开具处方或建议具体药物剂量
2. 必须包含免责声明
3. 紧急情况必须建议拨打120
4. 不得做出确定性诊断（只能说"可能"、"建议考虑"）
5. 症状描述不够明确时，必须追问细节
6. 不能跳过任何步骤
"""

    @staticmethod
    def build(system_prompt: str, step_instruction: str, tools_prompt: str,
              patient_context: str = "") -> str:
        """构建完整的动态系统提示"""
        parts = [system_prompt]

        if patient_context:
            parts.append(f"\n【当前患者上下文】\n{patient_context}")

        parts.append(f"\n【当前进度】\n{step_instruction}")

        if tools_prompt:
            parts.append(f"\n【当前可用工具】\n{tools_prompt}")

        parts.append(DynamicPromptBuilder.MANDATORY_RULES)

        return "\n\n".join(parts)


class WorkflowEngine:
    """
    工作流引擎
    管理完整的5步问诊流程
    """

    def __init__(self):
        self.tracker = StepTracker()
        self.prompt_builder = DynamicPromptBuilder()

    def get_system_prompt(self, thread_id: str, patient_context: str = "") -> str:
        """获取当前步骤的完整系统提示"""
        step_instruction = self.tracker.get_step_instruction(thread_id)
        tools_prompt = self.tracker.get_tools_prompt(thread_id)

        return self.prompt_builder.build(
            system_prompt=self.prompt_builder.BASE_SYSTEM_PROMPT,
            step_instruction=step_instruction,
            tools_prompt=tools_prompt,
            patient_context=patient_context,
        )

    def handle_tool_call(self, thread_id: str, tool_name: str, params: dict) -> str:
        """处理工具调用（模拟LLM工具调用）"""
        from tools import get_tool_by_name

        tool = get_tool_by_name(tool_name)
        if not tool:
            return f"[错误] 未知工具: {tool_name}"

        # 检查当前步骤是否允许此工具
        current_step = self.tracker.get_step(thread_id)
        allowed_tools = get_tools_prompt_for_step(current_step)
        if tool_name not in allowed_tools:
            return f"[约束] 步骤{current_step}不允许调用 {tool_name}，请先完成当前步骤。"

        # 执行工具
        try:
            if tool_name in ("generate_diagnosis_report", "suggest_next_steps"):
                result = tool.execute(**params)
            else:
                result = tool.execute(**params)
            return result
        except Exception as e:
            import traceback
            return f"[工具执行错误] {tool_name}: {str(e)}\n{traceback.format_exc()}"

    def advance_if_needed(self, thread_id: str, step: int):
        """推进步骤（由外部根据条件调用）"""
        current = self.tracker.get_step(thread_id)
        if current == step:
            self.tracker.advance_step(thread_id)

    def reset(self, thread_id: str):
        """重置整个工作流"""
        self.tracker.reset(thread_id)
