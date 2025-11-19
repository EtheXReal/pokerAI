"""
AI决策溯源工具

追踪和记录AI决策的完整逻辑链条，包括：
- 每个模块调用的输入输出
- 每个决策步骤的推理逻辑
- 每个步骤的执行时间
- 完整的决策链条可视化
"""
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class TraceStep:
    """单个决策步骤"""
    step_num: int                     # 步骤编号
    step_name: str                    # 步骤名称
    module: str                       # 模块名称（文件路径）
    function: str                     # 函数名
    inputs: Dict[str, Any]            # 输入参数
    outputs: Dict[str, Any]           # 输出结果
    duration_ms: float                # 执行时间（毫秒）
    reasoning: Optional[str] = None   # 推理逻辑说明

    def format_short(self) -> str:
        """简短格式（一行）"""
        return f"[{self.step_num}] {self.step_name} ({self.duration_ms:.2f}ms)"

    def format_full(self, verbose: bool = True) -> str:
        """完整格式（多行）"""
        lines = []
        lines.append(f"\n  步骤 {self.step_num}: {self.step_name}")
        lines.append(f"    模块: {self.module}")
        lines.append(f"    函数: {self.function}()")
        lines.append(f"    耗时: {self.duration_ms:.2f}ms")

        if verbose and self.inputs:
            lines.append(f"    输入:")
            for k, v in self.inputs.items():
                # 截断过长的值
                v_str = str(v)
                if len(v_str) > 100:
                    v_str = v_str[:97] + "..."
                lines.append(f"      - {k}: {v_str}")

        if self.outputs:
            lines.append(f"    输出:")
            for k, v in self.outputs.items():
                if isinstance(v, dict):
                    lines.append(f"      - {k}:")
                    for sk, sv in v.items():
                        sv_str = str(sv)
                        if len(sv_str) > 80:
                            sv_str = sv_str[:77] + "..."
                        lines.append(f"          {sk}: {sv_str}")
                else:
                    v_str = str(v)
                    if len(v_str) > 100:
                        v_str = v_str[:97] + "..."
                    lines.append(f"      - {k}: {v_str}")

        if self.reasoning:
            lines.append(f"    💡 推理: {self.reasoning}")

        return "\n".join(lines)


@dataclass
class DecisionTraceLog:
    """完整决策追踪日志"""
    hand_num: int
    street: str
    position: str
    hero_hand: str
    board: str
    pot: float
    facing_bet: float
    hero_stack: float

    # 决策步骤链
    steps: List[TraceStep] = field(default_factory=list)

    # 最终决策
    final_action: str = ""
    final_amount: float = 0.0

    # 总时间
    total_duration_ms: float = 0.0

    def add_step(
        self,
        step_name: str,
        module: str,
        function: str,
        inputs: Dict[str, Any],
        outputs: Dict[str, Any],
        duration_ms: float,
        reasoning: Optional[str] = None
    ):
        """添加追踪步骤"""
        step = TraceStep(
            step_num=len(self.steps) + 1,
            step_name=step_name,
            module=module,
            function=function,
            inputs=inputs,
            outputs=outputs,
            duration_ms=duration_ms,
            reasoning=reasoning
        )
        self.steps.append(step)
        self.total_duration_ms += duration_ms

    def format_summary(self) -> str:
        """格式化摘要（简短）"""
        lines = []
        lines.append(f"🔍 Hand #{self.hand_num} - {self.street} - {self.position}")
        lines.append(f"  手牌: {self.hero_hand} | 公共牌: {self.board}")
        lines.append(f"  底池: {self.pot:.1f}BB | 面对: {self.facing_bet:.1f}BB | 筹码: {self.hero_stack:.1f}BB")
        lines.append(f"  决策: {self.final_action}" + (f" {self.final_amount:.1f}BB" if self.final_amount > 0 else ""))
        lines.append(f"  步骤: {len(self.steps)}步 | 耗时: {self.total_duration_ms:.1f}ms")
        return "\n".join(lines)

    def format_full(self, verbose: bool = True) -> str:
        """格式化完整输出"""
        lines = []
        lines.append("=" * 100)
        lines.append(f"🔍 AI决策溯源 - Hand #{self.hand_num} - {self.street}")
        lines.append("=" * 100)

        # 游戏状态
        lines.append(f"\n【游戏状态】")
        lines.append(f"  手牌: {self.hero_hand}")
        lines.append(f"  公共牌: {self.board}")
        lines.append(f"  位置: {self.position}")
        lines.append(f"  底池: {self.pot:.2f}BB")
        lines.append(f"  面对下注: {self.facing_bet:.2f}BB")
        lines.append(f"  筹码: {self.hero_stack:.2f}BB")

        # 决策链条
        lines.append(f"\n【决策链条】共 {len(self.steps)} 步")
        for step in self.steps:
            lines.append(step.format_full(verbose=verbose))

        # 最终决策
        lines.append(f"\n【最终决策】")
        lines.append(f"  动作: {self.final_action}")
        if self.final_amount > 0:
            lines.append(f"  金额: {self.final_amount:.2f}BB")
        lines.append(f"  总耗时: {self.total_duration_ms:.2f}ms")

        # 性能分析
        if len(self.steps) > 0:
            lines.append(f"\n【性能分析】")
            # 找出最慢的3个步骤
            sorted_steps = sorted(self.steps, key=lambda s: s.duration_ms, reverse=True)
            lines.append(f"  最慢步骤:")
            for i, step in enumerate(sorted_steps[:3], 1):
                pct = (step.duration_ms / self.total_duration_ms) * 100
                lines.append(f"    {i}. {step.step_name}: {step.duration_ms:.2f}ms ({pct:.1f}%)")

        lines.append("\n" + "=" * 100)
        return "\n".join(lines)


