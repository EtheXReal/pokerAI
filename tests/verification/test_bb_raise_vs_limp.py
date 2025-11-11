#!/usr/bin/env python
"""
验证BB拿到强牌vs limp会Raise

测试场景：
- Hand #1: BB with TT vs limp → Should raise
- Hand #2: BB with KK vs limp → Should raise
- Hand #3: BB with 88 vs limp → Should raise
- Hand #4: BB with AQo vs limp → Should raise
- Hand #5: BB with 77 vs limp → Should check (below threshold)
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from advisor.range_engine import Hand, Card
from advisor.strategy_engine import ProLevelAdvisor, GameState
from advisor.strategy_engine.hand_strength import calculate_preflop_hand_strength


def test_bb_vs_limp(hand_str: str, expected_action: str):
    """测试BB面对limp的决策"""
    # 创建手牌
    card1 = Card.from_str(hand_str[0:2])
    card2 = Card.from_str(hand_str[2:4])
    hand = Hand([card1, card2])

    # 计算strength
    strength = calculate_preflop_hand_strength(hand)

    # 创建GameState (BB面对limp)
    game_state = GameState(
        street='preflop',
        position='BB',
        is_in_position=False,  # BB out of position
        hero_hand=hand,
        pot_size=2.0,  # SB 0.5 + BB 1.0 + BTN limp 0.5
        effective_stack=100.0,
        hero_stack=99.0,  # BB已投入1BB
        facing_bet=0.0,  # BB已投入1BB，limp后不需要再投注
        action_history=['call'],  # BTN limp
        num_opponents=1
    )

    # 创建AI
    ai = ProLevelAdvisor()

    # 获取决策
    decision = ai.advise(game_state)
    action = decision.recommended_action.lower()

    # 解析动作（和test_full_postflop_10hands.py中一样的逻辑）
    if 'raise' in action or action.startswith('r'):
        base_action = 'raise'
    elif 'call' in action or 'check' in action:
        base_action = 'check'  # BB facing limp, call = check
    elif 'fold' in action:
        base_action = 'fold'
    else:
        base_action = action

    # 输出结果
    print(f"\n{hand_str}: {hand.cards[0]} {hand.cards[1]}")
    print(f"  Strength: {strength:.2f}")
    print(f"  Raw action: {action}")
    print(f"  Base action: {base_action}")
    print(f"  Action dist: {decision.action_distribution}")

    # 验证
    if base_action == expected_action:
        print(f"  ✅ PASS (expected {expected_action})")
        return True
    else:
        print(f"  ❌ FAIL (expected {expected_action}, got {base_action})")
        return False


def main():
    print("=" * 80)
    print("🧪 BB vs Limp 强牌Raise测试")
    print("=" * 80)

    test_cases = [
        # (hand, expected_action, description)
        ('TcTh', 'raise', 'TT (0.82) should raise'),
        ('KcKd', 'raise', 'KK (0.95) should raise'),
        ('8d8s', 'raise', '88 (0.72) should raise'),
        ('AcQd', 'raise', 'AQo (0.76) should raise'),
        ('AcTc', 'raise', 'ATs (0.76) should raise'),  # ✅ Fixed: same suit
        ('7c7d', 'check', '77 (0.69) should check (below 0.72)'),
        ('AcJd', 'check', 'AJo (0.71) should check (below 0.72)'),
        ('Qc9h', 'check', 'Q9o (0.52) should check'),
    ]

    results = []
    for hand_str, expected, description in test_cases:
        print(f"\n--- {description} ---")
        success = test_bb_vs_limp(hand_str, expected)
        results.append((description, success))

    # 总结
    print("\n" + "=" * 80)
    print("📊 测试结果汇总")
    print("=" * 80)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for desc, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {desc}")

    print(f"\n通过率: {passed}/{total} ({100*passed//total}%)")

    if passed == total:
        print("\n🎉 所有测试通过！BB vs limp raise逻辑工作正常")
    else:
        print(f"\n⚠️  {total - passed}个测试失败，需要检查逻辑")


if __name__ == '__main__':
    main()
