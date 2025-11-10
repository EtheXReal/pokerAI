from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.sizing import plan_action
from env.actions import ACTION_TO_INDEX, ActionType
from env.engine import HeadsUpPokerEnv

EPS = 1e-6


def approx(value: float, target: float, eps: float = EPS) -> bool:
    return abs(value - target) <= eps


def test_open_r33(seed: int) -> None:
    env = HeadsUpPokerEnv()
    state, legal = env.reset(seed=seed)
    state, legal, _, _, _ = env.step(ACTION_TO_INDEX[ActionType.CALL])
    state, legal, _, _, _ = env.step(ACTION_TO_INDEX[ActionType.CALL])
    state, legal, _, _, _ = env.step(ACTION_TO_INDEX[ActionType.RAISE_33])
    action = env.get_hand_record()["actions"][-1]
    assert approx(action["amount"], 2.0), f"Expected 2.0, got {action['amount']}"
    assert action.get("sizing_tag") in {"r33", "r50"}, f"Unexpected sizing tag {action.get('sizing_tag')}"
    print("r33 open OK")


def test_r200_vs_bet(seed: int) -> None:
    env = HeadsUpPokerEnv()
    state, legal = env.reset(seed=seed + 1)
    state, legal, _, _, _ = env.step(ACTION_TO_INDEX[ActionType.CALL])
    state, legal, _, _, _ = env.step(ACTION_TO_INDEX[ActionType.CALL])
    state, legal, _, _, _ = env.step(ACTION_TO_INDEX[ActionType.RAISE_33])
    to_call = state["to_call"]
    pot_before = env.get_hand_record()["actions"][-1]["pot_after"]
    state, legal, _, _, _ = env.step(ACTION_TO_INDEX[ActionType.RAISE_POT])
    action = env.get_hand_record()["actions"][-1]
    expected_total = pot_before + 2 * to_call
    assert approx(action["total"], expected_total), f"Expected raise-to {expected_total}, got {action['total']}"
    assert action.get("sizing_tag") == "r200", f"Unexpected sizing tag {action.get('sizing_tag')}"
    print("r200 facing bet OK")


def test_r100_plan() -> None:
    plan = plan_action(
        ActionType.RAISE_POT,
        pot_before=6.0,
        to_call=2.0,
        street_commit=2.0,
        player_stack=100.0,
        min_bet=2.0,
        min_raise_to=4.0,
        max_raise_to=102.0,
        current_raise_to=4.0,
        last_raise_amount=2.0,
        big_blind=2.0,
    )
    assert plan.legal, "Plan should be legal"
    assert approx(plan.added, 8.0), f"Expected added 8.0, got {plan.added}"
    assert plan.sizing_tag == "r100", f"Unexpected sizing tag {plan.sizing_tag}"
    print("r100 sizing OK")


def test_r200_plan() -> None:
    plan = plan_action(
        ActionType.RAISE_POT,
        pot_before=4.0,
        to_call=4.0,
        street_commit=2.0,
        player_stack=100.0,
        min_bet=2.0,
        min_raise_to=4.0,
        max_raise_to=102.0,
        current_raise_to=6.0,
        last_raise_amount=2.0,
        big_blind=2.0,
    )
    assert plan.legal, "Plan should be legal"
    assert approx(plan.added, 10.0), f"Expected added 10.0, got {plan.added}"
    assert plan.sizing_tag == "r200", f"Unexpected sizing tag {plan.sizing_tag}"
    print("r200 sizing OK")


def test_manual_bet(seed: int) -> None:
    env = HeadsUpPokerEnv()
    env.reset(seed=seed)
    env.step_command("bet", 4.0)
    last_action = env.get_hand_record()["actions"][-1]
    assert last_action["type"] in {"bet_custom", "raise_custom"}, f"Unexpected action type {last_action['type']}"
    assert last_action["amount"] > 0.0
    print("manual bet OK")


def test_illegal_custom_raise(seed: int) -> None:
    env = HeadsUpPokerEnv()
    env.reset(seed=seed)
    try:
        env.step_command("bet", 0.5)
    except RuntimeError as exc:
        assert any(key in str(exc) for key in ("below_min_bet", "below_call")), f"Unexpected error: {exc}"
    else:
        raise AssertionError("Custom bet below big blind should fail")
    print("illegal custom bet rejected")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify sizing rules for discrete raises.")
    parser.add_argument("--seed", type=int, default=42, help="Base seed for deterministic scenarios.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    test_open_r33(args.seed)
    test_r200_vs_bet(args.seed)
    test_r100_plan()
    test_r200_plan()
    test_manual_bet(args.seed)
    test_illegal_custom_raise(args.seed)
    print("All sizing checks OK")


if __name__ == "__main__":
    main()
