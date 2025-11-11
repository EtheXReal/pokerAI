#!/usr/bin/env python
"""
测试 Hand vs Range Equity 计算

验证功能:
- Hand vs Range equity计算
- 死牌移除
- 边缘情况处理
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import unittest
from advisor.equity import Hand, Board, Range, EquityCalculator


class TestHandVsRange(unittest.TestCase):
    """测试Hand vs Range equity计算"""

    def setUp(self):
        self.calc = EquityCalculator(iterations=5000)

    def test_ak_vs_pocket_pairs(self):
        """测试 AK vs 中小口袋对范围"""
        hero = Hand.from_str("AsKh")
        villain_range = Range.from_string("77,88,99")
        board = Board.from_str("")

        # 转换为hands列表
        villain_hands = villain_range.to_hands()

        result = self.calc.calculate_vs_range(hero, villain_hands, board)

        # AK vs 中小口袋对，翻前约46% equity
        self.assertGreater(result.equity, 0.40, "AK vs 77-99 should have >40% equity")
        self.assertLess(result.equity, 0.52, "AK vs 77-99 should have <52% equity")

        print(f"\nAK vs 77,88,99 (翻前): {result.equity:.1%}")

    def test_aa_vs_broadway(self):
        """测试 AA vs Broadway范围"""
        hero = Hand.from_str("AsAh")
        villain_range = Range.from_string("AKs,AQs,KQs")
        board = Board.from_str("")

        villain_hands = villain_range.to_hands()
        result = self.calc.calculate_vs_range(hero, villain_hands, board)

        # AA vs broadway hands，翻前约80%+ equity
        self.assertGreater(result.equity, 0.75, "AA vs broadway should have >75% equity")
        self.assertLess(result.equity, 0.90, "AA vs broadway should have <90% equity")

        print(f"AA vs AKs,AQs,KQs (翻前): {result.equity:.1%}")

    def test_ak_vs_range_on_ace_high_board(self):
        """测试 AK vs 范围 (A高board)"""
        hero = Hand.from_str("AsKh")
        villain_range = Range.from_string("QQ,JJ,TT")
        board = Board.from_str("Ah9c3d")

        villain_hands = villain_range.to_hands()
        result = self.calc.calculate_vs_range(hero, villain_hands, board)

        # AK在A高board上领先中等对子，应该>80%
        self.assertGreater(result.equity, 0.75, "Top pair top kicker should dominate")

        print(f"AK vs QQ,JJ,TT on Ah9c3d: {result.equity:.1%}")

    def test_flush_draw_vs_made_hands(self):
        """测试 同花听牌 vs 成牌范围"""
        hero = Hand.from_str("AhKh")
        villain_range = Range.from_string("QQ,JJ")
        board = Board.from_str("Jh9h2c")

        villain_hands = villain_range.to_hands()
        result = self.calc.calculate_vs_range(hero, villain_hands, board)

        # 同花+overcards听牌 vs 中对，约40-50% equity
        self.assertGreater(result.equity, 0.30, "Flush draw + overcards should have >30%")
        self.assertLess(result.equity, 0.60, "Flush draw + overcards should have <60%")

        print(f"AhKh vs QQ,JJ on Jh9h2c: {result.equity:.1%}")

    def test_set_vs_draws(self):
        """测试 Set vs 听牌范围"""
        hero = Hand.from_str("9s9h")
        villain_range = Range.from_string("AKs")  # 所有AK同花
        board = Board.from_str("9d7h3c")

        villain_hands = villain_range.to_hands()
        result = self.calc.calculate_vs_range(hero, villain_hands, board)

        # Set vs overcards，应该>65%
        self.assertGreater(result.equity, 0.65, "Set should dominate overcards")

        print(f"99 set vs AKs on 9d7h3c: {result.equity:.1%}")

    def test_reduced_range_after_dead_cards(self):
        """测试 死牌移除后range缩减"""
        hero = Hand.from_str("AsAh")
        villain_range = Range.from_string("AA")  # 只有AA
        board = Board.from_str("")

        # 移除死牌
        dead_cards = set(hero.cards)
        villain_valid = villain_range.remove_dead_cards(dead_cards)
        villain_hands = villain_valid.to_hands()

        # AA有6种组合，hero拿了AsAh，villain只能有AcAd
        self.assertEqual(len(villain_hands), 1, "Should have only 1 valid AA combo (AcAd)")

    def test_overpair_vs_premium_range(self):
        """测试 超对 vs Premium范围"""
        hero = Hand.from_str("KsKh")
        villain_range = Range.from_string("QQ+,AK")
        board = Board.from_str("")

        villain_hands = villain_range.to_hands()
        result = self.calc.calculate_vs_range(hero, villain_hands, board)

        # KK vs (QQ+,AK) = KK vs (QQ,KK,AA,AK)
        # 对QQ很强，对KK平局，对AA弱，对AK约60%
        # 总体约45-55%
        self.assertGreater(result.equity, 0.35, "KK vs premium range")
        self.assertLess(result.equity, 0.65, "KK vs premium range")

        print(f"KK vs QQ+,AK (翻前): {result.equity:.1%}")

    def test_suited_connector_vs_pairs(self):
        """测试 同花连子 vs 对子范围"""
        hero = Hand.from_str("7s6s")
        villain_range = Range.from_string("88,99,TT")
        board = Board.from_str("")

        villain_hands = villain_range.to_hands()
        result = self.calc.calculate_vs_range(hero, villain_hands, board)

        # 同花连子 vs 中等对子，翻前约18-23%
        self.assertGreater(result.equity, 0.15, "Suited connector should have >15%")
        self.assertLess(result.equity, 0.28, "Suited connector should have <28%")

        print(f"7s6s vs 88,99,TT (翻前): {result.equity:.1%}")

    def test_range_with_plus_notation(self):
        """测试使用+符号的范围"""
        hero = Hand.from_str("AsKs")
        villain_range = Range.from_string("JJ+")  # JJ, QQ, KK, AA
        board = Board.from_str("")

        villain_hands = villain_range.to_hands()
        result = self.calc.calculate_vs_range(hero, villain_hands, board)

        # AK vs JJ+ 约43%
        self.assertGreater(result.equity, 0.35, "AKs vs JJ+ should have >35%")
        self.assertLess(result.equity, 0.50, "AKs vs JJ+ should have <50%")

        print(f"AKs vs JJ+ (翻前): {result.equity:.1%}")

    def test_hand_vs_wide_range(self):
        """测试 手牌 vs 宽范围"""
        hero = Hand.from_str("AdKd")
        villain_range = Range.from_string("77+,AJs+,KQs")
        board = Board.from_str("")

        villain_hands = villain_range.to_hands()
        result = self.calc.calculate_vs_range(hero, villain_hands, board)

        # AK vs 较宽范围应该>50%
        self.assertGreater(result.equity, 0.45, "AK vs wide range should have >45%")
        self.assertLess(result.equity, 0.65, "AK vs wide range should have <65%")

        print(f"AK vs 77+,AJs+,KQs (翻前): {result.equity:.1%}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
