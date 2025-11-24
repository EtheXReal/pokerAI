"""
Range-Aware Exploit Handlers

新一代handlers，根据equity bucket应用不同的行动频率。

与旧handlers的区别：
- 旧: 不管什么牌，统一调整频率（垃圾）
- 新: 根据牌力bucket，应用不同策略（正确）

Example:
    旧: "LOOSEN_DEFENSE → 所有牌call 60%"
    新: "Nutted hands call 90%, Strong hands call 60%, Medium hands fold 85%"
"""
from typing import Dict, Optional, Callable
from enum import Enum, auto

from .range_aware import (
    EquityBucket,
    ActionFrequencies,
    RangeAwareAdvice,
    DecisionContext,
)


# ============================================================================
# Range-Aware Action Types
# ============================================================================

class RangeAwareActionType(Enum):
    """
    范围感知的action types

    这些是新的action type，替代旧的频率调整类型
    """
    RANGE_AWARE_DEFENSE = auto()     # 范围感知防守
    RANGE_AWARE_AGGRESSION = auto()  # 范围感知攻击
    RANGE_AWARE_VALUE = auto()       # 范围感知价值下注
    RANGE_AWARE_BLUFF = auto()       # 范围感知诈唬


# ============================================================================
# Handler Functions
# ============================================================================

def handle_range_aware_defense(
    gto_actions: Dict[str, float],
    advice: RangeAwareAdvice,
    alpha: float,
    ctx: DecisionContext,
) -> Dict[str, float]:
    """
    范围感知防守

    根据当前牌力bucket，应用不同的防守频率

    Args:
        gto_actions: GTO baseline频率 {'fold': 0.4, 'call': 0.4, 'raise': 0.2}
        advice: RangeAwareAdvice with bucket_strategies
        alpha: blend权重 (0-1)
        ctx: DecisionContext with equity_bucket

    Returns:
        调整后的action频率

    Logic:
        1. 获取当前牌力bucket
        2. 查找该bucket的目标频率
        3. Alpha blending: GTO → Target
        4. 归一化确保sum=1.0

    Example:
        # GTO: fold=0.40, call=0.40, raise=0.20
        # Bucket: MEDIUM (边缘牌)
        # Target: fold=0.85, call=0.15, raise=0.0
        # Alpha: 1.0
        # Result: fold=0.85, call=0.15, raise=0.0 (高弃牌率)
    """
    # 1. 获取当前牌力bucket
    bucket = ctx.equity_bucket

    # 2. 获取该bucket的目标频率
    target_freqs = advice.get_target_freqs(bucket)
    if not target_freqs:
        # 如果没有定义该bucket的策略，使用GTO baseline
        return gto_actions

    # 3. Alpha blending: 对每个action进行插值
    adjusted = {}
    target_dict = target_freqs.to_dict()

    # 获取所有可能的actions（GTO + Target中的union）
    all_actions = set(gto_actions.keys()) | set(target_dict.keys())

    for action in all_actions:
        gto_freq = gto_actions.get(action, 0.0)
        target_freq = target_dict.get(action, 0.0)

        # 线性插值
        new_freq = gto_freq + alpha * (target_freq - gto_freq)
        adjusted[action] = max(0.0, new_freq)

    # 4. 归一化（确保sum=1.0）
    total = sum(adjusted.values())
    if total > 0.001:  # 避免除零
        adjusted = {k: v/total for k, v in adjusted.items()}
    else:
        # Fallback to GTO if something goes wrong
        return gto_actions

    # 5. 移除接近0的频率（清理）
    adjusted = {k: v for k, v in adjusted.items() if v > 0.01}

    return adjusted


def handle_range_aware_aggression(
    gto_actions: Dict[str, float],
    advice: RangeAwareAdvice,
    alpha: float,
    ctx: DecisionContext,
) -> Dict[str, float]:
    """
    范围感知攻击

    根据牌力bucket，应用不同的攻击策略

    Use cases:
    - Nutted hands: 可以slowplay (check > bet)
    - Strong hands: 正常value bet
    - Medium hands: 减少thin value
    - Weak/Air: 避免诈唬

    Example:
        # Against MANIAC (不弃牌)
        # Nutted: check 70%, bet 30% (trap)
        # Strong: bet 75%, check 25% (value)
        # Medium: bet 15%, check 85% (pot control)
        # Weak/Air: bet 0%, check 100% (no bluff)
    """
    bucket = ctx.equity_bucket
    target_freqs = advice.get_target_freqs(bucket)

    if not target_freqs:
        return gto_actions

    # Alpha blending (same logic as defense)
    adjusted = {}
    target_dict = target_freqs.to_dict()
    all_actions = set(gto_actions.keys()) | set(target_dict.keys())

    for action in all_actions:
        gto_freq = gto_actions.get(action, 0.0)
        target_freq = target_dict.get(action, 0.0)
        new_freq = gto_freq + alpha * (target_freq - gto_freq)
        adjusted[action] = max(0.0, new_freq)

    # 归一化
    total = sum(adjusted.values())
    if total > 0.001:
        adjusted = {k: v/total for k, v in adjusted.items()}
    else:
        return gto_actions

    # 清理
    adjusted = {k: v for k, v in adjusted.items() if v > 0.01}

    return adjusted


