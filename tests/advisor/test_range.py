#!/usr/bin/env python
"""
Range引擎单元测试

测试:
1. HandCombo创建和比较
2. Range创建和操作
3. RangeGenerator (组合生成)
4. RangeParser (表达式解析)
5. Range vs Range equity
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import unittest

from poker_core import (
    Card, Hand, Board, Rank,
    HandCombo, Range, RangeGenerator, RangeParser,
    EquityCalculator,
    create_premium_range, create_any_pair_range,
)


class TestHandCombo(unittest.TestCase):
    """测试HandCombo类"""

    def test_create_combo(self):
        """测试创建组合"""
        combo = HandCombo(Hand.from_str("AsKs"))
        self.assertIsNotNone(combo)
        self.assertEqual(str(combo), "AsKs")

    def test_combo_from_str(self):
        """测试从字符串创建"""
        combo = HandCombo.from_str("AsKs")
        self.assertEqual(str(combo), "AsKs")

    def test_combo_equality(self):
        """测试组合相等性"""
        combo1 = HandCombo.from_str("AsKs")
        combo2 = HandCombo.from_str("AsKs")
        combo3 = HandCombo.from_str("AhKh")

        self.assertEqual(combo1, combo2)
        self.assertNotEqual(combo1, combo3)

    def test_combo_hash(self):
        """测试组合可哈希"""
        combo1 = HandCombo.from_str("AsKs")
        combo2 = HandCombo.from_str("AsKs")

        combo_set = {combo1, combo2}
        self.assertEqual(len(combo_set), 1)


class TestRangeGenerator(unittest.TestCase):
    """测试RangeGenerator"""

    def test_generate_pair_combos(self):
        """测试生成对子组合"""
        combos = RangeGenerator.generate_from_notation("AA")

        # AA有6种组合
        self.assertEqual(len(combos), 6)

        # 所有组合都是AA
        for combo in combos:
            self.assertTrue(combo.hand.is_pocket_pair())
            self.assertEqual(combo.hand.cards[0].rank, Rank.ACE)

    def test_generate_suited_combos(self):
        """测试生成同花组合"""
        combos = RangeGenerator.generate_from_notation("AKs")

        # AKs有4种组合 (每种花色)
        self.assertEqual(len(combos), 4)

        # 所有组合都是同花
        for combo in combos:
            self.assertTrue(combo.hand.is_suited())

    def test_generate_offsuit_combos(self):
        """测试生成非同花组合"""
        combos = RangeGenerator.generate_from_notation("AKo")

        # AKo有12种组合
        self.assertEqual(len(combos), 12)

        # 所有组合都是非同花
        for combo in combos:
            self.assertFalse(combo.hand.is_suited())

    def test_generate_all_combos(self):
        """测试生成所有组合 (无s/o后缀)"""
        combos = RangeGenerator.generate_from_notation("AK")

        # AK有16种组合 (4同花 + 12非同花)
        self.assertEqual(len(combos), 16)


class TestRange(unittest.TestCase):
    """测试Range类"""

    def test_create_empty_range(self):
        """测试创建空range"""
        r = Range()
        self.assertEqual(len(r), 0)

    def test_from_hand_notation(self):
        """测试从手牌符号创建range"""
        r = Range.from_hand_notation("AA")
        self.assertEqual(len(r), 6)

        r2 = Range.from_hand_notation("AKs")
        self.assertEqual(len(r2), 4)

    def test_add_combo(self):
        """测试添加组合"""
        r = Range()
        r.add(HandCombo.from_str("AsKs"))
        self.assertEqual(len(r), 1)

    def test_remove_dead_cards(self):
        """测试移除死牌"""
        r = Range.from_hand_notation("AA")
        self.assertEqual(len(r), 6)

        # 移除As作为死牌
        dead_cards = {Card.from_str("As")}
        r_filtered = r.remove_dead_cards(dead_cards)

        # 应该剩下3种组合 (不包含As的)
        self.assertEqual(len(r_filtered), 3)

    def test_to_hands(self):
        """测试转换为Hand列表"""
        r = Range.from_hand_notation("AA")
        hands = r.to_hands()

        self.assertEqual(len(hands), 6)
        self.assertIsInstance(hands[0], Hand)


class TestRangeParser(unittest.TestCase):
    """测试RangeParser"""

    def test_parse_single_notation(self):
        """测试解析单个符号"""
        r = RangeParser.parse("AA")
        self.assertEqual(len(r), 6)

    def test_parse_multiple_notations(self):
        """测试解析多个符号"""
        r = RangeParser.parse("AA,KK")

        # AA(6) + KK(6) = 12
        self.assertEqual(len(r), 12)

    def test_parse_plus_pairs(self):
        """测试解析对子+符号"""
        r = RangeParser.parse("QQ+")

        # QQ, KK, AA = 6 + 6 + 6 = 18
        self.assertEqual(len(r), 18)

    def test_parse_plus_suited(self):
        """测试解析同花+符号"""
        r = RangeParser.parse("ATs+")

        # ATs, AJs, AQs, AKs = 4 + 4 + 4 + 4 = 16
        self.assertEqual(len(r), 16)

    def test_parse_range(self):
        """测试解析范围符号"""
        r = RangeParser.parse("88-TT")

        # 88, 99, TT = 6 + 6 + 6 = 18
        self.assertEqual(len(r), 18)

    def test_parse_complex_expression(self):
        """测试解析复杂表达式"""
        r = RangeParser.parse("QQ+,AK")

        # QQ(6) + KK(6) + AA(6) + AK(16) = 34
        self.assertEqual(len(r), 34)


class TestPremiumRanges(unittest.TestCase):
    """测试预定义range"""

    def test_premium_range(self):
        """测试premium range"""
        r = create_premium_range()

        # QQ+, AK = 18 + 16 = 34
        self.assertEqual(len(r), 34)

    def test_any_pair_range(self):
        """测试所有对子range"""
        r = create_any_pair_range()

        # 13个对子 * 6种组合 = 78
        self.assertEqual(len(r), 78)


class TestRangeVsRangeEquity(unittest.TestCase):
    """测试Range vs Range equity计算"""

    def test_aa_vs_small_pairs(self):
        """测试AA vs 小对子range"""
        calc = EquityCalculator(iterations=2000)

        hero_range = Range.from_string("AA")
        villain_range = Range.from_string("22-66")

        # 使用采样 (因为组合太多)
        result = calc.calculate_range_vs_range(
            hero_range,
            villain_range,
            Board([]),
            sample_size=20
        )

        # AA vs 小对子应该有约80% equity (考虑采样方差)
        self.assertGreater(result.equity, 0.60)
        self.assertLess(result.equity, 0.95)

    def test_premium_vs_premium(self):
        """测试premium vs premium"""
        calc = EquityCalculator(iterations=2000)

        hero_range = Range.from_string("QQ+")
        villain_range = Range.from_string("AK")

        result = calc.calculate_range_vs_range(
            hero_range,
            villain_range,
            Board([]),
            sample_size=30
        )

        # QQ+ vs AK应该有约优势，但AK也有不错的equity
        # 考虑采样方差，阈值放宽
        self.assertGreater(result.equity, 0.40)
        self.assertLess(result.equity, 0.70)


class TestRangeEdgeCases(unittest.TestCase):
    """测试Range边界情况"""

    def test_empty_range_after_dead_cards(self):
        """测试移除死牌后空range"""
        r = Range.from_string("AA")

        # 移除AA的所有牌
        dead_cards = {
            Card.from_str("As"),
            Card.from_str("Ah"),
            Card.from_str("Ad"),
            Card.from_str("Ac"),
        }

        r_filtered = r.remove_dead_cards(dead_cards)

        # 应该没有剩余组合
        self.assertEqual(len(r_filtered), 0)

    def test_overlapping_hands(self):
        """测试重叠手牌"""
        r = Range.from_string("AA,AA")

        # 重复添加AA，应该只有6种组合 (set自动去重)
        self.assertEqual(len(r), 6)


def run_tests():
    """运行所有测试"""
    suite = unittest.TestSuite()

    # 添加所有测试类
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestHandCombo))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestRangeGenerator))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestRange))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestRangeParser))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestPremiumRanges))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestRangeVsRangeEquity))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestRangeEdgeCases))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
