#!/usr/bin/env python
"""
测试 Multiway Equity 计算 (多人底池)

验证功能:
- 3人底池equity计算
- 4人底池equity计算
- Equity下降规律验证
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import unittest
from poker_core import Hand, Board, Range, EquityCalculator


class TestMultiwayEquity(unittest.TestCase):
    """测试Multiway equity计算"""

    def setUp(self):
        self.calc = EquityCalculator(iterations=2000)

    def test_aa_3way(self):
        """测试 AA在3人底池的equity"""
        hero = Hand.from_str("AsAh")
        v1_range = Range.from_string("KK,QQ")
        v2_range = Range.from_string("JJ,TT")
        board = Board.from_str("")

        result = self.calc.calculate_multiway(
            hero,
            [v1_range, v2_range],
            board,
            sample_size=50
        )

        # AA在heads-up约82%，3人约60-70%
        self.assertGreater(result.equity, 0.55, "AA in 3-way should have >55% equity")
        self.assertLess(result.equity, 0.75, "AA in 3-way should have <75% equity")

        print(f"\nAA vs [KK,QQ] vs [JJ,TT] (3-way): {result.equity:.1%}")

    def test_aa_4way(self):
        """测试 AA在4人底池的equity"""
        hero = Hand.from_str("AsAh")
        v1_range = Range.from_string("KK")
        v2_range = Range.from_string("QQ")
        v3_range = Range.from_string("JJ")
        board = Board.from_str("")

        result = self.calc.calculate_multiway(
            hero,
            [v1_range, v2_range, v3_range],
            board,
            sample_size=50
        )

        # AA在4人底池约50-65%
        self.assertGreater(result.equity, 0.45, "AA in 4-way should have >45% equity")
        self.assertLess(result.equity, 0.70, "AA in 4-way should have <70% equity")

        print(f"AA vs KK vs QQ vs JJ (4-way): {result.equity:.1%}")

    def test_equity_decreases_with_more_players(self):
        """测试equity随玩家数量递减"""
        hero = Hand.from_str("AsAh")
        board = Board.from_str("")

        # 2人底池 (heads-up)
        result_2way = self.calc.calculate_equity(
            hero,
            Hand.from_str("KsKh"),
            board,
            iterations=2000
        )

        # 3人底池
        result_3way = self.calc.calculate_multiway(
            hero,
            [Range.from_string("KK"), Range.from_string("QQ")],
            board,
            sample_size=30
        )

        # 4人底池
        result_4way = self.calc.calculate_multiway(
            hero,
            [Range.from_string("KK"), Range.from_string("QQ"), Range.from_string("JJ")],
            board,
            sample_size=30
        )

        print(f"\nAA equity decline:")
        print(f"  Heads-up (vs KK): {result_2way.equity:.1%}")
        print(f"  3-way (vs KK,QQ): {result_3way.equity:.1%}")
        print(f"  4-way (vs KK,QQ,JJ): {result_4way.equity:.1%}")

        # 验证递减趋势
        self.assertGreater(result_2way.equity, result_3way.equity,
                          "Equity should decrease in 3-way")
        self.assertGreater(result_3way.equity, result_4way.equity,
                          "Equity should decrease in 4-way")

    def test_multiway_with_board(self):
        """测试有公共牌的多人底池"""
        hero = Hand.from_str("AsKh")
        v1_range = Range.from_string("QQ,JJ")
        v2_range = Range.from_string("AQs,AJs")
        board = Board.from_str("Ah9c3d")  # A高board

        result = self.calc.calculate_multiway(
            hero,
            [v1_range, v2_range],
            board,
            sample_size=50
        )

        # Top pair top kicker应该有优势
        self.assertGreater(result.equity, 0.50, "TPTK should have >50% equity")

        print(f"\nAK vs [QQ,JJ] vs [AQs,AJs] on Ah9c3d (3-way): {result.equity:.1%}")

    def test_pocket_pairs_multiway(self):
        """测试中等对子在多人底池的equity"""
        hero = Hand.from_str("9s9h")
        v1_range = Range.from_string("AKs,AQs")
        v2_range = Range.from_string("KQs,QJs")
        board = Board.from_str("")

        result = self.calc.calculate_multiway(
            hero,
            [v1_range, v2_range],
            board,
            sample_size=50
        )

        # 中等对子vs多个overcards约40-60%
        self.assertGreater(result.equity, 0.30, "99 should have >30% equity")
        self.assertLess(result.equity, 0.70, "99 should have <70% equity")

        print(f"99 vs [AKs,AQs] vs [KQs,QJs] (3-way): {result.equity:.1%}")

    def test_suited_connectors_multiway(self):
        """测试同花连子在多人底池"""
        hero = Hand.from_str("8s7s")
        v1_range = Range.from_string("AA,KK")
        v2_range = Range.from_string("AKo")
        board = Board.from_str("")

        result = self.calc.calculate_multiway(
            hero,
            [v1_range, v2_range],
            board,
            sample_size=50
        )

        # 同花连子vs强牌约15-30%
        self.assertGreater(result.equity, 0.10, "87s should have >10% equity")
        self.assertLess(result.equity, 0.40, "87s should have <40% equity")

        print(f"8s7s vs [AA,KK] vs [AKo] (3-way): {result.equity:.1%}")

    def test_error_handling_single_range(self):
        """测试错误处理: 只有一个范围"""
        hero = Hand.from_str("AsAh")
        v1_range = Range.from_string("KK")

        with self.assertRaises(ValueError) as context:
            self.calc.calculate_multiway(hero, [v1_range], Board.from_str(""))

        self.assertIn("at least 2", str(context.exception))

        print("\nError handling: Single range correctly rejected")

    def test_strong_hand_multiway(self):
        """测试强牌在多人底池"""
        hero = Hand.from_str("AsKs")
        v1_range = Range.from_string("QQ,JJ")
        v2_range = Range.from_string("AQ,KQ")
        board = Board.from_str("Ah9c3d")  # A high board

        result = self.calc.calculate_multiway(
            hero,
            [v1_range, v2_range],
            board,
            sample_size=50
        )

        # TPTK在多人底池应该有优势
        self.assertGreater(result.equity, 0.50, "TPTK should have >50% equity")

        print(f"AK on A high board (3-way): {result.equity:.1%}")

    def test_dominated_hand_multiway(self):
        """测试被压制的手牌在多人底池"""
        hero = Hand.from_str("AhJh")
        v1_range = Range.from_string("AA,AK")
        v2_range = Range.from_string("KK,QQ")
        board = Board.from_str("Ac9c3d")  # A on board

        result = self.calc.calculate_multiway(
            hero,
            [v1_range, v2_range],
            board,
            sample_size=50
        )

        # AJ被AA,AK压制，equity应该很低
        self.assertLess(result.equity, 0.35, "Dominated hand should have <35% equity")

        print(f"AJ vs [AA,AK] vs [KK,QQ] on Ac9c3d (dominated): {result.equity:.1%}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
