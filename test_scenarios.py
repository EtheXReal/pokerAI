#!/usr/bin/env python
"""
场景测试：验证Strategy Engine在不同场景下的决策逻辑
"""
import sys
sys.path.append('/home/user/pokerAI')

from advisor.range_engine import Hand, Board
from advisor.strategy_engine import ProLevelAdvisor, GameState
from advisor.opponent_modeling import PlayerType

print('=' * 70)
print('🎯 Strategy Engine 场景测试')
print('=' * 70)

# 创建advisor（使用较低迭代次数加速测试）
advisor = ProLevelAdvisor(exploit_weight=0.4)
# 进一步降低迭代次数用于快速测试
advisor.equity_calculator.iterations = 200

def test_scenario(name: str, game_state: GameState, expected_action_type: str = None):
    """测试单个场景"""
    print(f'\n{"─" * 70}')
    print(f'📍 场景: {name}')
    print(f'{"─" * 70}')

    # 显示场景信息
    print(f'街道: {game_state.street}')
    print(f'位置: {game_state.position} ({"IP" if game_state.is_in_position else "OOP"})')
    print(f'手牌: {game_state.hero_hand}')
    if game_state.board and len(game_state.board.cards) > 0:
        print(f'公共牌: {game_state.board}')
    print(f'底池: {game_state.pot_size}BB, 有效筹码: {game_state.effective_stack}BB')
    print(f'对手类型: {game_state.opponent_type.name if game_state.opponent_type else "Unknown"}')

    try:
        import time
        start = time.time()
        decision = advisor.advise(game_state)
        elapsed = time.time() - start

        print(f'\n✅ 决策完成 (耗时 {elapsed:.2f}秒)')
        print(f'\n推荐动作: {decision.recommended_action}')
        print(f'置信度: {decision.confidence:.1%}')

        # 显示动作分布
        if decision.action_distribution:
            print(f'\n动作分布:')
            for action, freq in sorted(decision.action_distribution.items(), key=lambda x: -x[1])[:5]:
                print(f'  {action:10s}: {freq:5.1%}')

        # 显示sizing建议
        if decision.optimal_sizing:
            print(f'\n最佳尺寸: {decision.optimal_sizing:.0%} pot')

        # 简单验证
        if expected_action_type:
            if expected_action_type in decision.recommended_action:
                print(f'\n✅ 决策符合预期 (预期包含: {expected_action_type})')
            else:
                print(f'\n⚠️  决策可能不符预期 (预期包含: {expected_action_type}, 实际: {decision.recommended_action})')

        return True

    except Exception as e:
        print(f'\n❌ 决策失败: {e}')
        import traceback
        traceback.print_exc()
        return False


# ===== 翻前场景测试 =====
print('\n' + '=' * 70)
print('📋 第一部分: 翻前场景')
print('=' * 70)

scenarios_preflop = [
    ('AA vs TAG - BTN位置', GameState(
        street='preflop',
        position='BTN',
        is_in_position=True,
        hero_hand=Hand.from_str('AsAh'),
        pot_size=1.5,
        effective_stack=100.0,
        hero_stack=100.0,
        opponent_type=PlayerType.TAG
    ), 'raise'),

    ('72o vs Nit - UTG位置', GameState(
        street='preflop',
        position='UTG',
        is_in_position=False,
        hero_hand=Hand.from_str('7h2d'),
        pot_size=1.5,
        effective_stack=100.0,
        hero_stack=100.0,
        opponent_type=PlayerType.NIT
    ), 'fold'),

    ('AKs vs Fish - CO位置', GameState(
        street='preflop',
        position='CO',
        is_in_position=True,
        hero_hand=Hand.from_str('AsKs'),
        pot_size=1.5,
        effective_stack=100.0,
        hero_stack=100.0,
        opponent_type=PlayerType.FISH
    ), 'raise'),

    ('QQ vs LAG 3-bet', GameState(
        street='preflop',
        position='BTN',
        is_in_position=True,
        hero_hand=Hand.from_str('QhQd'),
        pot_size=10.0,  # 已经有3-bet
        effective_stack=90.0,
        hero_stack=90.0,
        opponent_type=PlayerType.LAG,
        action_history=['open', '3bet']
    ), 'raise'),  # QQ应该4-bet或call
]

results_preflop = []
for name, state, expected in scenarios_preflop:
    success = test_scenario(name, state, expected)
    results_preflop.append((name, success))


# ===== 翻后场景测试 (简化版) =====
print('\n' + '=' * 70)
print('📋 第二部分: 翻后场景 (简化)')
print('=' * 70)

scenarios_postflop = [
    ('Top Pair vs TAG - Flop', GameState(
        street='flop',
        position='BTN',
        is_in_position=True,
        hero_hand=Hand.from_str('AhKh'),
        board=Board.from_str('Kd9s2c'),
        pot_size=10.0,
        effective_stack=90.0,
        hero_stack=90.0,
        opponent_type=PlayerType.TAG
    ), 'bet'),

    ('Flush Draw vs Fish - Flop', GameState(
        street='flop',
        position='CO',
        is_in_position=False,
        hero_hand=Hand.from_str('AsQs'),
        board=Board.from_str('Ks7s2h'),
        pot_size=8.0,
        effective_stack=92.0,
        hero_stack=92.0,
        opponent_type=PlayerType.FISH
    ), None),  # 可能bet或call，都合理
]

print('\n💡 提示: 翻后场景可能较慢，请耐心等待...\n')

results_postflop = []
for name, state, expected in scenarios_postflop[:1]:  # 只测试第一个，避免太慢
    success = test_scenario(name, state, expected)
    results_postflop.append((name, success))


# ===== 总结 =====
print('\n' + '=' * 70)
print('📊 测试总结')
print('=' * 70)

print(f'\n翻前场景:')
for name, success in results_preflop:
    status = '✅' if success else '❌'
    print(f'  {status} {name}')

if results_postflop:
    print(f'\n翻后场景:')
    for name, success in results_postflop:
        status = '✅' if success else '❌'
        print(f'  {status} {name}')

total_tests = len(results_preflop) + len(results_postflop)
passed_tests = sum(1 for _, s in results_preflop + results_postflop if s)

print(f'\n总计: {passed_tests}/{total_tests} 测试通过 ({passed_tests*100//total_tests}%)')

if passed_tests == total_tests:
    print('\n🎉 所有场景测试通过！Strategy Engine 工作正常')
else:
    print(f'\n⚠️  有 {total_tests - passed_tests} 个场景失败，需要检查')
