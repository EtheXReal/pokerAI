#!/usr/bin/env python
"""
GTO Baseline 单元测试

测试:
1. GTO公式正确性 (MDF, Pot Odds, Bluff频率)
2. 翻前策略逻辑
3. 翻后防守/主动策略
4. 多人底池调整
5. Bug修复验证
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import unittest
from advisor.strategy_engine.gto_baseline import (
    GTOBaseline, GTOContext, Street, Position
)


class TestGTOFormulas(unittest.TestCase):
    """测试GTO公式"""

    def test_mdf_calculation(self):
        """测试MDF计算"""
        gto = GTOBaseline()

        # 例1: pot=100, bet=50
        # MDF = 100/(100+50) = 0.666...
        mdf = gto.calculate_mdf(100, 50)
        self.assertAlmostEqual(mdf, 2/3, places=2)

        # 例2: pot=100, bet=100
        # MDF = 100/(100+100) = 0.5
        mdf2 = gto.calculate_mdf(100, 100)
        self.assertAlmostEqual(mdf2, 0.5, places=2)

        # 例3: pot=100, bet=33
        # MDF = 100/(100+33) = 0.75
        mdf3 = gto.calculate_mdf(100, 33)
        self.assertAlmostEqual(mdf3, 0.75, places=2)

    def test_pot_odds_calculation(self):
        """测试底池赔率计算"""
        gto = GTOBaseline()

        # 例1: pot=100, call=50
        # Pot odds = 50/(100+50) = 0.333...
        odds = gto.calculate_pot_odds(100, 50)
        self.assertAlmostEqual(odds, 1/3, places=2)

        # 例2: pot=10, call=7.5
        # Pot odds = 7.5/(10+7.5) = 0.428...
        odds2 = gto.calculate_pot_odds(10, 7.5)
        self.assertAlmostEqual(odds2, 7.5/17.5, places=2)

    def test_optimal_bluff_frequency(self):
        """测试最优bluff频率"""
        gto = GTOBaseline()

        # 例1: pot=100, bet=50
        # Bluff freq = 50/(50+100) = 0.333... (1/3 bluff, 2/3 value)
        bluff = gto.calculate_optimal_bluff_frequency(100, 50)
        self.assertAlmostEqual(bluff, 1/3, places=2)

        # 例2: pot=100, bet=100
        # Bluff freq = 100/(100+100) = 0.5
        bluff2 = gto.calculate_optimal_bluff_frequency(100, 100)
        self.assertAlmostEqual(bluff2, 0.5, places=2)

    def test_multiway_equity_discount(self):
        """测试多人底池equity打折"""
        gto = GTOBaseline()

        # 单挑：无打折
        eq1 = gto.multiway_equity_discount(0.80, 1)
        self.assertAlmostEqual(eq1, 0.80, places=2)

        # 3人底池：打折15%
        eq2 = gto.multiway_equity_discount(0.80, 2)
        self.assertAlmostEqual(eq2, 0.80 * 0.85, places=2)

        # 4人底池：打折30%
        eq3 = gto.multiway_equity_discount(0.80, 3)
        self.assertAlmostEqual(eq3, 0.80 * 0.70, places=2)


class TestPreflopStrategies(unittest.TestCase):
    """测试翻前策略"""

    def setUp(self):
        self.gto = GTOBaseline()

    def test_preflop_open_by_position(self):
        """测试不同位置的开池范围"""
        # UTG紧 (threshold=0.75)
        utg_weak = self.gto._preflop_open_strategy(Position.UTG, 0.70)
        self.assertEqual(utg_weak['fold'], 1.0, "UTG弱牌应该fold")

        utg_strong = self.gto._preflop_open_strategy(Position.UTG, 0.80)
        self.assertEqual(utg_strong['raise'], 1.0, "UTG强牌应该raise")

        # BTN宽 (threshold=0.50)
        btn_medium = self.gto._preflop_open_strategy(Position.BTN, 0.60)
        self.assertEqual(btn_medium['raise'], 1.0, "BTN中等牌应该raise")

    def test_preflop_vs_open(self):
        """测试面对open的策略"""
        # 强牌：3-bet
        strong = self.gto._preflop_vs_open(Position.BTN, 0.90, 100)
        self.assertGreater(strong.get('3bet', 0), 0.5, "强牌应该主要3-bet")

        # 中等牌：跟注为主
        medium = self.gto._preflop_vs_open(Position.BTN, 0.70, 100)
        self.assertGreater(medium.get('call', 0), 0.5, "中等牌应该主要call")

        # 弱牌：弃牌
        weak = self.gto._preflop_vs_open(Position.BTN, 0.50, 100)
        self.assertGreater(weak.get('fold', 0), 0.5, "弱牌应该fold")

    def test_preflop_vs_3bet_with_equity(self):
        """测试面对3-bet的策略（使用equity）"""
        # Bug修复验证：应该优先使用equity

        # 高equity (0.65): 应该主要call/4bet
        high_eq = self.gto._preflop_vs_3bet(Position.BTN, 0.70, 100, equity=0.65)
        self.assertLess(high_eq.get('fold', 1.0), 0.1, "高equity不应该fold")

        # 中等equity (0.55): 应该主要call
        med_eq = self.gto._preflop_vs_3bet(Position.BTN, 0.70, 100, equity=0.55)
        self.assertLess(med_eq.get('fold', 1.0), 0.1, "中等equity不应该fold")
        self.assertGreater(med_eq.get('call', 0), 0.5, "应该主要call")

        # 接近pot odds (0.48): 应该主要call，少量fold
        edge_eq = self.gto._preflop_vs_3bet(Position.BTN, 0.70, 100, equity=0.48)
        self.assertLess(edge_eq.get('fold', 1.0), 0.1, "接近pot odds应该call")

        # 低于pot odds (0.40): 可以fold
        low_eq = self.gto._preflop_vs_3bet(Position.BTN, 0.70, 100, equity=0.40)
        self.assertGreater(low_eq.get('fold', 0), 0.4, "低equity可以fold")

    def test_preflop_vs_3bet_by_opponent_type(self):
        """测试vs不同对手类型的3-bet防守"""
        # Bug修复验证：应该根据对手类型调整阈值

        # vs LAG：defend wider (他们3-bet范围宽)
        vs_lag = self.gto._preflop_vs_3bet(
            Position.BTN, 0.75, 100,
            equity=None, opponent_type='LAG'
        )
        # strength=0.75 vs LAG应该call (call_threshold=0.70)
        self.assertGreater(vs_lag.get('call', 0), 0.5, "vs LAG应该wider defend")

        # vs Nit：defend tighter (他们3-bet范围紧)
        vs_nit = self.gto._preflop_vs_3bet(
            Position.BTN, 0.75, 100,
            equity=None, opponent_type='NIT'
        )
        # strength=0.75 vs Nit应该fold (call_threshold=0.80)
        self.assertGreater(vs_nit.get('fold', 0), 0.25, "vs Nit应该tighter defend")

    def test_qq_vs_lag_3bet_scenario(self):
        """
        关键场景测试：QQ vs LAG 3-bet

        这是CRITICAL_BUGS.md中的场景，必须通过
        """
        # QQ strength约为0.90，equity vs LAG 3-bet范围约为0.70
        qq_decision = self.gto._preflop_vs_3bet(
            Position.BTN,
            strength=0.90,
            stack=100,
            equity=0.70,  # QQ vs LAG 3-bet范围
            opponent_type='LAG'
        )

        # QQ应该call或4-bet，不应该fold
        self.assertLess(
            qq_decision.get('fold', 1.0),
            0.1,
            "QQ vs LAG 3-bet不应该fold！"
        )
        self.assertGreater(
            qq_decision.get('call', 0) + qq_decision.get('4bet', 0),
            0.9,
            "QQ应该call或4-bet"
        )

    def test_preflop_vs_4bet(self):
        """测试面对4-bet的策略"""
        # 超强牌：继续
        nuts = self.gto._preflop_vs_4bet(0.95, 100)
        self.assertEqual(nuts.get('fold', 1.0), 0.0, "nuts不应该fold")

        # 强牌：主要跟注
        strong = self.gto._preflop_vs_4bet(0.88, 100)
        self.assertGreater(strong.get('call', 0), 0.5, "强牌应该call")

        # 弱牌：弃牌
        weak = self.gto._preflop_vs_4bet(0.80, 100)
        self.assertEqual(weak.get('fold', 1.0), 1.0, "vs 4bet弱牌应该fold")


class TestPostflopStrategies(unittest.TestCase):
    """测试翻后策略"""

    def setUp(self):
        self.gto = GTOBaseline()

    def test_defense_strategy_good_equity(self):
        """测试防守策略：高equity"""
        ctx = GTOContext(
            street=Street.FLOP,
            position=Position.BTN,
            is_in_position=True,
            equity=0.70,
            range_advantage='medium',
            pot_size=20.0,
            effective_stack=80.0,
            spr=4.0,
            num_opponents=1,
            facing_bet=15.0,
            bet_to_call=15.0
        )

        decision = self.gto._defense_strategy(ctx)

        # 高equity应该主要call/raise
        self.assertLess(decision.get('fold', 1.0), 0.25, "高equity不应该fold太多")
        self.assertGreater(decision.get('call', 0), 0.5, "应该主要call")

    def test_defense_strategy_low_equity(self):
        """测试防守策略：低equity"""
        ctx = GTOContext(
            street=Street.FLOP,
            position=Position.BB,
            is_in_position=False,
            equity=0.25,
            range_advantage='weak',
            pot_size=20.0,
            effective_stack=80.0,
            spr=4.0,
            num_opponents=1,
            facing_bet=15.0,
            bet_to_call=15.0
        )

        decision = self.gto._defense_strategy(ctx)

        # 低equity应该主要fold
        self.assertGreater(decision.get('fold', 0), 0.5, "低equity应该fold")

    def test_aggression_strategy_strong_hand(self):
        """测试主动策略：强牌"""
        ctx = GTOContext(
            street=Street.FLOP,
            position=Position.BTN,
            is_in_position=True,
            equity=0.75,
            range_advantage='strong',
            pot_size=20.0,
            effective_stack=80.0,
            spr=4.0,
            num_opponents=1,
            board_texture='dry'
        )

        decision = self.gto._aggression_strategy(ctx)

        # 强牌应该下注
        self.assertGreater(decision.get('bet', 0), 0.5, "强牌应该bet")

    def test_aggression_strategy_weak_hand(self):
        """测试主动策略：弱牌"""
        ctx = GTOContext(
            street=Street.FLOP,
            position=Position.BTN,
            is_in_position=True,
            equity=0.25,
            range_advantage='weak',
            pot_size=20.0,
            effective_stack=80.0,
            spr=4.0,
            num_opponents=1,
            board_texture='wet'
        )

        decision = self.gto._aggression_strategy(ctx)

        # 弱牌应该主要check
        self.assertGreater(decision.get('check', 0), 0.6, "弱牌应该主要check")


class TestBetSizing(unittest.TestCase):
    """测试下注尺寸"""

    def setUp(self):
        self.gto = GTOBaseline()

    def test_sizing_by_range_advantage(self):
        """测试范围优势影响尺寸"""
        # 强范围优势 -> 大尺寸
        ctx_strong = GTOContext(
            street=Street.FLOP,
            position=Position.BTN,
            is_in_position=True,
            equity=0.70,
            range_advantage='strong',
            pot_size=20.0,
            effective_stack=80.0,
            spr=4.0,
            num_opponents=1
        )
        size_strong = self.gto.calculate_bet_sizing(ctx_strong)
        self.assertGreater(size_strong, 0.66, "强范围优势应该用大尺寸")

        # 弱范围优势 -> 小尺寸
        ctx_weak = GTOContext(
            street=Street.FLOP,
            position=Position.BTN,
            is_in_position=True,
            equity=0.70,
            range_advantage='weak',
            pot_size=20.0,
            effective_stack=80.0,
            spr=4.0,
            num_opponents=1
        )
        size_weak = self.gto.calculate_bet_sizing(ctx_weak)
        self.assertLess(size_weak, 0.60, "弱范围优势应该用小尺寸")

    def test_sizing_by_board_texture(self):
        """测试牌面湿度影响尺寸"""
        # 湿面 -> 大尺寸保护
        ctx_wet = GTOContext(
            street=Street.FLOP,
            position=Position.BTN,
            is_in_position=True,
            equity=0.70,
            range_advantage='medium',
            pot_size=20.0,
            effective_stack=80.0,
            spr=4.0,
            num_opponents=1,
            board_texture='wet'
        )
        size_wet = self.gto.calculate_bet_sizing(ctx_wet)

        # 干面 -> 小尺寸
        ctx_dry = GTOContext(
            street=Street.FLOP,
            position=Position.BTN,
            is_in_position=True,
            equity=0.70,
            range_advantage='medium',
            pot_size=20.0,
            effective_stack=80.0,
            spr=4.0,
            num_opponents=1,
            board_texture='dry'
        )
        size_dry = self.gto.calculate_bet_sizing(ctx_dry)

        self.assertGreater(size_wet, size_dry, "湿面应该用更大尺寸")


class TestDynamicWeights(unittest.TestCase):
    """测试动态权重系统"""

    def setUp(self):
        self.gto = GTOBaseline()

    def test_preflop_weights(self):
        """测试翻前权重"""
        ctx = GTOContext(
            street=Street.PREFLOP,
            position=Position.BTN,
            is_in_position=True,
            equity=0.60,
            range_advantage='medium',
            pot_size=7.5,
            effective_stack=100.0,
            spr=13.3,
            num_opponents=1
        )

        weights = self.gto.get_decision_weights(ctx)

        # 翻前应该重视position和hand_strength
        self.assertIn('position', weights)
        self.assertIn('hand_strength', weights)
        self.assertGreater(weights['position'], 0.2)

    def test_river_weights(self):
        """测试河牌权重"""
        ctx = GTOContext(
            street=Street.RIVER,
            position=Position.BTN,
            is_in_position=True,
            equity=0.60,
            range_advantage='strong',
            pot_size=50.0,
            effective_stack=50.0,
            spr=1.0,
            num_opponents=1
        )

        weights = self.gto.get_decision_weights(ctx)

        # 河牌应该重视range_advantage和pot_odds
        self.assertIn('range_advantage', weights)
        self.assertIn('pot_odds', weights)
        self.assertGreater(weights['range_advantage'], 0.25)

    def test_shallow_stack_weights(self):
        """测试浅筹码权重"""
        ctx = GTOContext(
            street=Street.FLOP,
            position=Position.BTN,
            is_in_position=True,
            equity=0.60,
            range_advantage='medium',
            pot_size=20.0,
            effective_stack=40.0,
            spr=2.0,
            num_opponents=1
        )

        weights = self.gto.get_decision_weights(ctx)

        # 浅筹码应该重视equity和pot_odds
        self.assertIn('equity', weights)
        self.assertIn('pot_odds', weights)
        self.assertGreater(weights['equity'], 0.30)


def run_tests():
    """运行所有测试"""
    suite = unittest.TestSuite()

    # 添加所有测试
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestGTOFormulas))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestPreflopStrategies))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestPostflopStrategies))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestBetSizing))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestDynamicWeights))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
