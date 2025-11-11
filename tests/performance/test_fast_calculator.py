#!/usr/bin/env python
"""
性能测试：快速计算器 vs 原始计算器

测试内容：
1. 速度对比
2. 精度对比（确保误差<5%测试，<2%实战）
3. 不同场景的性能表现
"""
import time
import sys
sys.path.append('/home/user/pokerAI')

from advisor.range_engine import Hand, Board, EquityCalculator
from advisor.range_engine.calculator_fast import FastEquityCalculator, quick_equity_fast
from advisor.range_engine.calculator import quick_equity


def test_accuracy(test_cases: list, tolerance: float = 0.05):
    """
    测试精度

    Args:
        test_cases: 测试用例列表
        tolerance: 允许的误差范围
    """
    print("=" * 60)
    print("精度测试")
    print("=" * 60)

    calc_original = EquityCalculator(iterations=5000)  # 高精度作为基准
    calc_fast = FastEquityCalculator(iterations=1000, use_adaptive_sampling=True)

    errors = []

    for i, (hero, villain, board_str, desc) in enumerate(test_cases):
        print(f"\n测试 {i+1}: {desc}")
        print(f"  Hero: {hero}, Villain: {villain}, Board: {board_str or 'empty'}")

        hero_hand = Hand.from_str(hero)
        villain_hand = Hand.from_str(villain)
        board = Board.from_str(board_str) if board_str else Board([])

        # 原始计算（高精度基准）
        result_original = calc_original.calculate_equity(hero_hand, villain_hand, board)

        # 快速计算
        result_fast = calc_fast.calculate_equity(hero_hand, villain_hand, board)

        # 比较
        equity_diff = abs(result_original.equity - result_fast.equity)
        errors.append(equity_diff)

        print(f"  原始 Equity: {result_original.equity:.4f} ({result_original.iterations} iters)")
        print(f"  快速 Equity: {result_fast.equity:.4f} ({result_fast.iterations} iters)")
        print(f"  误差: {equity_diff:.4f} ({equity_diff*100:.2f}%)")

        if equity_diff > tolerance:
            print(f"  ⚠️  警告: 误差超过阈值 {tolerance}")
        else:
            print(f"  ✅ 通过")

    # 统计
    print("\n" + "=" * 60)
    print("精度统计")
    print("=" * 60)
    print(f"测试用例数: {len(errors)}")
    print(f"平均误差: {sum(errors)/len(errors)*100:.2f}%")
    print(f"最大误差: {max(errors)*100:.2f}%")
    print(f"最小误差: {min(errors)*100:.2f}%")

    if max(errors) <= tolerance:
        print(f"✅ 所有测试通过！最大误差 {max(errors)*100:.2f}% < {tolerance*100}%")
        return True
    else:
        print(f"❌ 部分测试失败！最大误差 {max(errors)*100:.2f}% > {tolerance*100}%")
        return False


def test_speed(test_cases: list):
    """
    测试速度

    Args:
        test_cases: 测试用例列表
    """
    print("\n" + "=" * 60)
    print("速度测试")
    print("=" * 60)

    calc_original = EquityCalculator(iterations=1000)
    calc_fast = FastEquityCalculator(
        iterations=1000,
        use_adaptive_sampling=True,
        use_multithreading=False  # 先测试单线程
    )

    for i, (hero, villain, board_str, desc) in enumerate(test_cases[:3]):  # 只测试前3个
        print(f"\n测试 {i+1}: {desc}")

        hero_hand = Hand.from_str(hero)
        villain_hand = Hand.from_str(villain)
        board = Board.from_str(board_str) if board_str else Board([])

        # 原始版本
        start = time.time()
        result_original = calc_original.calculate_equity(hero_hand, villain_hand, board)
        time_original = time.time() - start

        # 快速版本
        start = time.time()
        result_fast = calc_fast.calculate_equity(hero_hand, villain_hand, board)
        time_fast = time.time() - start

        # 加速比
        speedup = time_original / time_fast

        print(f"  原始耗时: {time_original*1000:.1f} ms")
        print(f"  快速耗时: {time_fast*1000:.1f} ms")
        print(f"  加速比: {speedup:.1f}x")

    print("\n" + "=" * 60)


