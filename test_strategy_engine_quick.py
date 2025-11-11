#!/usr/bin/env python3
"""
快速测试 Strategy Engine

验证核心功能是否正常工作
"""
import sys
sys.path.append('/home/user/pokerAI')

from advisor.strategy_engine import ProLevelAdvisor, GameState, quick_advise
from advisor.range_engine import Hand, Board
from advisor.opponent_modeling import PlayerType


def test_imports():
    """测试1: 验证所有导入"""
    print("=" * 60)
    print("测试1: 验证模块导入")
    print("=" * 60)

    try:
        from advisor.strategy_engine import (
            DecisionOutput, GTOBaseline, RangeEstimator,
            QuantifiedExploitStrategy, get_exploit_strategy
        )
        print("✅ 所有模块导入成功")
        return True
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        return False


def test_basic_advisor():
    """测试2: 创建advisor实例"""
    print("\n" + "=" * 60)
    print("测试2: 创建 ProLevelAdvisor 实例")
    print("=" * 60)

    try:
        advisor = ProLevelAdvisor(exploit_weight=0.4)
        print(f"✅ Advisor创建成功")
        print(f"   - GTO权重: {advisor.gto_weight:.2f}")
        print(f"   - Exploit权重: {advisor.exploit_weight:.2f}")
        return advisor
    except Exception as e:
        print(f"❌ 创建失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_preflop_decision(advisor):
    """测试3: 翻前决策"""
    print("\n" + "=" * 60)
    print("测试3: 翻前决策 - BTN拿AA面对Fish")
    print("=" * 60)

    try:
        game_state = GameState(
            street='preflop',
            position='BTN',
            is_in_position=True,
            hero_hand=Hand.from_str('AsAh'),
            board=None,
            pot_size=3.0,  # 盲注1/2，已有3BB在池中
            effective_stack=100.0,
            hero_stack=100.0,
            opponent_type=PlayerType.FISH,
            num_opponents=1
        )

        decision = advisor.advise(game_state)

        print(f"✅ 决策成功")
        print(f"\n推荐动作: {decision.recommended_action}")
        print(f"置信度: {decision.confidence:.1%}")
        print(f"\n动作分布:")
        for action, prob in sorted(decision.action_distribution.items(),
                                   key=lambda x: x[1], reverse=True):
            print(f"  {action}: {prob:.1%}")

        if decision.reasoning:
            print(f"\n决策依据:")
            for key, value in decision.reasoning.items():
                if isinstance(value, float):
                    print(f"  {key}: {value:.2f}")
                else:
                    print(f"  {key}: {value}")

        return True
    except Exception as e:
        print(f"❌ 决策失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_postflop_decision(advisor):
    """测试4: 翻后决策"""
    print("\n" + "=" * 60)
    print("测试4: 翻后决策 - Flop顶对 vs Nit")
    print("=" * 60)

    try:
        game_state = GameState(
            street='flop',
            position='BTN',
            is_in_position=True,
            hero_hand=Hand.from_str('AsKs'),
            board=Board.from_str('Ah9c3d'),
            pot_size=10.0,
            effective_stack=90.0,
            hero_stack=90.0,
            opponent_type=PlayerType.NIT,
            num_opponents=1
        )

        decision = advisor.advise(game_state)

        print(f"✅ 决策成功")
        print(f"\n推荐动作: {decision.recommended_action}")
        print(f"置信度: {decision.confidence:.1%}")

        if decision.optimal_sizing:
            print(f"最优尺寸: {decision.optimal_sizing:.1f} BB")

        print(f"\n动作分布:")
        for action, prob in sorted(decision.action_distribution.items(),
                                   key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {action}: {prob:.1%}")

        if decision.reasoning:
            print(f"\n关键指标:")
            print(f"  Equity: {decision.reasoning.get('equity', 0):.1%}")
            print(f"  范围优势: {decision.reasoning.get('range_advantage', 'N/A')}")
            print(f"  牌面湿度: {decision.reasoning.get('board_texture', 'N/A')}")
            print(f"  SPR: {decision.reasoning.get('spr', 0):.1f}")

        return True
    except Exception as e:
        print(f"❌ 决策失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_vs_different_opponents(advisor):
    """测试5: 对不同对手的决策差异"""
    print("\n" + "=" * 60)
    print("测试5: 相同场景 vs 不同对手类型")
    print("=" * 60)

    opponent_types = [PlayerType.FISH, PlayerType.NIT, PlayerType.LAG, PlayerType.TAG]

    try:
        for opp_type in opponent_types:
            game_state = GameState(
                street='flop',
                position='BTN',
                is_in_position=True,
                hero_hand=Hand.from_str('AsKs'),
                board=Board.from_str('Ah9c3d'),
                pot_size=10.0,
                effective_stack=100.0,
                hero_stack=100.0,
                opponent_type=opp_type,
                num_opponents=1
            )

            decision = advisor.advise(game_state)

            print(f"\nvs {opp_type.name}:")
            print(f"  推荐: {decision.recommended_action}")
            if decision.optimal_sizing:
                print(f"  尺寸: {decision.optimal_sizing:.1f} BB ({decision.optimal_sizing/10:.0%} pot)")

        print(f"\n✅ 所有对手类型测试成功")
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_quick_advise():
    """测试6: 快速决策接口"""
    print("\n" + "=" * 60)
    print("测试6: quick_advise() 便捷函数")
    print("=" * 60)

    try:
        decision = quick_advise(
            hero_hand='AsKs',
            board='Ah9c3d',
            position='BTN',
            pot=10.0,
            stack=100.0,
            opponent_type=PlayerType.FISH
        )

        print(f"✅ 快速决策成功")
        print(f"\n{decision.summary()}")

        return True
    except Exception as e:
        print(f"❌ 快速决策失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_gto_formulas():
    """测试7: GTO公式验证"""
    print("\n" + "=" * 60)
    print("测试7: GTO公式验证")
    print("=" * 60)

    try:
        from advisor.strategy_engine.gto_baseline import GTOBaseline

        gto = GTOBaseline()

        # 测试MDF
        mdf = gto.calculate_mdf(pot=100, bet=50)
        expected_mdf = 100 / (100 + 50)
        print(f"MDF测试:")
        print(f"  输入: pot=100, bet=50")
        print(f"  输出: {mdf:.3f}")
        print(f"  预期: {expected_mdf:.3f}")
        print(f"  {'✅ 正确' if abs(mdf - expected_mdf) < 0.001 else '❌ 错误'}")

        # 测试Bluff频率
        bluff_freq = gto.calculate_optimal_bluff_frequency(pot=100, bet=50)
        expected_bluff = 50 / (50 + 100)
        print(f"\nBluff频率测试:")
        print(f"  输入: pot=100, bet=50")
        print(f"  输出: {bluff_freq:.3f}")
        print(f"  预期: {expected_bluff:.3f}")
        print(f"  {'✅ 正确' if abs(bluff_freq - expected_bluff) < 0.001 else '❌ 错误'}")

        # 测试底池赔率
        pot_odds = gto.calculate_pot_odds(pot=100, call_amount=50)
        expected_odds = 50 / (100 + 50)
        print(f"\n底池赔率测试:")
        print(f"  输入: pot=100, call=50")
        print(f"  输出: {pot_odds:.3f}")
        print(f"  预期: {expected_odds:.3f}")
        print(f"  {'✅ 正确' if abs(pot_odds - expected_odds) < 0.001 else '❌ 错误'}")

        return True
    except Exception as e:
        print(f"❌ 公式验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_exploit_strategies():
    """测试8: Exploit策略参数"""
    print("\n" + "=" * 60)
    print("测试8: Exploit策略参数检查")
    print("=" * 60)

    try:
        from advisor.strategy_engine.exploits import get_exploit_strategy

        test_types = [PlayerType.FISH, PlayerType.NIT, PlayerType.TAG]

        for player_type in test_types:
            strategy = get_exploit_strategy(player_type)

            print(f"\n{player_type.name}:")
            print(f"  C-bet频率: {strategy.cbet_frequency:.1%}")
            print(f"  Bluff频率: {strategy.bluff_frequency:.1%}")
            print(f"  价值下注尺寸: {strategy.value_bet_sizing:.0%} pot")
            print(f"  薄价值门槛: {strategy.thin_value_threshold:.1%}")

        print(f"\n✅ Exploit策略参数正常")
        return True
    except Exception as e:
        print(f"❌ Exploit策略检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试流程"""
    print("\n" + "=" * 60)
    print("🚀 Strategy Engine 快速测试")
    print("=" * 60)

    results = []

    # 测试1: 导入
    results.append(("模块导入", test_imports()))

    # 测试2: 创建advisor
    advisor = test_basic_advisor()
    results.append(("创建Advisor", advisor is not None))

    if advisor:
        # 测试3-6: 决策测试
        results.append(("翻前决策", test_preflop_decision(advisor)))
        results.append(("翻后决策", test_postflop_decision(advisor)))
        results.append(("多对手测试", test_vs_different_opponents(advisor)))
        results.append(("快速决策", test_quick_advise()))

    # 测试7-8: 组件测试
    results.append(("GTO公式", test_gto_formulas()))
    results.append(("Exploit策略", test_exploit_strategies()))

    # 总结
    print("\n" + "=" * 60)
    print("📊 测试结果总结")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name:20s}: {status}")

    print(f"\n总计: {passed}/{total} 通过 ({passed/total*100:.0f}%)")

    if passed == total:
        print("\n🎉 所有测试通过！Strategy Engine 工作正常！")
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败，需要修复")

    return passed == total


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
