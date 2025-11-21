#!/usr/bin/env python
"""
简单验证bet/raise金额规范化

直接测试round_bet_amount函数和检查实际游戏中的金额格式
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from poker_env.utils import round_bet_amount


def test_round_function():
    """测试round_bet_amount函数的关键用例"""
    print("="*80)
    print("测试：round_bet_amount函数")
    print("="*80)

    # 用户报告的问题金额
    problem_cases = [
        (19.97, 20.0, "19.97BB -> 20.0BB"),
        (1.32, 1.0, "1.32BB -> 1.0BB"),
        (9.35, 9.0, "9.35BB -> 9.0BB"),
        (32.88, 33.0, "32.88BB -> 33.0BB"),
        (23.50, 24.0, "23.50BB -> 24.0BB (不允许0.5)"),
    ]

    print("\n关键测试用例（来自用户报告的问题）：")
    all_passed = True
    for input_val, expected, description in problem_cases:
        result = round_bet_amount(input_val)
        passed = abs(result - expected) < 0.01
        status = "✅" if passed else "❌"
        print(f"  {status} {description}: 结果 {result:.2f}BB")
        if not passed:
            all_passed = False

    # 额外的边界用例
    additional_cases = [
        (0.24, 0.0, "0.24BB -> 0.0BB"),
        (0.49, 0.0, "0.49BB -> 0.0BB"),
        (0.50, 0.0, "0.50BB -> 0.0BB (banker's rounding，实际被MIN_BET拦截)"),
        (0.51, 1.0, "0.51BB -> 1.0BB"),
        (1.0, 1.0, "1.0BB -> 1.0BB"),
        (1.24, 1.0, "1.24BB -> 1.0BB"),
        (1.49, 1.0, "1.49BB -> 1.0BB"),
        (1.50, 2.0, "1.50BB -> 2.0BB"),
        (1.51, 2.0, "1.51BB -> 2.0BB"),
        (1.74, 2.0, "1.74BB -> 2.0BB"),
        (2.0, 2.0, "2.0BB -> 2.0BB"),
        (23.50, 24.0, "23.50BB -> 24.0BB"),
        (100.13, 100.0, "100.13BB -> 100.0BB"),
        (100.49, 100.0, "100.49BB -> 100.0BB"),
        (100.50, 100.0, "100.50BB -> 100.0BB (banker's rounding)"),
        (100.51, 101.0, "100.51BB -> 101.0BB"),
    ]

    print("\n额外的边界用例：")
    for input_val, expected, description in additional_cases:
        result = round_bet_amount(input_val)
        passed = abs(result - expected) < 0.01
        status = "✅" if passed else "❌"
        print(f"  {status} {description}: 结果 {result:.2f}BB")
        if not passed:
            all_passed = False

    print("\n" + "="*80)
    if all_passed:
        print("✅ 所有测试通过！round_bet_amount函数工作正常")
        print("="*80)
        print("\n规范化规则：")
        print("  - 所有bet/raise金额都会被规范化到整数BB")
        print("  - 例如：1.32BB -> 1.0BB, 9.35BB -> 9.0BB, 23.50BB -> 24.0BB")
        print("  - 允许的金额：1, 2, 3, 4, 5, ... (只允许整数BB)")
        print("  - 不允许：0.5BB, 1.5BB, 2.5BB等任何带小数的金额")
        print("  - 例外：小盲注可以是0.5BB（强制盲注），call可以是任意金额")
    else:
        print("❌ 部分测试失败")
    print("="*80)


def verify_no_weird_decimals():
    """验证规范化后都是整数"""
    print("\n" + "="*80)
    print("验证：所有bet/raise金额都是整数BB")
    print("="*80)

    # 生成100个随机金额，验证规范化后都是整数
    import random
    random.seed(42)

    all_valid = True
    weird_decimals_found = []

    print("\n测试100个随机金额的规范化：")
    for i in range(100):
        amount = random.uniform(0.1, 100.0)
        normalized = round_bet_amount(amount)

        # 检查是否是整数
        is_valid = abs(normalized - round(normalized)) < 0.01

        if not is_valid:
            all_valid = False
            weird_decimals_found.append((amount, normalized))
            print(f"  ❌ {amount:.4f}BB -> {normalized:.4f}BB (不是整数！)")

    if all_valid:
        print(f"  ✅ 所有100个随机金额都正确规范化到整数BB")
    else:
        print(f"  ❌ 发现{len(weird_decimals_found)}个无效的规范化结果：")
        for original, normalized in weird_decimals_found:
            print(f"     {original:.4f}BB -> {normalized:.4f}BB")

    print("="*80)


if __name__ == '__main__':
    test_round_function()
    verify_no_weird_decimals()
