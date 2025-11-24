"""
Range-Aware Exploit System - 端到端测试

测试完整的范围感知流程：
1. EquityBucketClassifier分类
2. RangeAwareAdvice提供策略
3. Handler应用调整
4. HybridStrategyRangeAware决策
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from advisor_v2.modeling.range_aware import (
    EquityBucket,
    EquityBucketClassifier,
    ActionFrequencies,
    RangeAwareAdvice,
    DecisionContext,
)
from advisor_v2.modeling.range_aware_handlers import apply_range_aware_adjustment
from advisor_v2.modeling.exploits_range_aware import get_range_aware_strategy_library
from advisor_v2.modeling.models import PlayerType, StreetType
from poker_core.cards import Card


def test_equity_classifier():
    """Test 1: Equity bucket分类"""
    print("="*80)
    print("Test 1: Equity Bucket Classifier")
    print("="*80)

    classifier = EquityBucketClassifier()

    test_cases = [
        ("AA preflop", [Card('A', 'h'), Card('A', 's')], [], EquityBucket.NUTTED),
        ("72o preflop", [Card('7', 'h'), Card('2', 's')], [], EquityBucket.AIR),
        ("AKs preflop", [Card('A', 'h'), Card('K', 'h')], [], EquityBucket.STRONG),
        ("JJ preflop", [Card('J', 'h'), Card('J', 's')], [], EquityBucket.STRONG),
    ]

    passed = 0
    for name, hole_cards, board, expected in test_cases:
        result = classifier.classify(hole_cards, board)
        status = "✅" if result == expected else "❌"
        print(f"  {status} {name:20s}: {result.value:15s} (expected: {expected.value})")
        if result == expected:
            passed += 1

    print(f"\nPassed: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


def test_range_aware_handler():
    """Test 2: Range-aware handler应用"""
    print("\n" + "="*80)
    print("Test 2: Range-Aware Handler")
    print("="*80)

    # GTO baseline
    gto_actions = {'fold': 0.40, 'call': 0.40, 'raise': 0.20}

    # MANIAC defense advice
    advice = RangeAwareAdvice(
        action_type='RANGE_AWARE_DEFENSE',
        bucket_strategies={
            EquityBucket.NUTTED: ActionFrequencies(fold=0.0, call=0.70, raise_=0.30),
            EquityBucket.MEDIUM: ActionFrequencies(fold=0.85, call=0.15, raise_=0.0),
            EquityBucket.AIR: ActionFrequencies(fold=1.0, call=0.0, raise_=0.0),
        },
        reason='Test'
    )

    test_cases = [
        ("Nutted hand", EquityBucket.NUTTED, 0.95, {'fold': 0.0}),  # Should not fold
        ("Medium hand", EquityBucket.MEDIUM, 0.40, {'fold': 0.85}),  # High fold rate
        ("Air", EquityBucket.AIR, 0.10, {'fold': 1.0}),  # Always fold
    ]

    passed = 0
    for name, bucket, equity, expected_contains in test_cases:
        ctx = DecisionContext(
            game_state=None,
            hole_cards=[],
            board=[],
            street=None,
            equity_bucket=bucket,
            equity=equity,
        )

        result = apply_range_aware_adjustment(gto_actions, advice, alpha=1.0, ctx=ctx)

        # Check expected values
        match = all(abs(result.get(k, 0) - v) < 0.01 for k, v in expected_contains.items())
        status = "✅" if match else "❌"

        print(f"  {status} {name}:")
        print(f"      GTO:    {gto_actions}")
        print(f"      Result: {result}")
        print(f"      Expected contains: {expected_contains}")

        if match:
            passed += 1

    print(f"\nPassed: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


def test_maniac_strategy():
    """Test 3: MANIAC range-aware策略"""
    print("\n" + "="*80)
    print("Test 3: MANIAC Range-Aware Strategy")
    print("="*80)

    lib = get_range_aware_strategy_library()
    strategy = lib.get_strategy(PlayerType.MANIAC)

    print(f"Player Type: {strategy.player_type}")
    print(f"Tendencies: {strategy.tendencies}")

    # Check postflop_defense
    defense = strategy.postflop_defense
    print(f"\nPostflop Defense:")
    print(f"  Type: {type(defense).__name__}")
    print(f"  Action Type: {defense.action_type}")

    # Check key buckets
    nutted = defense.get_target_freqs(EquityBucket.NUTTED)
    medium = defense.get_target_freqs(EquityBucket.MEDIUM)
    air = defense.get_target_freqs(EquityBucket.AIR)

    checks = [
        ("Nutted fold rate", nutted.fold, 0.0, 0.01),
        ("Medium fold rate", medium.fold, 0.85, 0.01),
        ("Air fold rate", air.fold, 1.0, 0.01),
    ]

    passed = 0
    for name, actual, expected, tolerance in checks:
        match = abs(actual - expected) < tolerance
        status = "✅" if match else "❌"
        print(f"  {status} {name}: {actual:.2f} (expected: {expected:.2f})")
        if match:
            passed += 1

    print(f"\nPassed: {passed}/{len(checks)}")
    return passed == len(checks)


def test_integration():
    """Test 4: 端到端集成测试"""
    print("\n" + "="*80)
    print("Test 4: End-to-End Integration")
    print("="*80)

    try:
        from advisor_v2.strategy.hybrid_strategy_range_aware import HybridStrategyRangeAware
        from advisor_v2.core.data_structures import StrategyContext
        from poker_core.cards import Hand

        # 创建strategy
        strategy = HybridStrategyRangeAware(config={'use_range_aware': True})

        # 模拟context（AA preflop vs MANIAC）
        ctx = StrategyContext(
            hand=Hand([Card('A', 'h'), Card('A', 's')]),
            board=[],
            pot=10.0,
            to_call=5.0,
            min_raise=10.0,
            stack=95.0,
            position='BTN',
            villain_tendencies={
                'player_type': 'MANIAC',
                'confidence': 0.85,
            },
        )

        # 决策
        decision = strategy.decide(ctx)

        print(f"Context: AA preflop vs MANIAC (confidence=0.85)")
        print(f"Decision: {decision.action_distribution}")
        print(f"Reasoning: {decision.reasoning}")

        # 检查结果：应该倾向于raise/call（不fold）
        fold_prob = decision.action_distribution.get('fold', 0.0)
        has_aggression = decision.action_distribution.get('raise', 0.0) > 0.3

        passed = fold_prob < 0.1 and has_aggression
        status = "✅" if passed else "❌"
        print(f"\n{status} Sanity check: fold<10% and raise>30%")

        return passed

    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("="*80)
    print("Range-Aware Exploit System - Test Suite")
    print("="*80)
    print()

    results = []

    # Run tests
    results.append(("Equity Classifier", test_equity_classifier()))
    results.append(("Range-Aware Handler", test_range_aware_handler()))
    results.append(("MANIAC Strategy", test_maniac_strategy()))
    results.append(("Integration", test_integration()))

    # Summary
    print("\n" + "="*80)
    print("Test Summary")
    print("="*80)

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")

    print()
    print(f"Total: {passed_count}/{total_count} passed")

    if passed_count == total_count:
        print("\n🎉 所有测试通过！Range-aware系统已就绪。")
        return 0
    else:
        print("\n❌ 部分测试失败，需要修复。")
        return 1


if __name__ == '__main__':
    exit(main())
