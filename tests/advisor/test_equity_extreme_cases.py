#!/usr/bin/env python
"""
Equity计算器极端测试 - 验证边界情况和容易出bug的场景

测试目标:
1. 验证之前的顺子bug已彻底修复
2. 测试各种极端牌型组合
3. 测试边界情况和容易混淆的场景
4. 确保手牌评估逻辑100%正确
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import unittest

from advisor.range_engine import (
    Hand, Board, Card, Rank, Suit,
    HandEvaluator, HandRank, EquityCalculator,
)


class TestHandEvaluationExtreme(unittest.TestCase):
    """测试极端手牌评估情况"""

    def test_straight_bug_verification_1(self):
        """
        验证Bug修复: 三张A不应被识别为顺子

        之前的bug: As Ah Ac Q T 被错误识别为顺子
        原因: ranks = [14,14,14,12,10], 14-10=4 满足条件
        """
        cards = [
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.ACE, Suit.CLUBS),
            Card(Rank.QUEEN, Suit.DIAMONDS),
            Card(Rank.TEN, Suit.SPADES),
        ]

        result = HandEvaluator.evaluate(cards)

        print(f"\n验证Bug修复 - AsAhAcQT:")
        print(f"  期望: Three of a Kind (三条A)")
        print(f"  实际: {result}")

        # 应该是三条，不是顺子
        self.assertEqual(result.rank, HandRank.THREE_OF_A_KIND)
        self.assertEqual(result.primary[0], Rank.ACE)

    def test_straight_bug_verification_2(self):
        """
        验证Bug修复: 三张K不应被识别为顺子

        KKK J 9 -> [13,13,13,11,9], 13-9=4 不应识别为顺子
        """
        cards = [
            Card(Rank.KING, Suit.SPADES),
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.KING, Suit.DIAMONDS),
            Card(Rank.JACK, Suit.CLUBS),
            Card(Rank.NINE, Suit.SPADES),
        ]

        result = HandEvaluator.evaluate(cards)

        print(f"\n验证Bug修复 - KKKJ9:")
        print(f"  期望: Three of a Kind (三条K)")
        print(f"  实际: {result}")

        self.assertEqual(result.rank, HandRank.THREE_OF_A_KIND)
        self.assertEqual(result.primary[0], Rank.KING)

    def test_wheel_straight(self):
        """
        测试轮子顺子 (A-2-3-4-5)

        这是特殊情况：A既可以做14，也可以做1
        """
        cards = [
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.TWO, Suit.HEARTS),
            Card(Rank.THREE, Suit.DIAMONDS),
            Card(Rank.FOUR, Suit.CLUBS),
            Card(Rank.FIVE, Suit.SPADES),
        ]

        result = HandEvaluator.evaluate(cards)

        print(f"\n轮子顺子 - A2345:")
        print(f"  期望: Straight (5-high)")
        print(f"  实际: {result}")

        self.assertEqual(result.rank, HandRank.STRAIGHT)
        # 轮子顺子的最大牌是5
        self.assertEqual(result.primary[0], Rank.FIVE)

    def test_wheel_straight_flush(self):
        """
        测试轮子同花顺 (A-2-3-4-5 同花)
        """
        cards = [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.TWO, Suit.HEARTS),
            Card(Rank.THREE, Suit.HEARTS),
            Card(Rank.FOUR, Suit.HEARTS),
            Card(Rank.FIVE, Suit.HEARTS),
        ]

        result = HandEvaluator.evaluate(cards)

        print(f"\n轮子同花顺 - Ah2h3h4h5h:")
        print(f"  期望: Straight Flush (5-high)")
        print(f"  实际: {result}")

        self.assertEqual(result.rank, HandRank.STRAIGHT_FLUSH)
        self.assertEqual(result.primary[0], Rank.FIVE)

    def test_royal_flush(self):
        """
        测试皇家同花顺 (10-J-Q-K-A 同花)
        """
        cards = [
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.KING, Suit.SPADES),
            Card(Rank.QUEEN, Suit.SPADES),
            Card(Rank.JACK, Suit.SPADES),
            Card(Rank.TEN, Suit.SPADES),
        ]

        result = HandEvaluator.evaluate(cards)

        print(f"\n皇家同花顺 - AsKsQsJsTs:")
        print(f"  期望: Royal Flush")
        print(f"  实际: {result}")

        self.assertEqual(result.rank, HandRank.ROYAL_FLUSH)
        self.assertEqual(result.primary[0], Rank.ACE)

    def test_four_of_a_kind_with_ace(self):
        """
        测试四条A
        """
        cards = [
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.ACE, Suit.DIAMONDS),
            Card(Rank.ACE, Suit.CLUBS),
            Card(Rank.KING, Suit.SPADES),
        ]

        result = HandEvaluator.evaluate(cards)

        print(f"\n四条A - AsAhAdAcKs:")
        print(f"  期望: Four of a Kind (A)")
        print(f"  实际: {result}")

        self.assertEqual(result.rank, HandRank.FOUR_OF_A_KIND)
        self.assertEqual(result.primary[0], Rank.ACE)

    def test_full_house_aces_over_kings(self):
        """
        测试葫芦 - AAA over KK
        """
        cards = [
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.ACE, Suit.DIAMONDS),
            Card(Rank.KING, Suit.CLUBS),
            Card(Rank.KING, Suit.SPADES),
        ]

        result = HandEvaluator.evaluate(cards)

        print(f"\n葫芦 - AAAKK:")
        print(f"  期望: Full House (A over K)")
        print(f"  实际: {result}")

        self.assertEqual(result.rank, HandRank.FULL_HOUSE)
        self.assertEqual(result.primary[0], Rank.ACE)
        self.assertEqual(result.secondary[0], Rank.KING)

    def test_full_house_kings_over_aces(self):
        """
        测试葫芦 - KKK over AA

        应该小于 AAA over KK
        """
        cards = [
            Card(Rank.KING, Suit.SPADES),
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.KING, Suit.DIAMONDS),
            Card(Rank.ACE, Suit.CLUBS),
            Card(Rank.ACE, Suit.SPADES),
        ]

        result = HandEvaluator.evaluate(cards)

        print(f"\n葫芦 - KKKAA:")
        print(f"  期望: Full House (K over A)")
        print(f"  实际: {result}")

        self.assertEqual(result.rank, HandRank.FULL_HOUSE)
        self.assertEqual(result.primary[0], Rank.KING)
        self.assertEqual(result.secondary[0], Rank.ACE)

    def test_two_pair_aces_and_kings(self):
        """
        测试两对 - AA KK Q
        """
        cards = [
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.KING, Suit.DIAMONDS),
            Card(Rank.KING, Suit.CLUBS),
            Card(Rank.QUEEN, Suit.SPADES),
        ]

        result = HandEvaluator.evaluate(cards)

        print(f"\n两对 - AAKKQ:")
        print(f"  期望: Two Pair (A and K)")
        print(f"  实际: {result}")

        self.assertEqual(result.rank, HandRank.TWO_PAIR)
        # 两对都在primary里：[大对, 小对]
        self.assertEqual(result.primary[0], Rank.ACE)
        self.assertEqual(result.primary[1], Rank.KING)

    def test_flush_vs_straight_confusion(self):
        """
        测试同花 vs 顺子的区分

        同花但不是顺子: Ah Kh Qh Jh 9h (缺10)
        """
        cards = [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.QUEEN, Suit.HEARTS),
            Card(Rank.JACK, Suit.HEARTS),
            Card(Rank.NINE, Suit.HEARTS),
        ]

        result = HandEvaluator.evaluate(cards)

        print(f"\n同花非顺子 - AhKhQhJh9h:")
        print(f"  期望: Flush (not straight)")
        print(f"  实际: {result}")

        # 应该是同花，不是同花顺（缺10）
        self.assertEqual(result.rank, HandRank.FLUSH)

    def test_almost_straight(self):
        """
        测试差一张的顺子 (不应识别为顺子)

        K Q J T 8 (缺9或A)
        """
        cards = [
            Card(Rank.KING, Suit.SPADES),
            Card(Rank.QUEEN, Suit.HEARTS),
            Card(Rank.JACK, Suit.DIAMONDS),
            Card(Rank.TEN, Suit.CLUBS),
            Card(Rank.EIGHT, Suit.SPADES),
        ]

        result = HandEvaluator.evaluate(cards)

        print(f"\n差一张的顺子 - KQJT8:")
        print(f"  期望: High Card (K)")
        print(f"  实际: {result}")

        # 不应该是顺子
        self.assertNotEqual(result.rank, HandRank.STRAIGHT)
        self.assertEqual(result.rank, HandRank.HIGH_CARD)


class TestEquityExtreme(unittest.TestCase):
    """测试极端equity场景"""

    def setUp(self):
        """初始化计算器"""
        self.calc = EquityCalculator(iterations=10000)

    def test_nuts_vs_air(self):
        """
        测试坚果牌 vs 废牌 (河牌圈)

        Hero: AA (top set on river)
        Villain: 72o (nothing)
        Board: As Kh Qd Jc 9s (straight on board, but hero has trip A)

        实际上公共牌已经有顺子了，让我改一下
        """
        hero = Hand.from_str("AsAh")
        villain = Hand.from_str("7c2d")
        board = Board.from_str("AdKsQh5c3s")

        result = self.calc.calculate_equity(hero, villain, board)

        print(f"\n河牌 - AA vs 72 on AdKsQh5c3s:")
        print(f"  Hero (AA - trip A): {result.equity:.1%}")
        print(f"  Villain (72 - Q high): {(1.0 - result.equity):.1%}")

        # Hero应该100%获胜
        self.assertEqual(result.equity, 1.0)
        self.assertEqual((1.0 - result.equity), 0.0)

    def test_identical_hands_preflop(self):
        """
        测试完全相同的手牌 (翻前)

        AhKh vs AdKd - 应该完全50-50
        """
        hero = Hand.from_str("AhKh")
        villain = Hand.from_str("AdKd")
        board = Board.from_str("")

        result = self.calc.calculate_equity(hero, villain, board)

        print(f"\n翻前 - AhKh vs AdKd (identical hands):")
        print(f"  Hero equity: {result.equity:.1%}")
        print(f"  Villain equity: {(1.0 - result.equity):.1%}")
        print(f"  Tie rate: {result.tie:.1%}")

        # 应该是50-50
        self.assertAlmostEqual(result.equity, 0.5, delta=0.02)
        self.assertAlmostEqual((1.0 - result.equity), 0.5, delta=0.02)

    def test_pocket_aces_vs_seven_deuce(self):
        """
        测试最强 vs 最弱 (翻前)

        AA vs 72o - 最大的equity差距
        理论值: AA约88%
        """
        hero = Hand.from_str("AsAh")
        villain = Hand.from_str("7c2d")
        board = Board.from_str("")

        result = self.calc.calculate_equity(hero, villain, board)

        print(f"\n翻前 - AA vs 72o (best vs worst):")
        print(f"  AA equity: {result.equity:.1%}")
        print(f"  72o equity: {(1.0 - result.equity):.1%}")

        # AA应该有85%+的equity
        self.assertGreater(result.equity, 0.85)
        self.assertLess(result.equity, 0.92)

    def test_dominated_hand(self):
        """
        测试完全统治的情况

        AK vs AQ - 共享A，K统治Q
        理论值: AK约70%
        """
        hero = Hand.from_str("AsKh")
        villain = Hand.from_str("AhQd")
        board = Board.from_str("")

        result = self.calc.calculate_equity(hero, villain, board)

        print(f"\n翻前 - AK vs AQ (domination):")
        print(f"  AK equity: {result.equity:.1%}")
        print(f"  AQ equity: {(1.0 - result.equity):.1%}")

        # AK应该有65-75%的equity
        self.assertGreater(result.equity, 0.65)
        self.assertLess(result.equity, 0.75)

    def test_made_straight_flush_vs_quads(self):
        """
        测试河牌 - 同花顺 vs 四条

        Hero: 9h8h (straight flush)
        Villain: QhQs (quads)
        Board: QdQcJhTh7h
        """
        hero = Hand.from_str("9h8h")
        villain = Hand.from_str("QhQs")
        board = Board.from_str("QdQcJhTh7h")

        result = self.calc.calculate_equity(hero, villain, board)

        print(f"\n河牌 - 9h8h (straight flush) vs QQ (quads) on QdQcJhTh7h:")
        print(f"  Straight flush: {result.equity:.1%}")
        print(f"  Four of a kind: {(1.0 - result.equity):.1%}")

        # 同花顺应该100%获胜
        self.assertEqual(result.equity, 1.0)

    def test_board_plays(self):
        """
        测试公共牌最大情况 (board plays)

        Hero: 2h3h
        Villain: 4c5c
        Board: AsKsQsJsTs (royal flush on board)

        应该平分
        """
        hero = Hand.from_str("2h3h")
        villain = Hand.from_str("4c5c")
        board = Board.from_str("AsKsQsJsTs")

        result = self.calc.calculate_equity(hero, villain, board)

        print(f"\n河牌 - 2h3h vs 4c5c on AsKsQsJsTs (board plays):")
        print(f"  Hero: {result.equity:.1%}")
        print(f"  Villain: {(1.0 - result.equity):.1%}")
        print(f"  Tie rate: {result.tie:.1%}")

        # 应该平分（公共牌皇家同花顺）
        self.assertEqual(result.tie, 1.0)
        self.assertEqual(result.equity, 0.5)

    def test_counterfeited_hand(self):
        """
        测试被反超的情况

        Hero: AhKd (two pair on flop)
        Villain: 2s2h (bottom set)
        Board: Ah Kh 2d Ks Kc (full house KKK over AA on river)

        公共牌最终有AAKKK，双方都是葫芦，但公共牌已经是KKK over AA
        Hero: AK + AAKKK = KKKAA
        Villain: 22 + AAKKK = KKKAA
        应该平分
        """
        hero = Hand.from_str("AhKd")
        villain = Hand.from_str("2s2h")
        board = Board.from_str("AcKhKsKc2d")

        result = self.calc.calculate_equity(hero, villain, board)

        print(f"\n河牌 - AK vs 22 on AcKhKsKc2d:")
        print(f"  AK equity: {result.equity:.1%}")
        print(f"  22 equity: {(1.0 - result.equity):.1%}")
        print(f"  Tie rate: {result.tie:.1%}")

        # 检查是否正确评估
        # AK可以用Ad+Kc+Kh+Ks+Ac = KKKAA葫芦
        # 22可以用2s+2h+Kc+Kh+Ks = KKK22葫芦
        # AK的葫芦应该更大
        self.assertGreater(result.equity, 0.95)

    def test_one_outer_scenario(self):
        """
        测试只有1个out的情况 (runner-runner不算)

        Hero: KdQd (nothing)
        Villain: AsAh (top set)
        Board: Ah 7s 3c 2h (turn)

        Hero只有runner-runner顺子或同花的可能
        """
        hero = Hand.from_str("KdQd")
        villain = Hand.from_str("AsAh")
        board = Board.from_str("Ac7s3c2h")

        result = self.calc.calculate_equity(hero, villain, board)

        print(f"\n转牌 - KQ vs AA on Ac7s3c2h:")
        print(f"  KQ equity: {result.equity:.1%}")
        print(f"  AA equity: {(1.0 - result.equity):.1%}")

        # Hero应该只有很小的equity (<5%)
        self.assertLess(result.equity, 0.05)
        self.assertGreater((1.0 - result.equity), 0.95)


class TestHandComparisonEdgeCases(unittest.TestCase):
    """测试手牌比较的边界情况"""

    def test_compare_full_houses(self):
        """
        比较不同的葫芦

        AAAKK > KKKAA > AAAQQ > QQQAA
        """
        hand1 = HandEvaluator.evaluate([
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.ACE, Suit.DIAMONDS),
            Card(Rank.KING, Suit.CLUBS),
            Card(Rank.KING, Suit.SPADES),
        ])  # AAAKK

        hand2 = HandEvaluator.evaluate([
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.KING, Suit.DIAMONDS),
            Card(Rank.KING, Suit.CLUBS),
            Card(Rank.ACE, Suit.CLUBS),
            Card(Rank.ACE, Suit.DIAMONDS),
        ])  # KKKAA

        hand3 = HandEvaluator.evaluate([
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.ACE, Suit.CLUBS),
            Card(Rank.QUEEN, Suit.DIAMONDS),
            Card(Rank.QUEEN, Suit.SPADES),
        ])  # AAAQQ

        print(f"\n比较葫芦:")
        print(f"  AAAKK: {hand1}")
        print(f"  KKKAA: {hand2}")
        print(f"  AAAQQ: {hand3}")

        # AAAKK > KKKAA
        self.assertGreater(hand1, hand2)
        # AAAKK > AAAQQ
        self.assertGreater(hand1, hand3)
        # KKKAA < AAAKK
        self.assertLess(hand2, hand1)

    def test_compare_two_pairs(self):
        """
        比较不同的两对

        AAKKQ > AAKK J > KKQQJ > KKQQA
        """
        hand1 = HandEvaluator.evaluate([
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.KING, Suit.DIAMONDS),
            Card(Rank.KING, Suit.CLUBS),
            Card(Rank.QUEEN, Suit.SPADES),
        ])  # AAKKQ

        hand2 = HandEvaluator.evaluate([
            Card(Rank.ACE, Suit.CLUBS),
            Card(Rank.ACE, Suit.DIAMONDS),
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.KING, Suit.SPADES),
            Card(Rank.JACK, Suit.HEARTS),
        ])  # AAKKJ

        hand3 = HandEvaluator.evaluate([
            Card(Rank.KING, Suit.DIAMONDS),
            Card(Rank.KING, Suit.CLUBS),
            Card(Rank.QUEEN, Suit.HEARTS),
            Card(Rank.QUEEN, Suit.DIAMONDS),
            Card(Rank.JACK, Suit.SPADES),
        ])  # KKQQJ

        print(f"\n比较两对:")
        print(f"  AAKKQ: {hand1}")
        print(f"  AAKKJ: {hand2}")
        print(f"  KKQQJ: {hand3}")

        # AAKKQ > AAKKJ (kicker)
        self.assertGreater(hand1, hand2)
        # AAKKQ > KKQQJ
        self.assertGreater(hand1, hand3)
        # AAKKJ > KKQQJ
        self.assertGreater(hand2, hand3)

    def test_compare_straights(self):
        """
        比较不同的顺子

        AKQJT > 9876T > A2345
        """
        hand1 = HandEvaluator.evaluate([
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.QUEEN, Suit.DIAMONDS),
            Card(Rank.JACK, Suit.CLUBS),
            Card(Rank.TEN, Suit.SPADES),
        ])  # AKQJT

        hand2 = HandEvaluator.evaluate([
            Card(Rank.TEN, Suit.HEARTS),
            Card(Rank.NINE, Suit.DIAMONDS),
            Card(Rank.EIGHT, Suit.CLUBS),
            Card(Rank.SEVEN, Suit.SPADES),
            Card(Rank.SIX, Suit.HEARTS),
        ])  # T9876

        hand3 = HandEvaluator.evaluate([
            Card(Rank.ACE, Suit.CLUBS),
            Card(Rank.TWO, Suit.DIAMONDS),
            Card(Rank.THREE, Suit.SPADES),
            Card(Rank.FOUR, Suit.HEARTS),
            Card(Rank.FIVE, Suit.CLUBS),
        ])  # A2345 (wheel)

        print(f"\n比较顺子:")
        print(f"  AKQJT: {hand1}")
        print(f"  T9876: {hand2}")
        print(f"  A2345 (wheel): {hand3}")

        # AKQJT > T9876
        self.assertGreater(hand1, hand2)
        # T9876 > A2345 (轮子顺子最小)
        self.assertGreater(hand2, hand3)
        # AKQJT > A2345
        self.assertGreater(hand1, hand3)


def run_tests():
    """运行所有极端测试"""
    print("\n" + "=" * 70)
    print("  Equity计算器极端测试 - 验证边界情况")
    print("=" * 70)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加所有测试类
    suite.addTests(loader.loadTestsFromTestCase(TestHandEvaluationExtreme))
    suite.addTests(loader.loadTestsFromTestCase(TestEquityExtreme))
    suite.addTests(loader.loadTestsFromTestCase(TestHandComparisonEdgeCases))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 70)
    print("  极端测试总结")
    print("=" * 70)
    print(f"  运行测试: {result.testsRun}")
    print(f"  通过: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"  失败: {len(result.failures)}")
    print(f"  错误: {len(result.errors)}")

    if result.wasSuccessful():
        print("\n  ✅ 所有极端测试通过！计算逻辑验证正确！")
    else:
        print("\n  ❌ 发现问题，需要修复！")

    print("=" * 70 + "\n")

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
