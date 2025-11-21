#!/usr/bin/env python
"""
翻后Equity精度测试 (Postflop Accuracy Tests)

对比在线计算器 (PokerStove, Equilab, ProPokerTools) 验证翻后equity计算精度

测试场景:
1. Flop场景 (3张公共牌)
2. Turn场景 (4张公共牌)
3. River场景 (5张公共牌)
4. 各种牌面结构 (干燥面、湿润面、同花面)
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import unittest

from poker_core import (
    Hand, Board, EquityCalculator,
)


class TestPostflopAccuracy(unittest.TestCase):
    """测试翻后equity精度"""

    def setUp(self):
        """初始化计算器"""
        self.calc = EquityCalculator(iterations=20000)

    def test_flop_overpair_vs_underpair(self):
        """
        翻牌圈: 超对 vs 底对

        Hero: AA
        Villain: 88
        Board: 8h 5c 2d (villain set)

        理论值: AA约12% (需要A或runner-runner)
        来源: PokerStove
        """
        hero = Hand.from_str("AsAh")
        villain = Hand.from_str("8s8d")
        board = Board.from_str("8h5c2d")

        result = self.calc.calculate_equity(hero, villain, board)

        print(f"\n翻牌圈 - AA vs 88 on 8h5c2d")
        print(f"  理论值: ~12%")
        print(f"  实际值: {result.equity:.1%}")
        print(f"  误差: {abs(result.equity - 0.12) * 100:.1f}%")

        # AA只有约12% equity (需要A或runner-runner两对/顺子)
        self.assertGreater(result.equity, 0.08)
        self.assertLess(result.equity, 0.18)

    def test_flop_flush_draw(self):
        """
        翻牌圈: 同花听牌

        Hero: As Ks (nut flush draw)
        Villain: Qd Qh (overpair)
        Board: 9s 6s 2h

        理论值: AKs约54% (9 flush outs + 6 overcard outs = 15 outs)
        来源: Equilab (修正后)
        """
        hero = Hand.from_str("AsKs")
        villain = Hand.from_str("QdQh")
        board = Board.from_str("9s6s2h")

        result = self.calc.calculate_equity(hero, villain, board)

        print(f"\n翻牌圈 - AKs (flush draw) vs QQ on 9s6s2h")
        print(f"  理论值: ~54%")
        print(f"  实际值: {result.equity:.1%}")
        print(f"  误差: {abs(result.equity - 0.54) * 100:.1f}%")

        # 同花听牌+两张overcards约54% (15 outs)
        self.assertGreater(result.equity, 0.49)
        self.assertLess(result.equity, 0.59)

    def test_flop_top_pair_vs_set(self):
        """
        翻牌圈: 顶对 vs 暗三条

        Hero: Ah Kd (top pair top kicker)
        Villain: 7h 7s (set)
        Board: As 7c 3d

        理论值: AK约2-3% (只有runner-runner A-A或K-K才能赢)
        来源: ProPokerTools (修正后)
        """
        hero = Hand.from_str("AhKd")
        villain = Hand.from_str("7h7s")
        board = Board.from_str("As7c3d")

        result = self.calc.calculate_equity(hero, villain, board)

        print(f"\n翻牌圈 - AK (top pair) vs 77 (set) on As7c3d")
        print(f"  理论值: ~2.5%")
        print(f"  实际值: {result.equity:.1%}")
        print(f"  误差: {abs(result.equity - 0.025) * 100:.1f}%")

        # 顶对vs暗三只有约2-3% equity (只有2个A和3个K的runner-runner)
        self.assertGreater(result.equity, 0.01)
        self.assertLess(result.equity, 0.05)

    def test_flop_oesd_vs_overpair(self):
        """
        翻牌圈: 两端顺子听牌 vs 超对

        Hero: JsTs (open-ended straight draw)
        Villain: Ah Ad (overpair)
        Board: Qh 9d 3c

        理论值: JT约32% (8 outs)
        来源: PokerStove
        """
        hero = Hand.from_str("JsTs")
        villain = Hand.from_str("AhAd")
        board = Board.from_str("Qh9d3c")

        result = self.calc.calculate_equity(hero, villain, board)

        print(f"\n翻牌圈 - JT (OESD) vs AA on Qh9d3c")
        print(f"  理论值: ~32%")
        print(f"  实际值: {result.equity:.1%}")
        print(f"  误差: {abs(result.equity - 0.32) * 100:.1f}%")

        # 两端顺子听牌约32%
        self.assertGreater(result.equity, 0.28)
        self.assertLess(result.equity, 0.37)

    def test_turn_flush_draw(self):
        """
        转牌圈: 同花听牌

        Hero: Ah Kh (nut flush draw)
        Villain: Qs Qd (overpair)
        Board: Jh 9h 3c 2s

        理论值: AK约35% (9 flush outs + 6 overcard outs / 46 cards)
        来源: Equilab (修正后 - 包含overcard outs)
        """
        hero = Hand.from_str("AhKh")
        villain = Hand.from_str("QsQd")
        board = Board.from_str("Jh9h3c2s")

        result = self.calc.calculate_equity(hero, villain, board)

        print(f"\n转牌圈 - AhKh (flush draw) vs QQ on Jh9h3c2s")
        print(f"  理论值: ~35%")
        print(f"  实际值: {result.equity:.1%}")
        print(f"  误差: {abs(result.equity - 0.35) * 100:.1f}%")

        # 转牌同花听牌+overcards约35%
        self.assertGreater(result.equity, 0.30)
        self.assertLess(result.equity, 0.40)

    def test_turn_two_pair_vs_straight(self):
        """
        转牌圈: 两对 vs 顺子

        Hero: As Kd (two pair)
        Villain: Ts 9h (straight)
        Board: Ah Kh Jc Qd

        理论值: AK约13% (4 outs for full house / 46 cards = 8.7%, plus runner-runner)
        来源: ProPokerTools
        """
        hero = Hand.from_str("AsKd")
        villain = Hand.from_str("Ts9h")
        board = Board.from_str("AhKhJcQd")

        result = self.calc.calculate_equity(hero, villain, board)

        print(f"\n转牌圈 - AK (two pair) vs T9 (straight) on AhKhJcQd")
        print(f"  理论值: ~13%")
        print(f"  实际值: {result.equity:.1%}")
        print(f"  误差: {abs(result.equity - 0.13) * 100:.1f}%")

        # 两对vs顺子约13%
        self.assertGreater(result.equity, 0.08)
        self.assertLess(result.equity, 0.18)

    def test_turn_set_vs_flush_draw(self):
        """
        转牌圈: 暗三 vs 同花听牌

        Hero: 9s 9d (set)
        Villain: Ah Kh (nut flush draw)
        Board: 9h 7h 3c 2s

        理论值: 99约84% (阻挡一张同花out, 且有10张full house/quads outs)
        来源: PokerStove (修正后 - villain只有8 clean outs)
        """
        hero = Hand.from_str("9s9d")
        villain = Hand.from_str("AhKh")
        board = Board.from_str("9h7h3c2s")

        result = self.calc.calculate_equity(hero, villain, board)

        print(f"\n转牌圈 - 99 (set) vs AhKh (flush draw) on 9h7h3c2s")
        print(f"  理论值: ~84%")
        print(f"  实际值: {result.equity:.1%}")
        print(f"  误差: {abs(result.equity - 0.84) * 100:.1f}%")

        # 暗三vs同花听牌约84% (villain被阻挡+hero有很多outs)
        self.assertGreater(result.equity, 0.79)
        self.assertLess(result.equity, 0.89)

    def test_river_nuts_vs_second_nuts(self):
        """
        河牌圈: 坚果同花 vs 次坚果同花

        Hero: Ah Kh (nut heart flush)
        Villain: Qh Jh (second nut flush)
        Board: Th 8h 3h 2c 5d

        理论值: AhKh 100% (已定胜负 - A-high flush beats Q-high flush)
        """
        hero = Hand.from_str("AhKh")
        villain = Hand.from_str("QhJh")
        board = Board.from_str("Th8h3h2c5d")

        result = self.calc.calculate_equity(hero, villain, board)

        print(f"\n河牌圈 - AhKh (nut flush) vs QhJh (Q-high flush) on Th8h3h2c5d")
        print(f"  理论值: 100%")
        print(f"  实际值: {result.equity:.1%}")

        # 河牌已定胜负 - nut flush beats second nut flush
        self.assertEqual(result.equity, 1.0)

    def test_river_chop(self):
        """
        河牌圈: 平分底池

        Hero: Ah Kd
        Villain: As Kc
        Board: Qh Jh Th 9c 8d (board straight)

        理论值: 50% (平分)
        """
        hero = Hand.from_str("AhKd")
        villain = Hand.from_str("AsKc")
        board = Board.from_str("QhJhTh9c8d")

        result = self.calc.calculate_equity(hero, villain, board)

        print(f"\n河牌圈 - AhKd vs AsKc (chop) on QhJhTh9c8d")
        print(f"  理论值: 50%")
        print(f"  实际值: {result.equity:.1%}")

        # 平分底池
        self.assertEqual(result.equity, 0.5)

    def test_flop_combo_draw(self):
        """
        翻牌圈: 组合听牌 (同花+顺子)

        Hero: Jh Th (flush draw + OESD)
        Villain: As Ad (overpair)
        Board: Qh 9h 3c

        理论值: JT约54% (15 outs)
        来源: Equilab
        """
        hero = Hand.from_str("JhTh")
        villain = Hand.from_str("AsAd")
        board = Board.from_str("Qh9h3c")

        result = self.calc.calculate_equity(hero, villain, board)

        print(f"\n翻牌圈 - JhTh (combo draw) vs AA on Qh9h3c")
        print(f"  理论值: ~54%")
        print(f"  实际值: {result.equity:.1%}")
        print(f"  误差: {abs(result.equity - 0.54) * 100:.1f}%")

        # 组合听牌约54%
        self.assertGreater(result.equity, 0.49)
        self.assertLess(result.equity, 0.59)


def run_tests():
    """运行所有翻后精度测试"""
    print("\n" + "=" * 70)
    print("  翻后Equity精度测试 - 对比在线计算器")
    print("=" * 70)

    suite = unittest.TestLoader().loadTestsFromTestCase(TestPostflopAccuracy)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 70)
    print("  测试总结")
    print("=" * 70)
    print(f"  运行测试: {result.testsRun}")
    print(f"  通过: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"  失败: {len(result.failures)}")
    print(f"  错误: {len(result.errors)}")
    print("=" * 70 + "\n")

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
