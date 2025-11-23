#!/usr/bin/env python
"""
调试翻后决策不bet的问题
打印关键参数值
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from poker_core import Hand, Board, Card
from advisor.strategy_engine import ProLevelAdvisor, GameState
from advisor.opponent_modeling import PlayerType

# 模拟Hand #2场景：BB with Q9o, flop顶对9
print("=" * 80)
print("调试场景：Hand #2 - BB with Q9o, flop 9d 4h 6c (顶对9)")
print("=" * 80)

# 创建手牌和公共牌
hand = Hand([Card.from_str('Qd'), Card.from_str('9h')])
board = Board([Card.from_str('9d'), Card.from_str('4h'), Card.from_str('6c')])

# 创建GameState (BB, OOP, facing check)
game_state = GameState(
    street='flop',
    position='BB',
    is_in_position=False,  # BB OOP
    hero_hand=hand,
    board=board,
    pot_size=2.0,
    effective_stack=99.0,
    hero_stack=99.0,
    facing_bet=None,  # Random check了
    bet_to_call=None,
    num_opponents=1,
    opponent_type=PlayerType.UNKNOWN
)

# 创建AI
ai = ProLevelAdvisor()

# 打印调试信息（修改advisor.py添加debug模式）
print("\nGameState:")
print(f"  Street: {game_state.street}")
print(f"  Position: {game_state.position}")
print(f"  In Position: {game_state.is_in_position}")
print(f"  Hand: {hand}")
print(f"  Board: {board}")
print(f"  Pot: {game_state.pot_size}BB")
print(f"  Facing bet: {game_state.facing_bet}")

# 获取决策
decision = ai.advise(game_state)

print("\n决策结果:")
print(f"  Recommended action: {decision.recommended_action}")
print(f"  Action distribution: {decision.action_distribution}")
print(f"  Confidence: {decision.confidence:.2f}")

# 手动计算应该的bet frequency
print("\n" + "=" * 80)
print("分析：为什么AI check了？")
print("=" * 80)

print("""
理论上，BB flop顶对9 facing check应该：
- Equity: ~60-70% (顶对 vs random range)
- Should bet for value频率: ~40-60%

但AI选择了check，可能的原因：
1. range_advantage计算错误
2. bet_frequency计算逻辑问题
3. equity threshold太高
4. board_texture判断问题

需要看代码中这些参数的实际值。
""")

print("\n" + "=" * 80)
print("测试Turn场景：Hand #26 - BB with QT, turn两对")
print("=" * 80)

# Hand #26: QhTh, board 8d Tc 3c Qd
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

print(f"\nHand: {hand2}")
print(f"Board: {board2}")
print(f"两对Q+T，facing check")
print(f"决策: {decision2.recommended_action}")
print(f"Action dist: {decision2.action_distribution}")

print("\n" + "=" * 80)
print("关键问题定位")
print("=" * 80)

print("""
如果AI在这两个场景都check：
- Hand #2: Flop顶对9
- Hand #26: Turn两对Q+T

说明翻后bet逻辑有严重问题。

可能的bug：
1. _calculate_bet_frequency 返回值太低
2. equity threshold (0.65) 太高 - 即使两对也可能equity<0.65 vs wide range
3. range_advantage 总是'weak' - 导致bet_frequency减少
4. 中等equity (0.35-0.65) 被归类为"主要check"

需要检查gto_baseline.py中_aggression_strategy的逻辑。
""")