def handle_range_aware_value(
    gto_actions: Dict[str, float],
    advice: RangeAwareAdvice,
    alpha: float,
    ctx: DecisionContext,
) -> Dict[str, float]:
    """
    范围感知价值下注

    专门用于价值下注场景

    Logic:
    - Nutted/Strong: 高频率bet
    - Medium: 选择性bet
    - Weak/Air: 不bet
    """
    # 同样的实现逻辑
    return handle_range_aware_aggression(gto_actions, advice, alpha, ctx)


def handle_range_aware_bluff(
    gto_actions: Dict[str, float],
    advice: RangeAwareAdvice,
    alpha: float,
    ctx: DecisionContext,
) -> Dict[str, float]:
    """
    范围感知诈唬

    控制诈唬频率（通常对MANIAC/CALLING_STATION应该是0）

    Logic:
    - Strong/Medium draws: 可以semi-bluff
    - Weak/Air: 不诈唬（对不弃牌的对手）
    """
    return handle_range_aware_aggression(gto_actions, advice, alpha, ctx)


# ============================================================================
# Backward Compatibility Wrapper
# ============================================================================

def handle_legacy_advice_with_range_awareness(
    gto_actions: Dict[str, float],
    advice: any,  # 旧的StrategyAdvice或新的RangeAwareAdvice
    alpha: float,
    ctx: Optional[DecisionContext],
) -> Dict[str, float]:
    """
    兼容层：支持旧的StrategyAdvice和新的RangeAwareAdvice

    如果传入RangeAwareAdvice且有ctx，使用range-aware handler
    否则fallback到旧的频率调整逻辑
    """
    # 检查是否是RangeAwareAdvice
    if isinstance(advice, RangeAwareAdvice) and ctx is not None:
        # 使用range-aware handler
        if advice.action_type == "RANGE_AWARE_DEFENSE":
            return handle_range_aware_defense(gto_actions, advice, alpha, ctx)
        elif advice.action_type == "RANGE_AWARE_AGGRESSION":
            return handle_range_aware_aggression(gto_actions, advice, alpha, ctx)
        elif advice.action_type == "RANGE_AWARE_VALUE":
            return handle_range_aware_value(gto_actions, advice, alpha, ctx)
        elif advice.action_type == "RANGE_AWARE_BLUFF":
            return handle_range_aware_bluff(gto_actions, advice, alpha, ctx)

    # Fallback: 使用旧的频率调整逻辑
    # (需要导入旧的handlers)
    # 这里暂时返回GTO，实际应该调用旧handler
    return gto_actions


# ============================================================================
# Handler Registry
# ============================================================================

RANGE_AWARE_HANDLERS: Dict[str, Callable] = {
    "RANGE_AWARE_DEFENSE": handle_range_aware_defense,
    "RANGE_AWARE_AGGRESSION": handle_range_aware_aggression,
    "RANGE_AWARE_VALUE": handle_range_aware_value,
    "RANGE_AWARE_BLUFF": handle_range_aware_bluff,
}


def apply_range_aware_adjustment(
    gto_actions: Dict[str, float],
    advice: RangeAwareAdvice,
    alpha: float,
    ctx: DecisionContext,
) -> Dict[str, float]:
    """
    应用范围感知调整

    统一入口函数，根据advice.action_type选择对应的handler

    Args:
        gto_actions: GTO baseline
        advice: RangeAwareAdvice
        alpha: blend weight
        ctx: DecisionContext with equity bucket

    Returns:
        Adjusted action frequencies
    """
    handler = RANGE_AWARE_HANDLERS.get(advice.action_type)

    if not handler:
        # Unknown action type, fallback to GTO
        return gto_actions

    try:
        return handler(gto_actions, advice, alpha, ctx)
    except Exception as e:
        # 出错时fallback到GTO（安全第一）
        print(f"[WARNING] Range-aware handler failed: {e}, using GTO baseline")
        return gto_actions


# ============================================================================
# Utility Functions
# ============================================================================

def debug_print_adjustment(
    bucket: EquityBucket,
    gto_actions: Dict[str, float],
    adjusted_actions: Dict[str, float],
    advice_type: str,
):
    """
    Debug输出：显示调整前后的对比

    Example output:
        [RANGE_AWARE_DEFENSE] Bucket: MEDIUM
        GTO:      fold=0.40, call=0.40, raise=0.20
        Adjusted: fold=0.85, call=0.15, raise=0.00
        → Fold rate increased by +45%
    """
    def format_freqs(actions: Dict[str, float]) -> str:
        return ', '.join([f"{k}={v:.2f}" for k, v in sorted(actions.items())])

    print(f"[{advice_type}] Bucket: {bucket.value}")
    print(f"  GTO:      {format_freqs(gto_actions)}")
    print(f"  Adjusted: {format_freqs(adjusted_actions)}")

    # 计算主要变化
    gto_fold = gto_actions.get('fold', 0.0)
    adj_fold = adjusted_actions.get('fold', 0.0)
    if abs(adj_fold - gto_fold) > 0.05:
        delta = (adj_fold - gto_fold) * 100
        print(f"  → Fold rate changed by {delta:+.0f}%")


def validate_frequencies(actions: Dict[str, float]) -> bool:
    """
    验证频率分布是否合法

    Returns:
        True if valid (sum ≈ 1.0, all non-negative)
    """
    if not actions:
        return False

    total = sum(actions.values())
    if not (0.98 <= total <= 1.02):
        return False

    if any(v < -0.001 for v in actions.values()):
        return False

    return True
