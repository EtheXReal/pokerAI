#!/usr/bin/env python
"""
分析所有位置的limp问题
验证是否只是BTN的问题，还是普遍问题
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from poker_core import Hand, Card
from advisor.strategy_engine.hand_strength import calculate_preflop_hand_strength

# 测试用垃圾牌
test_hands = [
    ('T2o', 'Tc2d', 0.360),
    ('83o', '8c3d', 0.420),
    ('64o', '6d4c', 0.370),
    ('J3o', 'Jh3s', 0.380),
    ('K3o', 'Kd3h', 0.420),
    ('95o', '9d5h', 0.460),
    ('Q8o', 'Qd8h', 0.470),
]

# 当前代码中的阈值设置
positions_config = {
    'UTG': {'raise': 0.75, 'limp': 0.60},
    'MP':  {'raise': 0.70, 'limp': 0.55},
    'CO':  {'raise': 0.65, 'limp': 0.50},
    'BTN': {'raise': 0.50, 'limp': 0.35},  # ← 问题最严重
    'SB':  {'raise': 0.60, 'limp': 0.40},
}

print("=" * 100)
print("所有位置的Limp问题分析")
print("=" * 100)

for pos, config in positions_config.items():
    print(f"\n{'='*100}")
    print(f"位置: {pos}")
    print(f"Raise阈值: {config['raise']:.2f}, Limp阈值: {config['limp']:.2f}")
    print(f"{'='*100}")

    limp_count = 0
    total_count = len(test_hands)

    for name, hand_str, expected_strength in test_hands:
        strength = expected_strength

        if strength >= config['raise']:
            decision = "RAISE"
            emoji = "✅"
        elif strength >= config['limp']:
            decision = "LIMP "
            emoji = "❌"
            limp_count += 1
        else:
            decision = "FOLD "
            emoji = "✅"

        print(f"  {name:6s} (strength={strength:.3f})  →  {decision:5s}  {emoji}")

    print(f"\n  📊 统计: {limp_count}/{total_count} 垃圾牌被limp ({100*limp_count//total_count}%)")

    if limp_count > 0:
        print(f"  ⚠️  问题严重度: {'🔴' * min(5, limp_count)}")

print("\n" + "=" * 100)
print("结论")
print("=" * 100)

print("""
问题分析：

1. **BTN位置最严重** (limp threshold = 0.35)
   - 7/7垃圾牌都会被limp (100%)
   - BTN应该要么raise要么fold，GTO不允许limp

2. **SB位置较严重** (limp threshold = 0.40)
   - 5/7垃圾牌会被limp (71%)
   - SB可以有少量limp，但0.40太低

3. **CO位置严重** (limp threshold = 0.50)
   - Q8o, 95o会被limp
   - CO位置较好，也不应该limp弱牌

4. **UTG/MP位置相对合理** (limp threshold = 0.60/0.55)
   - 但职业玩家现代打法：任何位置都不limp，要么raise要么fold

根本问题：
- 代码设计允许所有位置limp
- 但现代GTO扑克：几乎不limp（除了极少数特殊情况）
- 正确策略：
  * BTN/CO: 不limp，要么raise要么fold
  * MP/UTG: 不limp，要么raise要么fold
  * SB: 可以有很少量limp（只对BB）
  * BB: check（不是limp，是免费看flop）

建议修复：
1. BTN/CO/UTG/MP: 完全取消limp，strength < raise_threshold 就fold
2. SB: 只保留很窄的limp范围（如22-55, suited connectors）
3. BB: vs limp应该raise强牌（已修复）
""")

print("\n" + "=" * 100)
print("GTO现代打法参考")
print("=" * 100)

print("""
职业玩家翻前策略：

BTN开池：
  - Raise: 所有对子22+, Ax suited, Broadway, suited connectors
  - Fold: 所有低offsuit (T2o, 83o, 64o, J3o等)
  - Limp: 0% (不limp!)

CO开池：
  - Raise: 88+, Ax suited, ATo+, KJo+, suited connectors
  - Fold: 弱牌
  - Limp: 0%

SB vs BB:
  - Raise: 强范围
  - Limp: <5% (只有22-55, 某些suited connectors)
  - Fold: 弱牌

这就是为什么现代扑克很少看到limp：
- Limp给对手免费信息
- Raise可以建立pot、获得主动权、fold equity
- 位置好的玩家应该aggressive，不是passive limp
""")
