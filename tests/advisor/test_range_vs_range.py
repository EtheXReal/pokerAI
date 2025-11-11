#!/usr/bin/env python
"""
测试 Range vs Range Equity 计算

验证功能:
- Range vs Range equity计算
- 采样策略
- 复杂范围对抗
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import unittest
from advisor.range_engine import Hand, Board, Range, EquityCalculator


class TestRangeVsRange(unittest.TestCase):
    """测试Range vs Range equity计算"""

    def setUp(self):
        self.calc = EquityCalculator(iterations=3000)

    def test_premium_vs_medium_pairs(self):
        """测试 Premium范围 vs 中等对子"""
        hero_range = Range.from_string("AA,KK")
        villain_range = Range.from_string("QQ,JJ,TT")
        board = Board.from_str("")

        result = self.calc.calculate_range_vs_range(hero_range, villain_range, board)

        # AA,KK vs QQ,JJ,TT 应该>75%
        self.assertGreater(result.equity, 0.70, "Premium pairs should dominate")
        self.assertLess(result.equity, 0.90, "Should not be 100%")

        print(f"\nAA,KK vs QQ,JJ,TT (翻前): {result.equity:.1%}")

    def test_broadways_vs_pairs(self):
        """测试 Broadway范围 vs 对子范围"""
        hero_range = Range.from_string("AKs,AQs,KQs")
        villain_range = Range.from_string("77,88,99")
        board = Board.from_str("")

        result = self.calc.calculate_range_vs_range(hero_range, villain_range, board)

        # Broadway vs 小对子约45-55%
        self.assertGreater(result.equity, 0.35, "Broadway vs small pairs")
        self.assertLess(result.equity, 0.60, "Broadway vs small pairs")

        print(f"AKs,AQs,KQs vs 77,88,99 (翻前): {result.equity:.1%}")

    def test_value_vs_value(self):
        """测试 Value范围 vs Value范围"""
        hero_range = Range.from_string("QQ+,AK")
        villain_range = Range.from_string("JJ+,AKs")
        board = Board.from_str("")

        result = self.calc.calculate_range_vs_range(hero_range, villain_range, board)

        # QQ+,AK vs JJ+,AKs 应该约55-60%
        self.assertGreater(result.equity, 0.50, "Stronger value range should lead")
        self.assertLess(result.equity, 0.70, "But not dominating")

        print(f"QQ+,AK vs JJ+,AKs (翻前): {result.equity:.1%}")

    def test_plus_notation_ranges(self):
        """测试使用+符号的范围对抗"""
        hero_range = Range.from_string("88+")
        villain_range = Range.from_string("22+")
        board = Board.from_str("")

        # 使用采样以加快速度
        result = self.calc.calculate_range_vs_range(
            hero_range,
            villain_range,
            board,
            sample_size=100
        )

        # 88+ vs 22+ 应该>60% (因为88+更强)
        self.assertGreater(result.equity, 0.55, "Higher pairs should win")

        print(f"88+ vs 22+ (翻前, sampled): {result.equity:.1%}")

    def test_polarized_vs_linear(self):
        """测试 极化范围 vs 线性范围"""
        hero_range = Range.from_string("AA,KK,AKs")  # 极化 (顶端价值)
        villain_range = Range.from_string("QQ,JJ,TT,AQs,KQs")  # 线性 (中等价值)
        board = Board.from_str("")

        result = self.calc.calculate_range_vs_range(hero_range, villain_range, board)

        # 极化范围应该领先
        self.assertGreater(result.equity, 0.60, "Polarized range should lead")

        print(f"AA,KK,AKs vs QQ,JJ,TT,AQs,KQs (翻前): {result.equity:.1%}")

    def test_range_vs_range_on_board(self):
        """测试 有公共牌的Range vs Range"""
        hero_range = Range.from_string("AK,AQ,AJ")
        villain_range = Range.from_string("QQ,JJ,TT")
        board = Board.from_str("Ah9c3d")  # A高board

        result = self.calc.calculate_range_vs_range(hero_range, villain_range, board)

        # A高board，Ax范围应该大幅领先对子
        self.assertGreater(result.equity, 0.65, "Top pair range should dominate")

        print(f"AK,AQ,AJ vs QQ,JJ,TT on Ah9c3d: {result.equity:.1%}")

    def test_small_ranges(self):
        """测试 小范围对抗 (全计算，无采样)"""
        hero_range = Range.from_string("AA")
        villain_range = Range.from_string("KK")
        board = Board.from_str("")

        result = self.calc.calculate_range_vs_range(hero_range, villain_range, board)

        # AA vs KK 约82%
        self.assertGreater(result.equity, 0.78, "AA vs KK should be ~82%")
        self.assertLess(result.equity, 0.86, "AA vs KK should be ~82%")

        print(f"AA vs KK (翻前): {result.equity:.1%}")

    def test_suited_vs_offsuit(self):
        """测试 同花范围 vs 非同花范围"""
        hero_range = Range.from_string("AKs,AQs,AJs")
        villain_range = Range.from_string("AKo,AQo,AJo")
        board = Board.from_str("")

        result = self.calc.calculate_range_vs_range(hero_range, villain_range, board)

        # 同花应该略好于非同花（约52-55%）
        self.assertGreater(result.equity, 0.50, "Suited should be slightly better")
        self.assertLess(result.equity, 0.58, "But not huge difference")

        print(f"AKs,AQs,AJs vs AKo,AQo,AJo (翻前): {result.equity:.1%}")

    def test_sampling_consistency(self):
        """测试采样的一致性"""
        hero_range = Range.from_string("QQ+")
        villain_range = Range.from_string("77-JJ")
        board = Board.from_str("")

        # 多次采样，结果应该相似
        results = []
        for _ in range(3):
            result = self.calc.calculate_range_vs_range(
                hero_range,
                villain_range,
                board,
                sample_size=50
            )
            results.append(result.equity)

        # 检查方差不应该太大
        avg = sum(results) / len(results)
        variance = sum((r - avg) ** 2 for r in results) / len(results)
        std_dev = variance ** 0.5

        self.assertLess(std_dev, 0.05, "Sampling should be consistent")

        print(f"QQ+ vs 77-JJ (采样一致性): avg={avg:.1%}, std={std_dev:.3f}")

    def test_overlapping_ranges(self):
        """测试 有重叠的范围"""
        hero_range = Range.from_string("QQ+,AK")
        villain_range = Range.from_string("JJ+,AK")
        board = Board.from_str("")

        # 包含重叠（都有KK,AA,AK）
        result = self.calc.calculate_range_vs_range(hero_range, villain_range, board)

        # 应该能正确处理重叠（移除冲突组合）
        self.assertGreater(result.equity, 0.45, "Should handle overlaps")
        self.assertLess(result.equity, 0.65, "Should handle overlaps")

        print(f"QQ+,AK vs JJ+,AK (有重叠): {result.equity:.1%}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