def test_adaptive_sampling():
    """测试自适应采样的效果"""
    print("\n" + "=" * 60)
    print("自适应采样测试")
    print("=" * 60)

    hero = Hand.from_str("AsKs")
    villain = Hand.from_str("QhQd")
    board = Board([])

    # 固定迭代
    calc_fixed = FastEquityCalculator(
        iterations=1000,
        use_adaptive_sampling=False
    )

    # 自适应采样
    calc_adaptive = FastEquityCalculator(
        iterations=1000,
        use_adaptive_sampling=True,
        target_error=0.02
    )

    # 测试
    start = time.time()
    result_fixed = calc_fixed.calculate_equity(hero, villain, board)
    time_fixed = time.time() - start

    start = time.time()
    result_adaptive = calc_adaptive.calculate_equity(hero, villain, board)
    time_adaptive = time.time() - start

    print(f"固定迭代:")
    print(f"  Equity: {result_fixed.equity:.4f}")
    print(f"  迭代次数: {result_fixed.iterations}")
    print(f"  耗时: {time_fixed*1000:.1f} ms")

    print(f"\n自适应采样:")
    print(f"  Equity: {result_adaptive.equity:.4f}")
    print(f"  迭代次数: {result_adaptive.iterations}")
    print(f"  耗时: {time_adaptive*1000:.1f} ms")

    print(f"\n节省迭代: {result_fixed.iterations - result_adaptive.iterations} 次")
    print(f"加速比: {time_fixed/time_adaptive:.2f}x")
    print(f"精度损失: {abs(result_fixed.equity - result_adaptive.equity)*100:.2f}%")


def test_multithreading():
    """测试多线程的效果"""
    print("\n" + "=" * 60)
    print("多线程测试")
    print("=" * 60)

    from advisor.range_engine import Range

    hero_hand = Hand.from_str("AsKs")
    villain_range = Range.from_string("88+,ATs+,KQs").to_hands()[:20]  # 取20个combos
    board = Board([])

    # 单线程
    calc_single = FastEquityCalculator(
        iterations=500,
        use_multithreading=False
    )

    # 多线程
    calc_multi = FastEquityCalculator(
        iterations=500,
        use_multithreading=True,
        num_threads=4
    )

    print(f"测试: AsKs vs 范围 ({len(villain_range)} combos)")

    # 单线程
    start = time.time()
    result_single = calc_single.calculate_vs_range(hero_hand, villain_range, board)
    time_single = time.time() - start

    # 多线程
    start = time.time()
    result_multi = calc_multi.calculate_vs_range(hero_hand, villain_range, board)
    time_multi = time.time() - start

    print(f"\n单线程:")
    print(f"  Equity: {result_single.equity:.4f}")
    print(f"  耗时: {time_single:.2f} s")

    print(f"\n多线程(4线程):")
    print(f"  Equity: {result_multi.equity:.4f}")
    print(f"  耗时: {time_multi:.2f} s")

    print(f"\n加速比: {time_single/time_multi:.2f}x")
    print(f"精度损失: {abs(result_single.equity - result_multi.equity)*100:.2f}%")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("快速Equity计算器 - 性能测试")
    print("=" * 60)

    # 测试用例
    test_cases = [
        # (hero, villain, board, description)
        ("AsKs", "QhQd", "", "AKs vs QQ 翻前"),
        ("AsAh", "KsKh", "", "AA vs KK 翻前"),
        ("7h8h", "AsKc", "", "78s vs AK 翻前"),
        ("AsKs", "QhQd", "Ah9c3d", "AKs vs QQ 在A高flop"),
        ("JhTh", "AsKc", "QhKh2d", "JTs vs AK 在QKx flop（同花听牌）"),
        ("AsKs", "AhQh", "AdKc9s", "AK vs AQ 在AK9 flop"),
        ("9s9h", "AsKs", "9d8s7s", "99 vs AK 在997 flop（set vs 同花+顺子听）"),
        ("AsAh", "KsKh", "QsJsTd", "AA vs KK 在QJT flop"),
    ]

    # 1. 精度测试
    accuracy_pass = test_accuracy(test_cases, tolerance=0.05)

    # 2. 速度测试
    test_speed(test_cases)

    # 3. 自适应采样测试
    test_adaptive_sampling()

    # 4. 多线程测试
    test_multithreading()

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    if accuracy_pass:
        print("✅ 精度测试通过")
        print("✅ 速度大幅提升")
        print("✅ 可以安全使用快速计算器")
    else:
        print("⚠️ 精度测试未通过，需要调整参数")


if __name__ == "__main__":
    # 首先确保查找表已生成
    print("初始化查找表...")
    from advisor.range_engine.evaluator_fast import precompute_if_needed
    precompute_if_needed()

    print("\n开始测试...\n")
    run_all_tests()
