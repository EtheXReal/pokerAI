"""固定策略走到摊牌的回放脚本。

运行示例：
    python scripts/walk_showdown.py --seed 13

策略：优先 `call`，若不可行则选择最小合法加注（r33 -> r66 -> r100），
再不行则执行 `allin`。脚本会确保整手牌推进至摊牌，并做基本断言。
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from env.actions import ACTION_TO_INDEX, ActionType
from env.engine import HeadsUpPokerEnv
from utils.hand_history import print_hand


RAISE_PRIORITY = [
    ActionType.RAISE_33,
    ActionType.RAISE_66,
    ActionType.RAISE_POT,
]


def select_action(legal_mask: list[bool]) -> int:
    """按既定优先级选择动作索引。"""

    if legal_mask[ACTION_TO_INDEX[ActionType.CALL]]:
        return ACTION_TO_INDEX[ActionType.CALL]

    for action in RAISE_PRIORITY:
        idx = ACTION_TO_INDEX[action]
        if legal_mask[idx]:
            return idx

    if legal_mask[ACTION_TO_INDEX[ActionType.ALL_IN]]:
        return ACTION_TO_INDEX[ActionType.ALL_IN]

    if legal_mask[ACTION_TO_INDEX[ActionType.FOLD]]:
        return ACTION_TO_INDEX[ActionType.FOLD]

    raise RuntimeError("No legal action available for predetermined strategy.")


def run_walk(seed: int, max_steps: int = 64) -> None:
    env = HeadsUpPokerEnv()
    state, legal = env.reset(seed=seed)
    steps = 0
    done = False

    while not done and steps < max_steps:
        action_idx = select_action(legal)
        state, legal, _, done, _ = env.step(action_idx)
        steps += 1

    assert done, "Hand did not terminate within max_steps."
    hand_record = env.get_hand_record()
    assert hand_record.get("showdown"), "Hand did not reach showdown."
    terminal = env.terminal_rewards or {}
    assert isinstance(terminal, dict) and len(terminal) == 2, "Invalid terminal rewards payload."
    total_reward = sum(terminal.values())
    assert abs(total_reward) <= 1e-6, f"Terminal rewards not balanced: {terminal}"

    print(print_hand(hand_record, reveal_all=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deterministic walk to showdown.")
    parser.add_argument("--seed", type=int, default=42, help="Shuffle seed passed to env.reset.")
    parser.add_argument("--max-steps", type=int, default=64, help="Safety upper bound on step count.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_walk(seed=args.seed, max_steps=args.max_steps)
