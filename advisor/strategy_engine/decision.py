"""
决策输出数据结构 (Decision Output)

定义最终决策的输出格式，包括：
- 动作概率分布
- 推荐动作
- 下注尺寸选项
- 决策依据和解释
"""
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, Any


@dataclass
class DecisionOutput:
    """
    最终决策输出

    分层输出结构：
    1. 动作概率分布（用于混合策略）
    2. 推荐动作（单一建议）
    3. 动态尺寸支持
    4. 决策依据
    5. 置信度评分
    """

    # ===== 核心输出 =====

    action_distribution: Dict[str, float]
    """
    动作概率分布

    键格式：
    - 'fold': 弃牌
    - 'call': 跟注
    - 'check': 过牌
    - 'rX': raise to X% pot (例如: 'r33', 'r66', 'r100')
    - 'r{X}bb': raise to X big blinds (例如: 'r6bb', 'r12bb')

    值：概率 (0.0-1.0)，总和应为 1.0

    示例：
        {'fold': 0.05, 'call': 0.25, 'r66': 0.50, 'r100': 0.20}
    """

    recommended_action: str
    """
    推荐动作（概率最高的动作）

    示例：'r66', 'call', 'fold'
    """

    # ===== 尺寸详情 =====

    sizing_options: Optional[Dict[str, float]] = None
    """
    如果推荐动作是raise，提供各尺寸的概率分布

    示例：{'r33': 0.15, 'r50': 0.20, 'r66': 0.45, 'r100': 0.20}
    """

    optimal_sizing: Optional[float] = None
    """
    最优下注尺寸（实际BB数）

    示例：6.5 (表示6.5个大盲)
    """

    sizing_range: Optional[Tuple[float, float]] = None
    """
    推荐的尺寸范围 (min_bb, max_bb)

    示例：(4.5, 8.0) - 建议在4.5BB到8.0BB之间
    """

    # ===== 决策依据 =====

    reasoning: Dict[str, Any] = field(default_factory=dict)
    """
    决策依据详情

    建议包含：
    - 'equity': float - 当前equity
    - 'range_advantage': str - 'strong'/'medium'/'weak'
    - 'opponent_type': str - 对手类型
    - 'exploit_adjustment': str - 应用的exploit策略
    - 'board_texture': str - 'dry'/'medium'/'wet'
    - 'position': str - 'IP'(有位置)/'OOP'(无位置)
    - 'pot_odds': float - 底池赔率
    - 'spr': float - Stack-to-Pot Ratio
    - 'street': str - 'preflop'/'flop'/'turn'/'river'

    示例：
        {
            'equity': 0.62,
            'range_advantage': 'strong',
            'opponent_type': 'Fish',
            'exploit_adjustment': 'value_bet_large',
            'board_texture': 'dry',
            'position': 'IP',
            'pot_odds': 0.25,
            'spr': 8.5,
            'street': 'flop'
        }
    """

    confidence: float = 1.0
    """
    置信度评分 (0.0-1.0)

    影响因素：
    - 样本量（对手手数）
    - Equity计算准确度
    - 范围推断准确度
    - 情境复杂度

    < 0.5: 低置信度（建议谨慎）
    0.5-0.8: 中等置信度
    > 0.8: 高置信度
    """

    # ===== 可选输出 =====

    ev_delta: Optional[float] = None
    """
    推荐动作 vs 次优选择的EV差距（BB）

    > 1.0: 显著优势
    0.5-1.0: 中等优势
    < 0.5: 微小差距（接近无差别）
    """

    explanation: Optional[str] = None
    """
    自然语言解释（可选，Phase 3功能）

    示例：
        "你在翻牌圈拿顶对，有66%的equity。牌面干燥，
         你有位置优势。对手是Fish类型，建议大尺寸价值下注。"
    """

    alternative_actions: Optional[Dict[str, float]] = None
    """
    次优选择及其EV（相对于推荐动作）

    示例：
        {'call': -0.3, 'r100': -0.1}  # call差0.3BB, r100差0.1BB
    """

    # ===== 辅助方法 =====

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（用于JSON序列化）"""
        return {
            'action_distribution': self.action_distribution,
            'recommended_action': self.recommended_action,
            'sizing_options': self.sizing_options,
            'optimal_sizing': self.optimal_sizing,
            'sizing_range': self.sizing_range,
            'reasoning': self.reasoning,
            'confidence': self.confidence,
            'ev_delta': self.ev_delta,
            'explanation': self.explanation,
            'alternative_actions': self.alternative_actions,
        }

    def summary(self) -> str:
        """简洁的文本摘要"""
        lines = [
            f"推荐动作: {self.recommended_action}",
            f"置信度: {self.confidence:.1%}",
        ]

        if self.optimal_sizing:
            lines.append(f"最优尺寸: {self.optimal_sizing:.1f} BB")

        if self.ev_delta:
            lines.append(f"EV优势: {self.ev_delta:+.2f} BB")

        # 关键决策因素
        if 'equity' in self.reasoning:
            lines.append(f"Equity: {self.reasoning['equity']:.1%}")

        if 'opponent_type' in self.reasoning:
            lines.append(f"对手: {self.reasoning['opponent_type']}")

        if 'exploit_adjustment' in self.reasoning:
            lines.append(f"策略: {self.reasoning['exploit_adjustment']}")

        return '\n'.join(lines)

    def __str__(self) -> str:
        return self.summary()

    def __repr__(self) -> str:
        return (f"DecisionOutput(action={self.recommended_action}, "
                f"confidence={self.confidence:.2f})")


def create_simple_decision(action: str, reasoning: Dict[str, Any]) -> DecisionOutput:
    """
    创建简单的决策输出（100%概率单一动作）

    Args:
        action: 动作 ('fold', 'call', 'r66', etc.)
        reasoning: 决策依据

    Returns:
        DecisionOutput对象
    """
    return DecisionOutput(
        action_distribution={action: 1.0},
        recommended_action=action,
        reasoning=reasoning,
        confidence=1.0
    )


def merge_decisions(decisions: Dict[str, DecisionOutput],
                    weights: Dict[str, float]) -> DecisionOutput:
    """
    合并多个决策（例如：GTO + Exploit混合）

    Args:
        decisions: 决策字典 {'gto': DecisionOutput, 'exploit': DecisionOutput}
        weights: 权重字典 {'gto': 0.6, 'exploit': 0.4}

    Returns:
        混合后的DecisionOutput
    """
    # 合并action_distribution
    merged_dist: Dict[str, float] = {}

    for name, decision in decisions.items():
        weight = weights.get(name, 0.0)
        for action, prob in decision.action_distribution.items():
            merged_dist[action] = merged_dist.get(action, 0.0) + prob * weight

    # 归一化
    total = sum(merged_dist.values())
    if total > 0:
        merged_dist = {k: v / total for k, v in merged_dist.items()}

    # 找到推荐动作
    recommended = max(merged_dist, key=merged_dist.get)

    # 合并reasoning
    merged_reasoning = {}
    for decision in decisions.values():
        merged_reasoning.update(decision.reasoning)
    merged_reasoning['strategy_weights'] = weights

    # 计算平均置信度
    avg_confidence = sum(d.confidence * weights.get(name, 0.0)
                        for name, d in decisions.items())

    return DecisionOutput(
        action_distribution=merged_dist,
        recommended_action=recommended,
        reasoning=merged_reasoning,
        confidence=avg_confidence
    )
