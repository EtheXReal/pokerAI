"""env.evaluator 核心函数自测。

运行：
    python scripts/check_eval.py --seed 7
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path
import sys

from treys import Evaluator  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from env.evaluator import effective_hand_strength, evaluate_heads_up, hand_strength

rank_eval = Evaluator()


def run_checks(seed: int) -> None:
    rng_hs = random.Random(seed)
    rng_ehs = random.Random(seed + 1)

    hero_hand = ["As", "Ad"]
    board_flop = ["Kh", "7d", "2c"]
    hs_aa = hand_strength(hero_hand, board_flop, nsamples=800, rng=rng_hs)
    hs_99 = hand_strength(["9h", "9c"], board_flop, nsamples=800, rng=random.Random(seed + 2))
    assert hs_aa > hs_99, f"AA should dominate on K72r: {hs_aa:.3f} vs {hs_99:.3f}"

    ehs_aa = effective_hand_strength(hero_hand, board_flop, nsamples=800)
    assert ehs_aa >= hs_aa - 1e-6, "EHS should not be lower than HS for the same combo."

    print("=== Flop Equity Check ===")
    print("Board:", board_flop)
    print("Hero:", hero_hand, "| Villain sample combo: ['Ad', 'Qd']")
    print(f"HS(Hero AA) = {hs_aa:.3f}")
    print(f"HS(99)      = {hs_99:.3f}")
    print(f"EHS(Hero AA)= {ehs_aa:.3f}")

    river_board = ["Ah", "Ts", "3c", "9d", "2s"]
    result_split = evaluate_heads_up(river_board, ["As", "Kd"], ["Ac", "Kh"])
    assert result_split["split"], "Expected a split pot between AK combos."

    result_hero = evaluate_heads_up(river_board, ["As", "Kd"], ["Qc", "Qh"])
    assert result_hero["winners"] == [0], "Hero should win with top pair vs QQ."

    hero_score = result_hero["scores"][0]
    villain_score = result_hero["scores"][1]
    hero_rank = rank_eval.class_to_string(rank_eval.get_rank_class(hero_score))
    villain_rank = rank_eval.class_to_string(rank_eval.get_rank_class(villain_score))

    print("\n=== Showdown Check ===")
    print("Board:", river_board)
    print("Hero:", ["As", "Kd"], "| Villain:", ["Qc", "Qh"])
    print(f"Hero hand: {hero_rank} (score={hero_score})")
    print(f"Villain hand: {villain_rank} (score={villain_score})")
    print(f"Winners: {result_hero['winners']}")
    print("Split check:", result_split)
    print("\nAll evaluator checks passed.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Quick checks for env.evaluator utilities.")
    parser.add_argument("--seed", type=int, default=42, help="Seed for stochastic HS estimates.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_checks(seed=args.seed)
