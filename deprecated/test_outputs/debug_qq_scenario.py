#!/usr/bin/env python
"""
调试QQ vs LAG 3-bet场景
找出为什么建议fold的根本原因
"""
import sys
sys.path.append('/home/user/pokerAI')

from advisor.range_engine import Hand, Board, EquityCalculator, Range
from advisor.strategy_engine import ProLevelAdvisor, GameState
from advisor.strategy_engine.gto_baseline import GTOBaseline
from advisor.strategy_engine.exploits import get_exploit_strategy
from advisor.strategy_engine.range_estimator import RangeEstimator, Position, Action
from advisor.opponent_modeling import PlayerType

print('=' * 70)
print('🔍 调试 QQ vs LAG 3-bet 场景')
print('=' * 70)

# 场景设置
hero_hand = Hand.from_str('QhQd')
game_state = GameState(
    street='preflop',
    position='BTN',
    is_in_position=True,
    hero_hand=hero_hand,
    pot_size=10.0,  # 已经有3-bet
    effective_stack=90.0,
    hero_stack=90.0,
    opponent_type=PlayerType.LAG,
    action_history=['open', '3bet']
)

print('\n场景信息:')
print(f'手牌: {hero_hand}')
print(f'位置: BTN (IP)')
print(f'底池: 10.0BB')
print(f'对手: LAG')
print(f'动作历史: open -> 3bet')

# 步骤1: 检查范围推断
print('\n' + '=' * 70)
print('步骤1: 范围推断')
print('=' * 70)

estimator = RangeEstimator()

# LAG的3-bet范围
lag_3bet_range = estimator._estimate_3bet_range(
    Position.BB,
    PlayerType.LAG,
    Position.BTN
)

print(f'\nLAG 3-bet范围: {len(lag_3bet_range)} combos')
print(f'范围字符串: {lag_3bet_range}')

# 步骤2: 计算equity（不同迭代次数）
print('\n' + '=' * 70)
print('步骤2: Equity计算')
print('=' * 70)

villain_hands = lag_3bet_range.to_hands()
print(f'\n对手可能手牌: {len(villain_hands)} combos')

# 移除死牌
dead_cards = set(hero_hand.cards)
valid_hands = [h for h in villain_hands if not (set(h.cards) & dead_cards)]
print(f'移除死牌后: {len(valid_hands)} combos')

# 测试不同迭代次数
for iterations in [100, 500, 1000, 5000]:
    calc = EquityCalculator(iterations=iterations)
    result = calc.calculate_vs_range(hero_hand, valid_hands[:50], Board([]), iterations=iterations)
    print(f'\n{iterations:5d}次迭代: Equity = {result.equity:.3f} ({result.equity*100:.1f}%)')

# 步骤3: GTO决策
print('\n' + '=' * 70)
print('步骤3: GTO基线决策')
print('=' * 70)

gto = GTOBaseline()

# 构建GTO上下文
equity = 0.55  # 假设QQ vs LAG 3-bet range约55%
pot = 10.0
to_call = 7.5  # 假设3-bet到7.5BB，我们需要call 7.5
spr = 90.0 / 10.0

gto_context = {
    'equity': equity,
    'pot': pot,
    'to_call': to_call,
    'spr': spr,
    'position': 'BTN',
    'street': 'preflop',
    'is_in_position': True
}

print(f'\nGTO上下文:')
print(f'  Equity: {equity:.1%}')
print(f'  底池: {pot}BB')
print(f'  需要跟注: {to_call}BB')
print(f'  SPR: {spr:.1f}')

# 计算pot odds
pot_odds = to_call / (pot + to_call)
print(f'\n底池赔率: {pot_odds:.1%}')
print(f'Equity vs Pot Odds: {equity:.1%} vs {pot_odds:.1%}')

if equity > pot_odds:
    print('✅ Equity > Pot Odds → 应该至少Call')
else:
    print('❌ Equity < Pot Odds → 可以考虑Fold')

# 步骤4: 检查GTO决策逻辑
print('\n' + '=' * 70)
print('步骤4: 检查决策逻辑问题')
print('=' * 70)

# 创建advisor（使用更高迭代次数）
advisor = ProLevelAdvisor(exploit_weight=0.4)
advisor.equity_calculator.iterations = 1000

print('\n开始完整决策流程...')

try:
    decision = advisor.advise(game_state)

    print(f'\n决策结果:')
    print(f'推荐动作: {decision.recommended_action}')
    print(f'置信度: {decision.confidence:.1%}')
    print(f'\n动作分布:')
    for action, freq in sorted(decision.action_distribution.items(), key=lambda x: -x[1]):
        print(f'  {action:10s}: {freq:5.1%}')

    if decision.reasoning:
        print(f'\n决策理由:')
        for key, value in decision.reasoning.items():
            if key == 'equity':
                print(f'  {key}: {value:.1%}')
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                print(f'  {key}: {value:.3f}')
            else:
                print(f'  {key}: {value}')

except Exception as e:
    print(f'❌ 决策失败: {e}')
    import traceback
    traceback.print_exc()

# 步骤5: 分析问题
print('\n' + '=' * 70)
print('步骤5: 问题分析')
print('=' * 70)

print('\n可能的问题:')
print('1. LAG 3-bet范围估计过宽 → QQ equity被低估')
print('2. Equity计算迭代次数太低 → 结果不准确')
print('3. GTO决策逻辑有bug → fold threshold设置不合理')
print('4. Exploit策略对LAG过于保守')
print('5. 没有考虑hand strength绝对值（QQ是premium hand）')

print('\n期望行为:')
print('✅ QQ vs LAG 3-bet应该至少有45-55% equity')
print('✅ 应该建议 Call 或 4-bet，而不是Fold')
print('✅ 对LAG应该更激进（他们3-bet范围宽，我们应该defend wider）')
