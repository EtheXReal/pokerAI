"""测试HybridStrategy是否真的在使用exploit调整"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from advisor_v2.strategy.hybrid_strategy import HybridStrategy
from advisor_v2.core.data_structures import StrategyContext

# 启用调试
os.environ['DEBUG_HYBRID'] = '1'

# 创建HybridStrategy
strategy = HybridStrategy()

print("="*80)
print("测试1: 低confidence (0.2) - 应该使用纯GTO")
print("="*80)

ctx1 = StrategyContext(
    street='preflop',
    pot=10.0,
    to_call=3.0,
    hero_stack=100.0,
    villain_tendencies={
        'player_type': 'MANIAC',
        'confidence': 0.2,
        'vpip': 0.75,
        'pfr': 0.60
    }
)

decision1 = strategy.decide(ctx1)
print(f"Decision: {decision1.action_distribution}\n")

print("="*80)
print("测试2: 高confidence (0.9) - 应该使用高权重exploit")
print("="*80)

ctx2 = StrategyContext(
    street='preflop',
    pot=10.0,
    to_call=3.0,
    hero_stack=100.0,
    villain_tendencies={
        'player_type': 'MANIAC',
        'confidence': 0.9,
        'vpip': 0.75,
        'pfr': 0.60
    }
)

decision2 = strategy.decide(ctx2)
print(f"Decision: {decision2.action_distribution}\n")

print("="*80)
print("测试3: UNKNOWN player_type - 应该使用纯GTO")
print("="*80)

ctx3 = StrategyContext(
    street='preflop',
    pot=10.0,
    to_call=3.0,
    hero_stack=100.0,
    villain_tendencies={
        'player_type': 'UNKNOWN',
        'confidence': 0.9
    }
)

decision3 = strategy.decide(ctx3)
print(f"Decision: {decision3.action_distribution}\n")

print("="*80)
print("测试4: 没有villain_tendencies - 应该使用纯GTO")
print("="*80)

ctx4 = StrategyContext(
    street='preflop',
    pot=10.0,
    to_call=3.0,
    hero_stack=100.0
)

decision4 = strategy.decide(ctx4)
print(f"Decision: {decision4.action_distribution}\n")
