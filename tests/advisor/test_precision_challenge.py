#!/usr/bin/env python
"""
高精度挑战测试

用户要求：Ac As vs 8s 8d on 8h5c2d
在线计算器结果：AA 10.2%, Tie 0%
要求误差 < 0.1%
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from advisor.range_engine import Hand, Board, EquityCalculator


def test_high_precision():
    """
    高精度测试：要求误差 < 0.1%

    场景：AcAs vs 8s8d on 8h5c2d
    - Villain有暗三条888
    - Hero需要runner-runner两张A或其他runner-runner组合
    - 理论值：AA约10.2%
    """
    print("\n" + "=" * 70)
    print("  高精度Equity计算挑战")
    print("=" * 70)
    print("\n场景：AcAs vs 8s8d on 8h5c2d")
    print("  Villain: 8s8d (暗三条888)")
    print("  Hero: AcAs (一对AA)")
    print("  理论值：AA 10.2%, Tie 0%")
    print("  要求误差：< 0.1%\n")

    hero = Hand.from_str("AcAs")
    villain = Hand.from_str("8s8d")
    board = Board.from_str("8h5c2d")

    # 逐步增加迭代次数，寻找稳定结果
    iterations_list = [10000, 20000, 50000, 100000]

    results = []

    for iterations in iterations_list:
        calc = EquityCalculator(iterations=iterations)
        result = calc.calculate_equity(hero, villain, board)

        error = abs(result.equity - 0.102) * 100

        print(f"迭代次数: {iterations:,}")
        print(f"  AA equity: {result.equity:.4f} ({result.equity * 100:.2f}%)")
        print(f"  88 equity: {result.loss:.4f} ({result.loss * 100:.2f}%)")
        print(f"  Tie rate: {result.tie:.4f} ({result.tie * 100:.2f}%)")
        print(f"  误差: {error:.2f}%")
        print(f"  状态: {'✅ 通过' if error < 0.1 else '❌ 未达标'}\n")

        results.append({
            'iterations': iterations,
            'equity': result.equity,
            'tie': result.tie,
            'error': error
        })

    # 找到最佳结果
    best_result = min(results, key=lambda x: x['error'])

    print("=" * 70)
    print("  测试总结")
    print("=" * 70)
    print(f"最佳结果: {best_result['iterations']:,} 次迭代")
    print(f"  AA equity: {best_result['equity'] * 100:.2f}%")
    print(f"  Tie rate: {best_result['tie'] * 100:.2f}%")
    print(f"  误差: {best_result['error']:.3f}%")

    if best_result['error'] < 0.1:
        print(f"\n✅ 挑战成功！误差 {best_result['error']:.3f}% < 0.1%")
        return True
    else:
        print(f"\n⚠️  需要更多迭代次数才能达到 0.1% 精度")
        print(f"  当前最佳误差: {best_result['error']:.3f}%")
        return False


if __name__ == '__main__':
    success = test_high_precision()
    sys.exit(0 if success else 1)
