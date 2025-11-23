#!/usr/bin/env python
"""
控制变量实验：AI决策依赖hand_strength还是range？

实验设计：
1. Baseline: K7o (strength=0.46, 不在BTN normal range)
2. 实验1: 修改K7o strength to 0.55 (保持range不变)
3. 实验2: 修改BTN range包含K7o (保持strength不变)

如果AI决策依赖strength：实验1应该改变决策
如果AI决策依赖range：实验2应该改变决策
"""
import sys
sys.path.append('/home/user/pokerAI')

from advisor.strategy_engine.advisor import ProLevelAdvisor, GameState
from poker_core import Hand, Board
from advisor.opponent_modeling import PlayerType
from advisor.strategy_engine.hand_strength import calculate_preflop_hand_strength


def test_k7o_decision(experiment_name: str):
    """
    测试K7o在BTN位置的决策

    Args:
        experiment_name: 实验名称
    """
    print(f"\n{'='*80}")
    print(f"实验: {experiment_name}")
    print(f"{'='*80}\n")

    # 创建K7o
    k7o = Hand.from_str("KcTd")  # 实际是KT，但我们用这个来代表K7o的逻辑
    # 让我们用实际的K7o
    k7o = Hand.from_str("Kc7h")

    # 计算strength
    strength = calculate_preflop_hand_strength(k7o)
    print(f"K7o Hand Strength: {strength:.3f}")

    # 创建GameState（BTN位置，无人进池）
    game_state = GameState(
        street='preflop',
        position='BTN',
        is_in_position=True,
        hero_hand=k7o,
        pot_size=1.5,  # SB(0.5) + BB(1.0)
        effective_stack=99.5,  # 100 - 0.5(SB)
        hero_stack=99.5,
        board=Board([]),
        facing_bet=0,
        bet_to_call=0.5,  # 需要补到BB
        action_history=[],  # 无人行动，我们是第一个
        opponent_type=PlayerType.UNKNOWN
    )

    # 创建advisor
    advisor = ProLevelAdvisor()

    # 获取决策
    decision = advisor.advise(game_state)

    print(f"\n决策结果:")
    print(f"  推荐动作: {decision.recommended_action}")
    print(f"  动作分布: {decision.action_distribution}")
    print(f"\n决策依据:")
    for key, value in decision.reasoning.items():
        print(f"  {key}: {value}")

    # 判断是fold还是raise/call
    if 'fold' in decision.recommended_action.lower():
        result = "FOLD"
    elif 'raise' in decision.recommended_action.lower() or 'r' in decision.recommended_action.lower():
        result = "RAISE"
    elif 'call' in decision.recommended_action.lower():
        result = "CALL"
    else:
        result = decision.recommended_action

    print(f"\n{'='*80}")
    print(f"最终决策: {result}")
    print(f"{'='*80}\n")

    return result


def run_all_experiments():
    """运行所有实验"""
    results = {}

    print("\n" + "="*80)
    print("控制变量实验：AI决策依赖hand_strength还是range？")
    print("="*80)

    # Baseline
    print("\n### BASELINE（未修改）###")
    print("K7o strength = 0.46")
    print("BTN normal range = K8o+ (不包含K7o)")
    results['baseline'] = test_k7o_decision("Baseline")

    # 提示用户修改
    print("\n" + "="*80)
    print("请按以下步骤运行实验：")
    print("="*80)
    print("\n实验1: 修改hand_strength（证明决策依赖strength）")
    print("  步骤:")
    print("  1. 编辑 advisor/strategy_engine/hand_strength.py:139")
    print("  2. 将 'return 0.60 if suited else 0.46' 改为 'return 0.62 if suited else 0.55'")
    print("  3. 保存文件")
    print("  4. 重新运行此脚本")
    print("  预期: 如果AI依赖strength，K7o应该从FOLD变为RAISE")

    print("\n实验2: 修改range（证明决策是否依赖range）")
    print("  步骤:")
    print("  1. 先恢复hand_strength.py到原始值(0.46)")
    print("  2. 编辑 advisor/range_engine/preflop_ranges.py:105")
    print("  3. 将 'offsuit': ['A5o+', 'K8o+', ...] 改为 'offsuit': ['A5o+', 'K7o+', ...]")
    print("  4. 保存文件")
    print("  5. 重新运行此脚本")
    print("  预期: 如果AI依赖range，K7o应该从FOLD变为RAISE")
    print("       如果AI依赖strength，K7o应该仍然FOLD")

    return results


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='测试AI决策依赖strength还是range')
    parser.add_argument('--experiment', choices=['baseline', 'strength', 'range', 'all'],
                       default='all',
                       help='选择要运行的实验')

    args = parser.parse_args()

    if args.experiment == 'all':
        results = run_all_experiments()
    else:
        result = test_k7o_decision(args.experiment)
        print(f"\n结果: {result}")
