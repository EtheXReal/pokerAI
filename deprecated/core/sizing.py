"""下注尺寸计算与注释工具。

提供离散动作到具体下注金额（或 raise-to）的换算逻辑，同时给出人类可读的注释标签。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from env.actions import ActionType, RAISE_SIZE_FACTORS

EPS = 1e-6


@dataclass
class ActionPlan:
    """描述一次动作的计算结果。"""

    legal: bool
    target_total: Optional[float] = None  # 执行后玩家 street_commit 总量
    added: float = 0.0  # 本次新增的筹码（call+raise）
    sizing_tag: Optional[str] = None
    reason: Optional[str] = None


def _derive_tag(pot_before: float, added: float) -> Optional[str]:
    if added <= EPS or pot_before <= EPS:
        return None
    ratio = added / pot_before
    if ratio <= 0.40:
        return "r33"
    if ratio <= 0.80:
        return "r50"
    if ratio <= 1.5:
        return "r100"
    if ratio <= 2.5:
        return "r200"
    return "r300"


def plan_action(
    action: ActionType,
    *,
    pot_before: float,
    to_call: float,
    street_commit: float,
    player_stack: float,
    min_bet: float,
    min_raise_to: float,
    max_raise_to: float,
    current_raise_to: float,
    last_raise_amount: float,
    big_blind: float,
) -> ActionPlan:
    """根据当前局面给出动作计划。"""

    total_cap = street_commit + player_stack
    available = max(0.0, player_stack)
    plan = ActionPlan(legal=False, target_total=None, added=0.0)

    if action == ActionType.FOLD:
        plan.legal = to_call > EPS
        return plan

    if action == ActionType.CALL:
        if to_call <= EPS:
            plan.legal = True
            plan.target_total = street_commit
            plan.added = 0.0
            return plan
        call_amount = min(to_call, available)
        plan.legal = call_amount + EPS >= to_call or available > EPS
        plan.target_total = street_commit + call_amount
        plan.added = call_amount
        return plan

    if action == ActionType.ALL_IN:
        if available <= EPS:
            return plan
        target_total = min(max_raise_to, total_cap)
        if target_total <= street_commit + EPS:
            return plan
        plan.legal = True
        plan.target_total = target_total
        plan.added = target_total - street_commit
        plan.sizing_tag = "allin"
        return plan

    if available <= EPS or max_raise_to <= street_commit + EPS:
        return plan

    desired_total = None

    if action == ActionType.RAISE_POT:
        if to_call <= EPS:
            desired_total = street_commit + max(min_bet, pot_before)
        else:
            desired_total = pot_before + 2 * to_call
    else:
        factor = RAISE_SIZE_FACTORS.get(action, 0.0)
        if to_call <= EPS:
            desired_total = street_commit + max(min_bet, pot_before * factor)
        else:
            desired_total = current_raise_to + max(last_raise_amount, pot_before * factor)

    if desired_total is None:
        return plan

    clipped = min(max(desired_total, min_raise_to), max_raise_to)
    if clipped <= street_commit + EPS:
        return plan

    added = clipped - street_commit
    if to_call > EPS and added <= to_call + EPS and clipped < max_raise_to - EPS:
        plan.reason = "raise_not_above_call"
        return plan

    if to_call > EPS and clipped + EPS < min_raise_to and clipped < max_raise_to - EPS:
        plan.reason = "below_min_raise"
        return plan

    plan.legal = True
    plan.target_total = clipped
    plan.added = added
    plan.sizing_tag = _derive_tag(pot_before, added)
    return plan

