"""env.evaluator 核心函数自测。

运行：
    python scripts/check_eval.py --seed 7
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path
import sys

from treys import Deck, Evaluator  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from env.evaluator import effective_hand_strength, evaluate_heads_up, hand_strength

rank_eval = Evaluator()


def run_checks(seed: int, fuzz: int) -> None:
    rng_hs = random.Random(seed)
    rng_ehs = random.Random(seed + 1)
    rng_99 = random.Random(seed + 2)

    hero_hand = ["As", "Ad"]
    board_flop = ["Kh", "7d", "2c"]
    hs_aa = hand_strength(hero_hand, board_flop, nsamples=800, rng=rng_hs)
    hs_99 = hand_strength(["9h", "9c"], board_flop, nsamples=800, rng=rng_99)
    assert hs_aa > hs_99, f"AA should dominate on K72r: {hs_aa:.3f} vs {hs_99:.3f}"

    ehs_aa = effective_hand_strength(hero_hand, board_flop, nsamples=800, rng=rng_ehs)
    hs_ehs = hand_strength(hero_hand, board_flop, nsamples=800 // 2, rng=random.Random(seed + 1))
    assert ehs_aa >= hs_ehs - 1e-6, "EHS should not be lower than the HS estimate using the same RNG."

    print("=== Flop Equity Check ===")
    print("Board:", board_flop)
    print("Hero:", hero_hand)
    print(f"HS(Hero AA) = {hs_aa:.3f}")
    print(f"HS(99)      = {hs_99:.3f}")
    print(f"EHS(Hero AA)= {ehs_aa:.3f}")
    print(f"HS (shared rng)= {hs_ehs:.3f}")

    river_board = ["Ah", "Ts", "3c", "9d", "2s"]
    result_split = evaluate_heads_up(river_board, ["As", "Kd"], ["Ac", "Kh"])
    assert result_split["split"], "Expected a split pot between AK combos."

    result_hero = evaluate_heads_up(river_board, ["As", "Kd"], ["Qc", "Qh"])
    assert result_hero["winners"] == [0], "Hero should win with top pair vs QQ."

    hero_score = result_hero["scores"][0]
    villain_score = result_hero["scores"][1]
    hero_rank = rank_eval.class_to_string(rank_eval.get_rank_class(hero_score))
    villain_rank = rank_eval.class_to_string(rank_eval.get_rank_class(villain_score))

    print("\n=== Showdown: Hero Wins ===")
    print("Board:", river_board)
    print("Hero:", ["As", "Kd"], "| Villain:", ["Qc", "Qh"])
    print(f"Hero hand: {hero_rank} (score={hero_score})")
    print(f"Villain hand: {villain_rank} (score={villain_score})")
    print(f"Winners: {result_hero['winners']}")
    print("Note: lower rank score = stronger hand (treys)")

    split_scores = result_split["scores"]
    split_hero_rank = rank_eval.class_to_string(rank_eval.get_rank_class(split_scores[0]))
    split_villain_rank = rank_eval.class_to_string(rank_eval.get_rank_class(split_scores[1]))

    print("\n=== Showdown: Split Pot ===")
    print("Board:", river_board)
    print("Hero:", ["As", "Kd"], "| Villain:", ["Ac", "Kh"])
    print(f"Hero hand: {split_hero_rank} (score={split_scores[0]})")
    print(f"Villain hand: {split_villain_rank} (score={split_scores[1]})")
    print(f"Winners: {result_split['winners']}")
    print("Note: lower rank score = stronger hand (treys)")
    print("\nAll evaluator checks passed.")

    if fuzz > 0:
        print(f"\n=== Fuzz Check ({fuzz} samples) ===")
        base_rng = random.Random(seed + 100)
        deck_template = Deck.GetFullDeck()  # type: ignore[attr-defined]
        for idx in range(fuzz):
            rng_local = random.Random(base_rng.random() * 1e6 + idx)
            deck_cards = list(deck_template)
            rng_local.shuffle(deck_cards)
            hero_cards = deck_cards[:2]
            villain_cards = deck_cards[2:4]
            board_size = rng_local.randint(0, 5)
            board_cards = deck_cards[4 : 4 + board_size]

            rng_hs = random.Random(seed + 1000 + idx)
            rng_ehs = random.Random(seed + 2000 + idx)
            hs_val = hand_strength(hero_cards, board_cards, nsamples=400, rng=rng_hs)
            ehs_val = effective_hand_strength(hero_cards, board_cards, nsamples=400, rng=rng_ehs)
            hs_shared = hand_strength(
                hero_cards, board_cards, nsamples=200, rng=random.Random(seed + 2000 + idx)
            )

            assert 0.0 <= hs_val <= 1.0, "HS out of range during fuzz."
            assert 0.0 <= ehs_val <= 1.0, "EHS out of range during fuzz."
            assert ehs_val + 1e-6 >= hs_shared, "EHS dropped below shared HS in fuzz."

            # Ensure evaluate_heads_up agrees with score ordering on a full board.
            full_board = list(board_cards)
            if len(full_board) < 5:
                needed = 5 - len(full_board)
                extra_cards = deck_cards[4 + board_size : 4 + board_size + needed]
                full_board.extend(extra_cards)
            showdown = evaluate_heads_up(full_board, hero_cards, villain_cards)
            scores = showdown["scores"]
            winners = showdown["winners"]
            if winners == [0]:
                assert scores[0] < scores[1], "Winner mismatch: hero should have lower score."
            elif winners == [1]:
                assert scores[1] < scores[0], "Winner mismatch: villain should have lower score."
            else:
                assert scores[0] == scores[1], "Split pot expected equal scores."

        print("Fuzz checks passed.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Quick checks for env.evaluator utilities.")
    parser.add_argument("--seed", type=int, default=42, help="Seed for stochastic HS estimates.")
    parser.add_argument("--fuzz", type=int, default=0, help="Number of random fuzz scenarios to validate.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_checks(seed=args.seed, fuzz=args.fuzz)
