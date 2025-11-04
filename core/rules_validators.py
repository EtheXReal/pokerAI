"""环境动作前后规则校验。"""

from __future__ import annotations

from typing import Optional

from env.actions import ActionType

EPS = 1e-6


class RuleViolation(RuntimeError):
    """在调试阶段用于捕获规则违规。"""


def validate_pre_action(
    *,
    street: str,
    player_is_all_in: bool,
    action: ActionType,
    to_call: float,
) -> None:
    if street == "showdown":
        raise RuleViolation("Cannot act after showdown has been reached.")
    if player_is_all_in:
        raise RuleViolation("All-in player cannot take further actions.")
    if action == ActionType.FOLD and to_call <= EPS:
        raise RuleViolation("Folding without facing a bet is not permitted in this environment.")


def validate_post_action(
    *,
    action: ActionType,
    plan_target_total: Optional[float],
    plan_added: float,
    min_raise_to: float,
    max_raise_to: float,
    street_advanced: bool,
    pending_response: bool,
    to_call_after: float,
) -> None:
    if action in (ActionType.RAISE_33, ActionType.RAISE_66, ActionType.RAISE_POT) and plan_target_total is not None:
        if plan_target_total + EPS < min_raise_to and plan_target_total + EPS < max_raise_to:
            raise RuleViolation("Raise did not meet minimum raise-to requirement.")
        if plan_added <= EPS:
            raise RuleViolation("Raise action added no chips.")
    if street_advanced and pending_response:
        raise RuleViolation("Street advanced while responses were still pending.")
    if street_advanced and to_call_after > EPS:
        raise RuleViolation("Street advanced while there was still money to call.")
