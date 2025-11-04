"""随机自博弈 Smoke 测试。

运行示例：
    python scripts/smoke_env.py --seed 42

脚本会以随机策略打完 1 手牌，并打印每步街次、动作与底池。
用于快速验证 env/engine 的状态推进与结算是否正常。
"""

from __future__ import annotations

import argparse
import random
from typing import List

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from env.engine import HeadsUpPokerEnv
from utils.hand_history import print_hand


def run_smoke(seed: int, reveal_all: bool) -> None:
    rng = random.Random(seed)
    env = HeadsUpPokerEnv()
    state, legal = env.reset(seed=seed)

    done = False
    while not done:
        actions: List[int] = [idx for idx, flag in enumerate(legal) if flag]
        if not actions:
            raise RuntimeError("No legal actions available during smoke run.")
        action = rng.choice(actions)
        state, legal, _, done, _ = env.step(action)

    hand_record = env.get_hand_record()
    print(print_hand(hand_record, reveal_all=reveal_all))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Random smoke test for Heads-Up poker env.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility.")
    parser.add_argument("--reveal-all", action="store_true", help="Reveal所有玩家底牌。")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_smoke(seed=args.seed, reveal_all=args.reveal_all)