class DecisionTracer:
    """决策追踪器"""

    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self.current_log: Optional[DecisionTraceLog] = None
        self._step_start_time: float = 0

    def is_enabled(self) -> bool:
        """检查是否启用"""
        return self.enabled

    def start_trace(self, hand_num: int, game_state: Any) -> Optional[DecisionTraceLog]:
        """开始追踪一个决策"""
        if not self.enabled:
            return None

        self.current_log = DecisionTraceLog(
            hand_num=hand_num,
            street=game_state.street,
            position=game_state.position,
            hero_hand=str(game_state.hero_hand),
            board=str(game_state.board) if game_state.board else "None",
            pot=game_state.pot_size,
            facing_bet=game_state.facing_bet if hasattr(game_state, 'facing_bet') else 0.0,
            hero_stack=game_state.hero_stack
        )
        return self.current_log

    def step_begin(self):
        """开始一个步骤的计时"""
        if self.enabled:
            self._step_start_time = time.time()

    def step_end(
        self,
        step_name: str,
        module: str,
        function: str,
        inputs: Dict[str, Any],
        outputs: Dict[str, Any],
        reasoning: Optional[str] = None
    ):
        """结束一个步骤的计时并记录"""
        if not self.enabled or not self.current_log:
            return

        duration_ms = (time.time() - self._step_start_time) * 1000
        self.current_log.add_step(
            step_name=step_name,
            module=module,
            function=function,
            inputs=inputs,
            outputs=outputs,
            duration_ms=duration_ms,
            reasoning=reasoning
        )

    def trace_step(
        self,
        step_name: str,
        module: str,
        function: str,
        inputs: Dict[str, Any],
        outputs: Dict[str, Any],
        duration_ms: float,
        reasoning: Optional[str] = None
    ):
        """直接记录一个步骤（不使用step_begin/step_end）"""
        if not self.enabled or not self.current_log:
            return

        self.current_log.add_step(
            step_name=step_name,
            module=module,
            function=function,
            inputs=inputs,
            outputs=outputs,
            duration_ms=duration_ms,
            reasoning=reasoning
        )

    def finish_trace(self, action: str, amount: float):
        """完成追踪"""
        if not self.enabled or not self.current_log:
            return

        self.current_log.final_action = action
        self.current_log.final_amount = amount

    def get_log(self) -> Optional[DecisionTraceLog]:
        """获取当前日志"""
        return self.current_log

    def reset(self):
        """重置追踪器"""
        self.current_log = None
        self._step_start_time = 0
