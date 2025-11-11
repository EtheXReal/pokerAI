#!/usr/bin/env python
"""
性能测试：验证方案1优化效果
"""
import sys
sys.path.append('/home/user/pokerAI')

import time
from advisor.range_engine import Hand, Board, EquityCalculator, Range
from advisor.strategy_engine import ProLevelAdvisor, GameState
from advisor.opponent_modeling import PlayerType

print('=' * 60)
print('⚡ 性能优化测试 - 方案1: 降低迭代次数')
print('=' * 60)

# ===== 测试1: Hand vs Hand =====
print('\n[测试1] Hand vs Hand 性能对比')
print('-' * 60)

hero = Hand.from_str('AsKs')
villain = Hand.from_str('QhQd')
board = Board([])

# 旧方案: 10000次
calc_old = EquityCalculator(iterations=10000)
start = time.time()
result_old = calc_old.calculate_equity(hero, villain, board)
time_old = time.time() - start

# 新方案: 1000次
calc_new = EquityCalculator(iterations=1000)
start = time.time()
result_new = calc_new.calculate_equity(hero, villain, board)
time_new = time.time() - start

print(f'旧方案 (10000次): Equity={result_old.equity:.3f}  耗时={time_old*1000:6.1f}ms')
print(f'新方案 (1000次):  Equity={result_new.equity:.3f}  耗时={time_new*1000:6.1f}ms')
print(f'性能提升: {time_old/time_new:.1f}x')
print(f'精度差异: {abs(result_old.equity - result_new.equity)*100:.2f}%')

speedup1 = time_old / time_new
accuracy_loss1 = abs(result_old.equity - result_new.equity) * 100


# ===== 测试2: Hand vs Range =====
print('\n[测试2] Hand vs Range 性能对比')
print('-' * 60)

villain_range = Range.from_string('QQ+,AK')  # 18 combos
villain_hands = villain_range.to_hands()

# 旧方案: 10000次
start = time.time()
try:
    result_old = calc_old.calculate_vs_range(hero, villain_hands[:10], board, iterations=1000)
    time_old = time.time() - start

    # 新方案: 500次
    calc_fast = EquityCalculator(iterations=500)
    start = time.time()
    result_new = calc_fast.calculate_vs_range(hero, villain_hands[:10], board, iterations=500)
    time_new = time.time() - start

    print(f'旧方案 (1000次): Equity={result_old.equity:.3f}  耗时={time_old*1000:6.1f}ms')
    print(f'新方案 (500次):  Equity={result_new.equity:.3f}  耗时={time_new*1000:6.1f}ms')
    print(f'性能提升: {time_old/time_new:.1f}x')
    print(f'精度差异: {abs(result_old.equity - result_new.equity)*100:.2f}%')

    speedup2 = time_old / time_new
    accuracy_loss2 = abs(result_old.equity - result_new.equity) * 100
except Exception as e:
    print(f'测试失败: {e}')
    speedup2 = 0
    accuracy_loss2 = 0


# ===== 测试3: ProLevelAdvisor 端到端 =====
print('\n[测试3] ProLevelAdvisor 决策性能')
print('-' * 60)

advisor = ProLevelAdvisor(exploit_weight=0.4)

# 翻前场景
game_state = GameState(
    street='preflop',
    position='BTN',
    is_in_position=True,
    hero_hand=Hand.from_str('AsAh'),
    pot_size=10.0,
    effective_stack=100.0,
    hero_stack=100.0,
    opponent_type=PlayerType.TAG
)

start = time.time()
try:
    decision = advisor.advise(game_state)
    elapsed = time.time() - start

    print(f'决策耗时: {elapsed*1000:.1f}ms')
    print(f'推荐动作: {decision.recommended_action}')
    print(f'置信度: {decision.confidence:.1%}')

    if elapsed < 0.5:
        print('✅ 性能达标 (< 500ms)')
    elif elapsed < 1.0:
        print('⚠️  性能可接受 (< 1s)')
    else:
        print('❌ 性能需要进一步优化 (> 1s)')

    advisor_time = elapsed * 1000
except Exception as e:
    print(f'测试失败: {e}')
    advisor_time = 999


# ===== 测试4: 不同场景的迭代次数 =====
print('\n[测试4] 上下文感知迭代次数')
print('-' * 60)

scenarios = [
    ('翻前深筹码', GameState(
        street='preflop', position='BTN', is_in_position=True,
        hero_hand=Hand.from_str('AsKs'), pot_size=10, effective_stack=200,
        hero_stack=200
    )),
    ('小底池翻后', GameState(
        street='flop', position='BTN', is_in_position=True,
        hero_hand=Hand.from_str('AsKs'), pot_size=3, effective_stack=100,
        hero_stack=100, board=Board.from_str('KhQs2d')
    )),
    ('Turn中等底池', GameState(
        street='turn', position='CO', is_in_position=False,
        hero_hand=Hand.from_str('AhKh'), pot_size=25, effective_stack=75,
        hero_stack=75, board=Board.from_str('KhQs2d7c')
    )),
]

for name, state in scenarios:
    iters = advisor._get_iterations(state)
    spr = state.effective_stack / state.pot_size if state.pot_size > 0 else 0
    print(f'{name:15s}: {iters:4d}次  (SPR={spr:.1f}, Pot={state.pot_size}BB)')


# ===== 总结 =====
print('\n' + '=' * 60)
print('📊 优化效果总结')
print('=' * 60)

print(f'\n✅ Hand vs Hand:')
print(f'   性能提升: {speedup1:.1f}x')
print(f'   精度损失: {accuracy_loss1:.2f}%')

if speedup2 > 0:
    print(f'\n✅ Hand vs Range:')
    print(f'   性能提升: {speedup2:.1f}x')
    print(f'   精度损失: {accuracy_loss2:.2f}%')

print(f'\n✅ 端到端决策:')
print(f'   耗时: {advisor_time:.1f}ms')
print(f'   目标: < 100ms (需进一步优化)')

print('\n💡 结论:')
if accuracy_loss1 < 1.0:
    print('   精度影响极小 (< 1%)，决策几乎不受影响')
else:
    print(f'   精度损失 {accuracy_loss1:.1f}%，建议评估是否可接受')

if speedup1 >= 8:
    print(f'   性能提升显著 ({speedup1:.1f}x)，方案1实施成功！')
else:
    print(f'   性能提升一般 ({speedup1:.1f}x)，可能需要其他优化')

print('\n下一步: 考虑实施方案3（翻前查表）进一步优化到 < 100ms')
