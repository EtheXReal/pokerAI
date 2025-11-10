#!/usr/bin/env python
"""
Range Engine 单元测试

测试:
1. Range解析和基础操作
2. Equity计算准确性
3. Board Texture分析
4. Preflop范围表正确性
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import unittest
from treys import Card
from advisor.range_engine import (
    Range,
    parse_range_dict,
    EquityCalculator,
    BoardTexture,
    get_open_range,
)


class TestRange(unittest.TestCase):
    """测试Range类"""

    def test_pair_parsing(self):
        """测试口袋对解析"""
        r = Range("AA")
        self.assertEqual(r.size(), 6, "AA应该有6个combo")

        r2 = Range("77+")
        self.assertEqual(r2.size(), 48, "77+应该有48个combo (8种对*6)")

    def test_suited_parsing(self):
        """测试同花解析"""
        r = Range("AKs")
        self.assertEqual(r.size(), 4, "AKs应该有4个combo")

        r2 = Range("A5s+")
        # A5s, A6s, A7s, A8s, A9s, ATs, AJs, AQs, AKs = 9种 * 4花色 = 36
        self.assertEqual(r2.size(), 36, "A5s+应该有36个combo")

    def test_offsuit_parsing(self):
        """测试非同花解析"""
        r = Range("AKo")
        self.assertEqual(r.size(), 12, "AKo应该有12个combo")

        r2 = Range("ATo+")
        # ATo, AJo, AQo, AKo = 4种 * 12 = 48
        self.assertEqual(r2.size(), 48, "ATo+应该有48个combo")

    def test_combined_range(self):
        """测试组合范围"""
        r = Range("AA,KK,AKs")
        # 6 + 6 + 4 = 16
        self.assertEqual(r.size(), 16)

    def test_dead_cards_removal(self):
        """测试死牌移除"""
        r = Range("AA,KK")
        self.assertEqual(r.size(), 12)

        r.remove_dead_cards(["As", "Kd"])
        # AA少3个 (包含As的), KK少3个 (包含Kd的)
        # AA: 6-3=3, KK: 6-3=3, 总计6
        self.assertEqual(r.size(), 6)

    def test_set_operations(self):
        """测试集合操作"""
        r1 = Range("AA,KK,QQ")
        r2 = Range("QQ,JJ,TT")

        # 交集
        inter = r1.intersect(r2)
        self.assertEqual(inter.size(), 6, "交集应该只有QQ (6个combo)")

        # 并集
        union = r1.union(r2)
        self.assertEqual(union.size(), 30, "并集应该有5种对 (30个combo)")

        # 差集
        diff = r1.subtract(r2)
        self.assertEqual(diff.size(), 12, "差集应该是AA+KK (12个combo)")


class TestEquityCalculator(unittest.TestCase):
    """测试Equity计算"""

    def setUp(self):
        self.calc = EquityCalculator()

    def test_hand_vs_range_dominated(self):
        """测试明显占优的情况"""
        hero = [Card.new('As'), Card.new('Ah')]
        villain_range = Range("KK,QQ")
        board = []

        equity = self.calc.hand_vs_range(hero, villain_range, board, nsamples=500)

        # AA vs KK/QQ翻前应该 ~82% equity
        self.assertGreater(equity, 0.75, "AA应该明显领先KK/QQ")
        self.assertLess(equity, 0.90)

    def test_range_vs_range(self):
        """测试范围vs范围"""
        hero_range = Range("AA,KK")
        villain_range = Range("QQ,JJ")
        board = []

        equity = self.calc.range_vs_range(hero_range, villain_range, board, nsamples=500)

        # AA/KK vs QQ/JJ应该 ~80%+
        self.assertGreater(equity, 0.75)

    def test_multiway_equity_decrease(self):
        """测试多人底池equity下降"""
        hero = [Card.new('As'), Card.new('Ah')]
        v1 = Range("KK")
        v2 = Range("QQ")
        board = []

        # 单挑 vs KK
        eq_hu = self.calc.hand_vs_range(hero, v1, board, nsamples=300)

        # 3人 vs KK + QQ
        eq_3way = self.calc.multiway_equity(hero, [v1, v2], board, nsamples=300)

        # 多人底池equity应该下降
        self.assertLess(eq_3way, eq_hu, "多人底池equity应该降低")


class TestBoardTexture(unittest.TestCase):
    """测试公共牌结构分析"""

    def test_dry_board(self):
        """测试干燥面"""
        board = [Card.new('As'), Card.new('7h'), Card.new('2d')]
        texture = BoardTexture(board)

        # A72彩虹面应该是dry或medium都可以接受
        self.assertIn(texture.wetness, ['dry', 'medium'])
        self.assertFalse(texture.flush_draw_possible)
        # 高牌面应该有利于raiser或neutral
        self.assertIn(texture.favors_caller_or_raiser(), ['raiser', 'neutral'])

    def test_wet_board(self):
        """测试湿润面"""
        board = [Card.new('Ts'), Card.new('9s'), Card.new('8h')]
        texture = BoardTexture(board)

        self.assertIn(texture.wetness, ['wet', 'medium'])
        self.assertTrue(texture.flush_draw_possible)
        self.assertTrue(texture.straight_draw_possible)

    def test_paired_board(self):
        """测试对子面"""
        board = [Card.new('Kc'), Card.new('Kh'), Card.new('3d')]
        texture = BoardTexture(board)

        self.assertTrue(texture.has_pair)
        self.assertFalse(texture.has_trips)

    def test_flush_draw_board(self):
        """测试同花面"""
        board = [Card.new('Ah'), Card.new('Kh'), Card.new('Th')]
        texture = BoardTexture(board)

        self.assertTrue(texture.flush_draw_possible)
        self.assertEqual(texture.high_card_count, 3)


class TestPreflopRanges(unittest.TestCase):
    """测试翻前范围表"""

    def test_position_ranges_get_tighter(self):
        """测试位置越早范围越紧"""
        utg_normal = parse_range_dict(get_open_range('UTG', 'normal'))
        co_normal = parse_range_dict(get_open_range('CO', 'normal'))
        btn_normal = parse_range_dict(get_open_range('BTN', 'normal'))

        # 范围应该: UTG < CO < BTN
        self.assertLess(utg_normal.size(), co_normal.size())
        self.assertLess(co_normal.size(), btn_normal.size())

    def test_tightness_levels(self):
        """测试紧度分级"""
        btn_tight = parse_range_dict(get_open_range('BTN', 'tight'))
        btn_normal = parse_range_dict(get_open_range('BTN', 'normal'))
        btn_loose = parse_range_dict(get_open_range('BTN', 'loose'))

        # 范围应该: tight < normal < loose
        self.assertLess(btn_tight.size(), btn_normal.size())
        self.assertLess(btn_normal.size(), btn_loose.size())

    def test_utg_normal_vpip(self):
        """测试UTG normal范围接近21% VPIP"""
        utg = parse_range_dict(get_open_range('UTG', 'normal'))
        total_combos = 1326  # 52选2
        vpip = utg.size() / total_combos

        # 允许 ±5% 误差 (范围表基于经验，不需要完全精确)
        # 实际 ~16-28% 都在合理范围内
        self.assertGreater(vpip, 0.15, "UTG normal应该有合理VPIP")
        self.assertLess(vpip, 0.30)


class TestRangeIntegration(unittest.TestCase):
    """集成测试: 范围推断 + equity计算"""

    def test_preflop_scenario(self):
        """
        场景: BTN open, BB 3-bet

        BB应该:
        1. 有合理的3-bet范围
        2. vs BTN范围有正equity
        """
        from advisor.range_engine import get_3bet_range, merge_range_dicts

        btn_open = parse_range_dict(get_open_range('BTN', 'normal'))
        bb_3bet_dict = get_3bet_range('BB', 'BTN')
        bb_3bet = merge_range_dicts(bb_3bet_dict['value'], bb_3bet_dict['bluff'])

        # BB 3-bet范围应该远小于BTN open
        self.assertLess(bb_3bet.size(), btn_open.size())

        # BB 3-bet范围应该 vs BTN有正equity
        calc = EquityCalculator()
        equity = calc.range_vs_range(bb_3bet, btn_open, [], nsamples=300)
        self.assertGreaterEqual(equity, 0.54, "BB 3-bet范围应该 vs BTN open有优势")


def run_tests():
    """运行所有测试"""
    suite = unittest.TestSuite()

    # 添加所有测试
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestRange))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestEquityCalculator))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestBoardTexture))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestPreflopRanges))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestRangeIntegration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
