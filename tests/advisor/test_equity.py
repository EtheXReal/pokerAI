#!/usr/bin/env python
"""
Equity计算器单元测试

测试:
1. Card, Hand, Board基础类
2. 手牌评估器 (9种牌型)
3. Hand vs Hand equity计算
4. Hand vs Range equity计算
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import unittest

from advisor.equity import (
    # Cards
    Rank, Suit, Card, Hand, Board,
    create_deck, validate_no_duplicates,
    # Evaluator
    HandRank, HandStrength, HandEvaluator, evaluate_hand,
    # Calculator
    EquityResult, EquityCalculator, quick_equity,
)


class TestCard(unittest.TestCase):
    """测试Card类"""

    def test_create_card(self):
        """测试创建卡牌"""
        card = Card(Rank.ACE, Suit.SPADES)
        self.assertEqual(card.rank, Rank.ACE)
        self.assertEqual(card.suit, Suit.SPADES)

    def test_card_from_str(self):
        """测试从字符串创建卡牌"""
        card = Card.from_str("As")
        self.assertEqual(card.rank, Rank.ACE)
        self.assertEqual(card.suit, Suit.SPADES)

        card2 = Card.from_str("Th")
        self.assertEqual(card2.rank, Rank.TEN)
        self.assertEqual(card2.suit, Suit.HEARTS)

    def test_card_str(self):
        """测试卡牌字符串表示"""
        card = Card(Rank.KING, Suit.HEARTS)
        self.assertEqual(str(card), "Kh")

    def test_card_equality(self):
        """测试卡牌相等性"""
        card1 = Card(Rank.ACE, Suit.SPADES)
        card2 = Card(Rank.ACE, Suit.SPADES)
        card3 = Card(Rank.ACE, Suit.HEARTS)

        self.assertEqual(card1, card2)
        self.assertNotEqual(card1, card3)

    def test_card_hash(self):
        """测试卡牌可哈希"""
        card1 = Card(Rank.ACE, Suit.SPADES)
        card2 = Card(Rank.ACE, Suit.SPADES)

        card_set = {card1, card2}
        self.assertEqual(len(card_set), 1)


class TestHand(unittest.TestCase):
    """测试Hand类"""

    def test_create_hand(self):
        """测试创建手牌"""
        hand = Hand([Card.from_str("As"), Card.from_str("Ks")])
        self.assertEqual(len(hand.cards), 2)

    def test_hand_from_str(self):
        """测试从字符串创建手牌"""
        hand = Hand.from_str("AsKs")
        self.assertEqual(str(hand), "AsKs")

    def test_hand_invalid_length(self):
        """测试无效手牌长度"""
        with self.assertRaises(ValueError):
            Hand([Card.from_str("As")])  # 只有1张牌

    def test_pocket_pair(self):
        """测试对子检测"""
        pair = Hand.from_str("AsAh")
        self.assertTrue(pair.is_pocket_pair())

        non_pair = Hand.from_str("AsKs")
        self.assertFalse(non_pair.is_pocket_pair())

    def test_suited(self):
        """测试同花检测"""
        suited = Hand.from_str("AsKs")
        self.assertTrue(suited.is_suited())

        offsuit = Hand.from_str("AsKh")
        self.assertFalse(offsuit.is_suited())


class TestBoard(unittest.TestCase):
    """测试Board类"""

    def test_create_empty_board(self):
        """测试创建空牌面"""
        board = Board([])
        self.assertTrue(board.is_preflop())
        self.assertEqual(len(board), 0)

    def test_board_from_str(self):
        """测试从字符串创建牌面"""
        board = Board.from_str("AsKsQs")
        self.assertEqual(len(board), 3)
        self.assertTrue(board.is_flop())

    def test_board_stages(self):
        """测试牌面阶段检测"""
        preflop = Board.from_str("")
        self.assertTrue(preflop.is_preflop())

        flop = Board.from_str("AsKsQs")
        self.assertTrue(flop.is_flop())

        turn = Board.from_str("AsKsQsJs")
        self.assertTrue(turn.is_turn())

        river = Board.from_str("AsKsQsJsTs")
        self.assertTrue(river.is_river())


class TestDeck(unittest.TestCase):
    """测试牌组相关"""

    def test_create_deck(self):
        """测试创建完整牌组"""
        deck = create_deck()
        self.assertEqual(len(deck), 52)

        # 检查没有重复
        self.assertEqual(len(set(deck)), 52)

    def test_validate_no_duplicates(self):
        """测试重复牌检测"""
        hand = Hand.from_str("AsKs")
        board = Board.from_str("QsJs")

        # 应该通过
        validate_no_duplicates(hand, board)

        # 应该失败 (重复As)
        hand2 = Hand.from_str("AsKs")
        board2 = Board.from_str("AsQsJs")

        with self.assertRaises(ValueError):
            validate_no_duplicates(hand2, board2)


class TestHandEvaluator(unittest.TestCase):
    """测试手牌评估器"""

    def test_high_card(self):
        """测试高牌"""
        cards = [
            Card.from_str("As"),
            Card.from_str("Kd"),
            Card.from_str("Qh"),
            Card.from_str("Jc"),
            Card.from_str("9s"),
        ]
        strength = HandEvaluator.evaluate(cards)
        self.assertEqual(strength.rank, HandRank.HIGH_CARD)
        self.assertEqual(strength.primary[0], int(Rank.ACE))

    def test_one_pair(self):
        """测试一对"""
        cards = [
            Card.from_str("As"),
            Card.from_str("Ad"),
            Card.from_str("Kh"),
            Card.from_str("Qc"),
            Card.from_str("Js"),
        ]
        strength = HandEvaluator.evaluate(cards)
        self.assertEqual(strength.rank, HandRank.ONE_PAIR)
        self.assertEqual(strength.primary[0], int(Rank.ACE))

    def test_two_pair(self):
        """测试两对"""
        cards = [
            Card.from_str("As"),
            Card.from_str("Ad"),
            Card.from_str("Kh"),
            Card.from_str("Kc"),
            Card.from_str("Qs"),
        ]
        strength = HandEvaluator.evaluate(cards)
        self.assertEqual(strength.rank, HandRank.TWO_PAIR)
        self.assertEqual(strength.primary[0], int(Rank.ACE))
        self.assertEqual(strength.primary[1], int(Rank.KING))

    def test_three_of_a_kind(self):
        """测试三条"""
        cards = [
            Card.from_str("As"),
            Card.from_str("Ad"),
            Card.from_str("Ah"),
            Card.from_str("Kc"),
            Card.from_str("Qs"),
        ]
        strength = HandEvaluator.evaluate(cards)
        self.assertEqual(strength.rank, HandRank.THREE_OF_A_KIND)
        self.assertEqual(strength.primary[0], int(Rank.ACE))

    def test_straight(self):
        """测试顺子"""
        # 普通顺子
        cards = [
            Card.from_str("As"),
            Card.from_str("Kd"),
            Card.from_str("Qh"),
            Card.from_str("Jc"),
            Card.from_str("Ts"),
        ]
        strength = HandEvaluator.evaluate(cards)
        self.assertEqual(strength.rank, HandRank.STRAIGHT)
        self.assertEqual(strength.primary[0], int(Rank.ACE))

        # A-2-3-4-5 (轮子顺子)
        cards2 = [
            Card.from_str("As"),
            Card.from_str("2d"),
            Card.from_str("3h"),
            Card.from_str("4c"),
            Card.from_str("5s"),
        ]
        strength2 = HandEvaluator.evaluate(cards2)
        self.assertEqual(strength2.rank, HandRank.STRAIGHT)
        self.assertEqual(strength2.primary[0], int(Rank.FIVE))

    def test_flush(self):
        """测试同花"""
        cards = [
            Card.from_str("As"),
            Card.from_str("Ks"),
            Card.from_str("Qs"),
            Card.from_str("Js"),
            Card.from_str("9s"),
        ]
        strength = HandEvaluator.evaluate(cards)
        self.assertEqual(strength.rank, HandRank.FLUSH)
        self.assertEqual(strength.primary[0], int(Rank.ACE))

    def test_full_house(self):
        """测试葫芦"""
        cards = [
            Card.from_str("As"),
            Card.from_str("Ad"),
            Card.from_str("Ah"),
            Card.from_str("Kc"),
            Card.from_str("Ks"),
        ]
        strength = HandEvaluator.evaluate(cards)
        self.assertEqual(strength.rank, HandRank.FULL_HOUSE)
        self.assertEqual(strength.primary[0], int(Rank.ACE))
        self.assertEqual(strength.secondary[0], int(Rank.KING))

    def test_four_of_a_kind(self):
        """测试四条"""
        cards = [
            Card.from_str("As"),
            Card.from_str("Ad"),
            Card.from_str("Ah"),
            Card.from_str("Ac"),
            Card.from_str("Ks"),
        ]
        strength = HandEvaluator.evaluate(cards)
        self.assertEqual(strength.rank, HandRank.FOUR_OF_A_KIND)
        self.assertEqual(strength.primary[0], int(Rank.ACE))

    def test_straight_flush(self):
        """测试同花顺"""
        cards = [
            Card.from_str("Ks"),
            Card.from_str("Qs"),
            Card.from_str("Js"),
            Card.from_str("Ts"),
            Card.from_str("9s"),
        ]
        strength = HandEvaluator.evaluate(cards)
        self.assertEqual(strength.rank, HandRank.STRAIGHT_FLUSH)
        self.assertEqual(strength.primary[0], int(Rank.KING))

    def test_royal_flush(self):
        """测试皇家同花顺"""
        cards = [
            Card.from_str("As"),
            Card.from_str("Ks"),
            Card.from_str("Qs"),
            Card.from_str("Js"),
            Card.from_str("Ts"),
        ]
        strength = HandEvaluator.evaluate(cards)
        self.assertEqual(strength.rank, HandRank.ROYAL_FLUSH)

    def test_hand_comparison(self):
        """测试手牌强度比较"""
        # 四条 > 葫芦
        quads = HandEvaluator.evaluate([
            Card.from_str("As"), Card.from_str("Ad"),
            Card.from_str("Ah"), Card.from_str("Ac"), Card.from_str("Ks")
        ])
        full_house = HandEvaluator.evaluate([
            Card.from_str("Ks"), Card.from_str("Kd"),
            Card.from_str("Kh"), Card.from_str("Qc"), Card.from_str("Qs")
        ])
        self.assertGreater(quads, full_house)

        # 大对子 > 小对子
        aces = HandEvaluator.evaluate([
            Card.from_str("As"), Card.from_str("Ad"),
            Card.from_str("Kh"), Card.from_str("Qc"), Card.from_str("Js")
        ])
        kings = HandEvaluator.evaluate([
            Card.from_str("Ks"), Card.from_str("Kd"),
            Card.from_str("Ah"), Card.from_str("Qc"), Card.from_str("Js")
        ])
        self.assertGreater(aces, kings)

    def test_evaluate_best_5_from_7(self):
        """测试从7张牌中评估最佳5张"""
        # 手牌: AhKh, 公共牌: Qh Jh Th 2d 3c
        # 最佳牌型: 皇家同花顺
        cards = [
            Card.from_str("Ah"), Card.from_str("Kh"),  # 手牌
            Card.from_str("Qh"), Card.from_str("Jh"), Card.from_str("Th"),  # 公共牌
            Card.from_str("2d"), Card.from_str("3c"),
        ]
        strength = HandEvaluator.evaluate_best_5(cards)
        self.assertEqual(strength.rank, HandRank.ROYAL_FLUSH)


class TestEquityCalculator(unittest.TestCase):
    """测试Equity计算器"""

    def test_create_calculator(self):
        """测试创建计算器"""
        calc = EquityCalculator(iterations=1000)
        self.assertEqual(calc.iterations, 1000)

    def test_calculate_equity_preflop(self):
        """测试翻前equity计算"""
        calc = EquityCalculator(iterations=10000)

        # AA vs KK (AA应该约80-82% equity)
        result = calc.calculate_equity(
            Hand.from_str("AsAh"),
            Hand.from_str("KsKh"),
            Board([])
        )
        # 考虑蒙特卡洛方差，设置更宽容的范围
        self.assertGreater(result.equity, 0.73)
        self.assertLess(result.equity, 0.87)

    def test_calculate_equity_postflop(self):
        """测试翻后equity计算"""
        calc = EquityCalculator(iterations=5000)

        # AK vs QQ on A-high flop (AK应该有很高equity)
        result = calc.calculate_equity(
            Hand.from_str("AsKs"),
            Hand.from_str("QhQd"),
            Board.from_str("Ah7h2d")
        )
        self.assertGreater(result.equity, 0.85)  # AK已经击中A

    def test_equity_result_properties(self):
        """测试EquityResult属性"""
        result = EquityResult(win=0.5, tie=0.1, loss=0.4, iterations=1000)

        # 总和应该是1.0
        self.assertAlmostEqual(result.win + result.tie + result.loss, 1.0)

        # Equity = win + tie/2
        self.assertAlmostEqual(result.equity, 0.55)

    def test_validate_no_overlap(self):
        """测试检测重复牌"""
        calc = EquityCalculator(iterations=1000)

        # 应该抛出异常 (两手牌有重复As)
        with self.assertRaises(ValueError):
            calc.calculate_equity(
                Hand.from_str("AsKs"),
                Hand.from_str("AsQd"),
                Board([])
            )

    def test_calculate_vs_range(self):
        """测试vs range的equity计算"""
        calc = EquityCalculator(iterations=2000)

        # AK vs {QQ, JJ, TT}
        villain_range = [
            Hand.from_str("QhQd"),
            Hand.from_str("JhJd"),
            Hand.from_str("ThTd"),
        ]

        result = calc.calculate_vs_range(
            Hand.from_str("AsKs"),
            villain_range,
            Board([])
        )

        # AK vs 中等对子，equity应该在40-50%左右
        self.assertGreater(result.equity, 0.35)
        self.assertLess(result.equity, 0.55)

    def test_quick_equity_function(self):
        """测试quick_equity便捷函数"""
        result = quick_equity("AsKs", "QhQd", "", iterations=5000)

        # AKs vs QQ equity约45-47%
        self.assertGreater(result.equity, 0.42)
        self.assertLess(result.equity, 0.50)


class TestKnownEquities(unittest.TestCase):
    """测试已知equity场景"""

    def test_set_vs_flush_draw(self):
        """测试三条 vs 同花听牌"""
        calc = EquityCalculator(iterations=5000)

        # 77 on 7-8-9 rainbow vs flush draw
        # Set应该有约60-70% equity
        result = calc.calculate_equity(
            Hand.from_str("7h7d"),
            Hand.from_str("AsKs"),
            Board.from_str("7s8s9h")
        )

        # 77有三条，AsKs有同花听牌和两张高牌
        self.assertGreater(result.equity, 0.55)
        self.assertLess(result.equity, 0.80)

    def test_dominated_hand(self):
        """测试被压制的手牌"""
        calc = EquityCalculator(iterations=5000)

        # AK vs AQ (AK dominate AQ)
        result = calc.calculate_equity(
            Hand.from_str("AsKs"),
            Hand.from_str("AhQh"),
            Board([])
        )

        # AK应该有约70% equity
        self.assertGreater(result.equity, 0.65)
        self.assertLess(result.equity, 0.75)


def run_tests():
    """运行所有测试"""
    suite = unittest.TestSuite()

    # 添加所有测试类
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestCard))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestHand))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestBoard))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestDeck))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestHandEvaluator))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestEquityCalculator))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestKnownEquities))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
