#!/usr/bin/env python
"""
验证equity和range_advantage的实际计算值
看看是否存在计算问题
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from advisor.range_engine import Hand, Board, Card, Range
from advisor.strategy_engine import ProLevelAdvisor, GameState
from advisor.opponent_modeling import PlayerType
from advisor.range_engine.preflop_ranges import get_open_range

print("=" * 80)
print("验证equity和range_advantage计算")
print("=" * 80)

# 测试场景1：BB with Q9o, flop 9d 4h 6c (顶对9)
print("\n场景1：BB with Q9o, flop 9d 4h 6c (顶对9)")
print("-" * 80)

hand = Hand([Card.from_str('Qd'), Card.from_str('9h')])
board = Board([Card.from_str('9d'), Card.from_str('4h'), Card.from_str('6c')])

# 创建GameState
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

# 创建AI并启用debug模式
ai = ProLevelAdvisor()

# 我们需要手动调用内部方法来看中间值
# 先估计range
from advisor.strategy_engine.range_estimator import RangeEstimator, Action

range_estimator = RangeEstimator()

# 估计对手range（Random应该是很宽的range）
# Random在flop之前只是limp，所以range很宽
villain_actions = [Action.LIMP]  # 假设Random只是limp进来的
villain_range = range_estimator.estimate_preflop_range(
    position='BTN',
    actions=villain_actions,
    tightness='loose',  # Random应该是loose
    aggression=0.3
)

# 估计hero range
hero_range = range_estimator.estimate_preflop_range(
    position='BB',
    actions=[Action.CHECK],
    tightness='normal',
    aggression=0.5
)

print(f"\nHero range size: {len(hero_range)} combos")
print(f"Villain range size: {len(villain_range)} combos")
print(f"Range ratio: {len(hero_range) / len(villain_range):.2f}")

# 判断range_advantage
hero_size = len(hero_range)
villain_size = len(villain_range)

if hero_size > villain_size * 1.3:
    range_advantage = 'strong'
elif hero_size > villain_size * 0.8:
    range_advantage = 'medium'
else:
    range_advantage = 'weak'

print(f"Range advantage: {range_advantage}")

# 计算equity
from advisor.range_engine import EquityCalculator

equity_calc = EquityCalculator()
result = equity_calc.calculate(
    hero_hand=hand,
    villain_range=villain_range,
    board=board,
    num_opponents=1,
    iterations=1000,
    max_combos=100
)

print(f"\nEquity: {result.win_rate:.3f}")
print(f"Win: {result.win_rate:.3f}, Tie: {result.tie_rate:.3f}")

# 检查value_threshold
value_threshold_oop = 0.65
value_threshold_ip = 0.55

print(f"\nValue threshold (OOP): {value_threshold_oop}")
print(f"Equity >= threshold? {result.win_rate >= value_threshold_oop}")

if result.win_rate >= value_threshold_oop:
    print("  → 进入'强牌'分支，使用bet_frequency")
elif result.win_rate >= 0.35:
    print("  → 进入'中等牌'分支，硬编码80% check ❌")
else:
    print("  → 进入'弱牌'分支，bluff")

# 计算bet_frequency
from advisor.strategy_engine.gto_baseline import GTOBaseline, GTOContext, Street, Position

gto = GTOBaseline()

# 构建context
ctx = GTOContext(
    street=Street.FLOP,
    position=Position.BB,
    is_in_position=False,
    equity=result.win_rate,
    range_advantage=range_advantage,
    pot_size=2.0,
    effective_stack=99.0,
    spr=99.0 / 2.0,
    num_opponents=1,
    facing_bet=None,
    bet_to_call=None,
    board_texture='medium'  # 假设
)

bet_frequency = gto._calculate_bet_frequency(ctx)
print(f"\nCalculated bet_frequency: {bet_frequency:.3f}")

# 模拟完整的aggression_strategy逻辑
base_freq = 0.5

# Range advantage调整
if range_advantage == 'strong':
    base_freq += 0.2
elif range_advantage == 'weak':
    base_freq -= 0.2

print(f"\nBet frequency calculation breakdown:")
print(f"  Base: 0.5")
print(f"  Range advantage ({range_advantage}): {base_freq - 0.5:+.1f}")

# 位置调整
if not ctx.is_in_position:
    base_freq -= 0.1
    print(f"  Position (OOP): -0.1")

print(f"  Final bet_frequency: {base_freq:.2f}")

print("\n" + "=" * 80)
print("场景2：Turn两对 - Hand #26")
print("=" * 80)

hand2 = Hand([Card.from_str('Qh'), Card.from_str('Th')])
board2 = Board([
    Card.from_str('8d'),
    Card.from_str('Tc'),
    Card.from_str('3c'),
    Card.from_str('Qd')
])

result2 = equity_calc.calculate(
    hero_hand=hand2,
    villain_range=villain_range,
    board=board2,
    num_opponents=1,
    iterations=1000,
    max_combos=100
)

print(f"Hand: QhTh (两对)")
print(f"Board: {board2}")
print(f"Equity: {result2.win_rate:.3f}")
print(f"Value threshold (OOP): {value_threshold_oop}")
print(f"Equity >= threshold? {result2.win_rate >= value_threshold_oop}")

if result2.win_rate >= value_threshold_oop:
    print("  → 进入'强牌'分支 ✅")
    print(f"  → bet_freq = bet_frequency = {bet_frequency:.3f}")
else:
    print("  → 进入'中等牌'分支 ❌")
    print("  → 硬编码 bet_freq = 0.2")

print("\n" + "=" * 80)
print("总结")
print("=" * 80)

print(f"""
发现：

1. Range advantage可能是'weak'
   - Hero range: {len(hero_range)} combos
   - Villain range: {len(villain_range)} combos
   - 如果hero < villain * 0.8 → 'weak'
   - 导致bet_frequency减少0.2

2. 顶对的equity确实在0.55-0.62区间
   - 场景1 Q9o顶对9: equity ≈ {result.win_rate:.3f}
   - 低于threshold 0.65 → 进入中等牌分支

3. 中等牌被硬编码80% check
   - 即使bet_frequency计算是0.3-0.5
   - 也被强制改为0.2

4. Random range可能被估计得太宽
   - 如果Random被认为是100% range
   - 而AI range更窄（比如40-50%）
   - 就会导致range_advantage = 'weak'

修复建议：
1. 降低value_threshold: 0.65 → 0.55 (OOP)
2. 移除中等牌硬编码
3. (可选) 检查range估计逻辑
""")
