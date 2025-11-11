#!/usr/bin/env python
"""
性能测试：超快速计算器 V2

快速测试关键优化效果
"""
import time
import sys
sys.path.append('/home/user/pokerAI')

from advisor.range_engine import Hand, Board, EquityCalculator
from advisor.range_engine.evaluator_fast_v2 import (
    UltraFastHandEvaluator,
    precompute_if_needed_v2
)
from advisor.range_engine.evaluator import HandEvaluator as OriginalEvaluator


def test_evaluator_speed():
    """测试评估器速度对比"""
    print("=" * 60)
    print("评估器速度测试（7张选5张）")
    print("=" * 60)

    # 准备测试数据
    hero_hand = Hand.from_str("AsKs")
    board = Board.from_str("Ah9c3dKd2h")
    cards = list(hero_hand.cards) + list(board.cards)

    iterations = 10000

    # 原始评估器
    print(f"\n原始评估器 ({iterations}次)...")
    start = time.time()
    for _ in range(iterations):
        strength = OriginalEvaluator.evaluate_best_5(cards)
    time_original = time.time() - start

    # 超快速评估器 V2
    print(f"超快速评估器 V2 ({iterations}次)...")
    start = time.time()
    for _ in range(iterations):
        strength = UltraFastHandEvaluator.evaluate_best_5(cards)
    time_fast = time.time() - start

    # 结果
    print(f"\n结果:")
    print(f"  原始评估器: {time_original:.3f} 秒 ({time_original/iterations*1000:.3f} ms/次)")
    print(f"  快速评估器: {time_fast:.3f} 秒 ({time_fast/iterations*1000:.3f} ms/次)")
    print(f"  加速比: {time_original/time_fast:.1f}x")


def test_equity_calculation():
    """测试Equity计算速度"""
    print("\n" + "=" * 60)
    print("Equity计算速度测试")
    print("=" * 60)

    from advisor.range_engine.calculator import EquityCalculator as OriginalCalc

    hero = Hand.from_str("AsKs")
    villain = Hand.from_str("QhQd")
    board = Board([])

    iterations = 1000

    # 原始计算器
    print(f"\n原始计算器 ({iterations}次迭代)...")
    calc_original = OriginalCalc(iterations=iterations)
    start = time.time()
    result_original = calc_original.calculate_equity(hero, villain, board)
    time_original = time.time() - start

    # 快速计算器（使用V2评估器）
    print(f"快速计算器 ({iterations}次迭代)...")
    # 创建一个使用V2评估器的简化计算器
    import random
    from advisor.range_engine import create_deck, validate_no_duplicates
    from advisor.range_engine.calculator import EquityResult

    start = time.time()
    # 简化实现：直接使用V2评估器
    deck = create_deck()
    used_cards = set(hero.cards) | set(villain.cards)
    available_cards = [c for c in deck if c not in used_cards]
    cards_needed = 5

    wins = 0
    ties = 0

    for _ in range(iterations):
        random_board = random.sample(available_cards, cards_needed)
        hero_cards = list(hero.cards) + random_board
        villain_cards = list(villain.cards) + random_board

        # 使用整数score比较（最快）
        hero_score = UltraFastHandEvaluator.evaluate_best_5_score(hero_cards)
        villain_score = UltraFastHandEvaluator.evaluate_best_5_score(villain_cards)

        if hero_score > villain_score:
            wins += 1
        elif hero_score == villain_score:
            ties += 1

    result_fast = EquityResult(
        win=wins / iterations,
        tie=ties / iterations,
        loss=(iterations - wins - ties) / iterations,
        iterations=iterations
    )
    time_fast = time.time() - start

    # 结果
    print(f"\n结果:")
    print(f"  原始计算器:")
    print(f"    Equity: {result_original.equity:.4f}")
    print(f"    耗时: {time_original*1000:.1f} ms")

    print(f"  快速计算器:")
    print(f"    Equity: {result_fast.equity:.4f}")
    print(f"    耗时: {time_fast*1000:.1f} ms")

    print(f"\n  加速比: {time_original/time_fast:.1f}x")
    print(f"  精度差异: {abs(result_original.equity - result_fast.equity)*100:.2f}%")


def run_quick_test():
    """运行快速测试"""
    print("=" * 60)
    print("超快速计算器 V2 - 性能测试")
    print("=" * 60)

    # 初始化查找表
    print("\n初始化查找表 V2...")
    precompute_if_needed_v2()

    # 测试评估器速度
    test_evaluator_speed()

    # 测试Equity计算
    test_equity_calculation()

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    run_quick_test()
