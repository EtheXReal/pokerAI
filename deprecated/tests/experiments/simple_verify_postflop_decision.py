#!/usr/bin/env python
"""
简单验证：直接看AI决策的中间值
通过添加打印语句来debug
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from poker_core import Hand, Board, Card
from advisor.strategy_engine import ProLevelAdvisor, GameState
from advisor.opponent_modeling import PlayerType

print("=" * 80)
print("简化验证：查看AI决策的实际参数")
print("=" * 80)

# 场景1：BB with Q9o, flop 9d 4h 6c (顶对9)
print("\n场景1：BB with Q9o, flop 9d 4h 6c (顶对9)")
print("-" * 80)

hand = Hand([Card.from_str('Qd'), Card.from_str('9h')])
board = Board([Card.from_str('9d'), Card.from_str('4h'), Card.from_str('6c')])

game_state = GameState(
    street='flop',
    position='BB',
    is_in_position=False,
    hero_hand=hand,
    board=board,
    pot_size=2.0,
    effective_stack=99.0,
    hero_stack=99.0,
    facing_bet=None,
    bet_to_call=None,
    num_opponents=1,
    opponent_type=PlayerType.UNKNOWN
)

ai = ProLevelAdvisor()
decision = ai.advise(game_state)

print(f"\n决策结果:")
print(f"  Action: {decision.recommended_action}")
print(f"  Distribution: {decision.action_distribution}")

# 从决策中反推
bet_freq = decision.action_distribution.get('bet', 0.0)
check_freq = decision.action_distribution.get('check', 0.0)

print(f"\n分析:")
print(f"  Bet频率: {bet_freq:.2f}")
print(f"  Check频率: {check_freq:.2f}")

if bet_freq == 0.2 and check_freq == 0.8:
    print("  → 这是中等牌的硬编码值！")
    print("  → 说明equity < 0.65（进入中等牌分支）")
elif bet_freq > 0.3:
    print("  → 这是使用bet_frequency的值")
    print("  → 说明equity >= 0.65（进入强牌分支）")

print("\n" + "=" * 80)
print("场景2：Turn两对 QhTh")
print("=" * 80)

hand2 = Hand([Card.from_str('Qh'), Card.from_str('Th')])
board2 = Board([
    Card.from_str('8d'),
    Card.from_str('Tc'),
    Card.from_str('3c'),
    Card.from_str('Qd')
])

game_state2 = GameState(
    street='turn',
    position='BB',
    is_in_position=False,
    hero_hand=hand2,
    board=board2,
    pot_size=2.0,
    effective_stack=99.0,
    hero_stack=99.0,
    facing_bet=None,
    bet_to_call=None,
    num_opponents=1,
    opponent_type=PlayerType.UNKNOWN
)

decision2 = ai.advise(game_state2)

print(f"\n决策结果:")
print(f"  Action: {decision2.recommended_action}")
print(f"  Distribution: {decision2.action_distribution}")

bet_freq2 = decision2.action_distribution.get('bet', 0.0)
check_freq2 = decision2.action_distribution.get('check', 0.0)

print(f"\n分析:")
print(f"  Bet频率: {bet_freq2:.2f}")
print(f"  Check频率: {check_freq2:.2f}")

if bet_freq2 == 0.2:
    print("  → 硬编码值（中等牌）")
else:
    print(f"  → 计算值（强牌或弱牌）")

print("\n" + "=" * 80)
print("结论")
print("=" * 80)

print(f"""
观察到的bet频率：
- 场景1 (顶对9): {bet_freq:.2f}
- 场景2 (两对QT): {bet_freq2:.2f}

如果都是0.2或接近0.2 → 说明都进入中等牌分支
如果>0.3 → 说明进入强牌分支，使用bet_frequency

这验证了我们的分析：
1. value_threshold = 0.65太高
2. 大多数value hand (顶对、两对) equity < 0.65
3. 进入中等牌分支，被硬编码80% check

Random的20% bet频率：
- Random bet_rate = 0.2是硬编码的
- 这不是bug，这是测试设计
- Random很passive是正常的

真正的问题是AI也只有20% bet（应该40-60%）
""")

print("\n" + "=" * 80)
print("从bug2Repair.txt统计Random的实际bet频率")
print("=" * 80)

print("""
让我们统计一下bug2Repair.txt中Random实际bet了多少次：

方法：grep "Random bet" bug2Repair.txt | wc -l
""")
