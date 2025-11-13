#!/usr/bin/env python
"""
验证 A8s vs BTN normal 范围的 equity
测试不同采样数，看结果是否稳定
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from advisor.range_engine import (
    EquityCalculator, Range, parse_range_dict, get_open_range
)
from treys import Card


def test_a8s_vs_btn():
    """测试 A8s vs BTN normal"""
    print("=" * 60)
    print("验证: A8s vs BTN normal 范围")
    print("=" * 60)

    # 手牌: A8s
    hero = [Card.new('As'), Card.new('8s')]
    print(f"英雄手牌: As 8s (A8 suited)")

    # BTN normal 范围
    btn_range = parse_range_dict(get_open_range('BTN', 'normal'))
    print(f"BTN normal 范围: {btn_range.size()} combos")
    print(f"VPIP: {btn_range.size() / 1326:.1%}")

    # 显示BTN范围内容
    btn_dict = get_open_range('BTN', 'normal')
    print(f"\nBTN normal 范围包含:")
    print(f"  Pairs: {btn_dict['pairs']}")
    print(f"  Suited: {btn_dict['suited']}")
    print(f"  Offsuit: {btn_dict['offsuit']}")

    calc = EquityCalculator()

    # 测试不同采样数
    print("\n" + "=" * 60)
    print("不同采样数的 equity 结果:")
    print("=" * 60)

    results = []
    for nsamples in [500, 1000, 2000, 5000]:
        equity = calc.hand_vs_range(hero, btn_range, [], nsamples=nsamples)
        results.append(equity)
        print(f"n={nsamples:5d}: {equity:.3f} ({equity:.1%})")

    avg_equity = sum(results) / len(results)
    print(f"\n平均 equity: {avg_equity:.3f} ({avg_equity:.1%})")

    # 分析
    print("\n" + "=" * 60)
    print("分析:")
    print("=" * 60)

    if avg_equity > 0.48:
        print(f"⚠️  Equity {avg_equity:.1%} 偏高")
        print("   预期应该在 40-45% (A8s vs 46% VPIP范围)")
    elif avg_equity < 0.38:
        print(f"⚠️  Equity {avg_equity:.1%} 偏低")
    else:
        print(f"✅ Equity {avg_equity:.1%} 合理")
        print("   A8s vs BTN宽范围处于劣势，但有一定对抗能力")


def test_a8s_vs_specific_hands():
    """测试 A8s vs 特定手牌组合"""
    print("\n" + "=" * 60)
    print("A8s vs 具体手牌类型的 equity:")
    print("=" * 60)

    hero = [Card.new('As'), Card.new('8s')]
    calc = EquityCalculator()

    test_cases = [
        ("AA,KK,QQ", "大对子 (AA/KK/QQ)"),
        ("JJ,TT,99,88", "中对子 (JJ-88)"),
        ("77,66,55,44,33,22", "小对子 (77-22)"),
        ("AKs,AQs,AJs,ATs,A9s", "Ax suited (强kicker)"),
        ("A7s,A6s,A5s,A4s,A3s,A2s", "Ax suited (弱kicker)"),
        ("KQs,KJs,KTs,QJs,QTs,JTs", "高牌同花连牌"),
        ("AKo,AQo,AJo,ATo", "Ax offsuit (强kicker)"),
        ("KQo,KJo,QJo", "高牌非同花"),
    ]

    for range_str, desc in test_cases:
        villain_range = Range(range_str)
        villain_range.remove_dead_cards(["As", "8s"])

        if villain_range.size() == 0:
            print(f"{desc:30s}: N/A (无可用combo)")
            continue

        equity = calc.hand_vs_range(hero, villain_range, [], nsamples=1000)
        print(f"{desc:30s}: {equity:.3f} ({equity:.1%})")


def test_a8s_vs_different_positions():
    """测试 A8s vs 不同位置的范围"""
    print("\n" + "=" * 60)
    print("A8s vs 不同位置的 equity:")
    print("=" * 60)

    hero = [Card.new('As'), Card.new('8s')]
    calc = EquityCalculator()

    positions = ['UTG', 'MP', 'CO', 'BTN']

    for pos in positions:
        pos_range = parse_range_dict(get_open_range(pos, 'normal'))
        pos_range.remove_dead_cards(["As", "8s"])

        equity = calc.hand_vs_range(hero, pos_range, [], nsamples=2000)
        vpip = pos_range.size() / 1326

        print(f"{pos:5s} (VPIP {vpip:.1%}): equity = {equity:.3f} ({equity:.1%})")

    print("\n预期: UTG < MP < CO < BTN (位置越晚范围越宽，A8s equity越高)")


if __name__ == '__main__':
    test_a8s_vs_btn()
    test_a8s_vs_specific_hands()
    test_a8s_vs_different_positions()

    print("\n" + "=" * 60)
    print("验证完成")
    print("=" * 60)
