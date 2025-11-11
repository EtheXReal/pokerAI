#!/usr/bin/env python
"""
分析BTN limp的垃圾牌strength值
验证为什么这些牌会被limp
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from advisor.range_engine import Hand, Card
from advisor.strategy_engine.hand_strength import calculate_preflop_hand_strength

# BTN limp的垃圾牌
trash_hands = [
    ('J3o', 'Jh3s'),
    ('Q8o', 'Qd8h'),
    ('T2o', 'Tc2d'),
    ('95o', '9d5h'),
    ('K3o', 'Kd3h'),
    ('83o', '8c3d'),
    ('94o', '9s4h'),
    ('64o', '6d4c'),
]

print("=" * 80)
print("BTN limp垃圾牌的Strength分析")
print("=" * 80)

print("\n分析BTN limp阈值 = 0.35的影响：")
print("-" * 80)

for name, hand_str in trash_hands:
    card1 = Card.from_str(hand_str[0:2])
    card2 = Card.from_str(hand_str[2:4])
    hand = Hand([card1, card2])

    strength = calculate_preflop_hand_strength(hand)

    # BTN limp阈值
    btn_limp_threshold = 0.35
    btn_raise_threshold = 0.50

    if strength >= btn_raise_threshold:
        decision = "RAISE"
    elif strength >= btn_limp_threshold:
        decision = "LIMP"
    else:
        decision = "FOLD"

    print(f"{name:6s}: strength={strength:.3f}  →  {decision:5s}  ", end="")

    if decision == "LIMP" and strength < 0.45:
        print("❌ (垃圾牌应该fold!)")
    elif decision == "LIMP":
        print("⚠️  (弱牌)")
    else:
        print("✅")

print("\n" + "=" * 80)
print("结论分析")
print("=" * 80)

print("""
问题根源：
1. BTN limp_threshold = 0.35 太低
2. 导致所有 strength >= 0.35 的牌都会limp
3. 包括 T2o (0.36), J3o (0.38), 64o (0.37) 这些绝对垃圾

正确的BTN策略应该是：
- strength >= 0.50: RAISE
- strength < 0.50: FOLD (不limp!)

BTN是最好的位置，GTO原则要么raise要么fold，不应该limp。
""")

print("\n如果将BTN limp threshold改为0.50（即取消limp）：")
print("-" * 80)

for name, hand_str in trash_hands:
    card1 = Card.from_str(hand_str[0:2])
    card2 = Card.from_str(hand_str[2:4])
    hand = Hand([card1, card2])

    strength = calculate_preflop_hand_strength(hand)

    # 新策略：BTN不limp
    btn_raise_threshold = 0.50

    if strength >= btn_raise_threshold:
        decision = "RAISE"
    else:
        decision = "FOLD"

    print(f"{name:6s}: strength={strength:.3f}  →  {decision:5s}  ✅")
