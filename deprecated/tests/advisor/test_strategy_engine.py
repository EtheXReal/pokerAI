#!/usr/bin/env python
"""
Strategy Engine 单元测试

测试:
1. DecisionOutput结构正确性
2. ProLevelAdvisor基础功能
3. 动态权重计算
4. 尺寸建议
5. 上下文感知精度
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import unittest
from advisor.strategy_engine import (
    DecisionOutput, merge_decisions,
    ProLevelAdvisor, GameState, create_advisor
)
from poker_core import Hand, Board
from advisor.opponent_modeling import PlayerType, OpponentStats


class TestDecisionOutput(unittest.TestCase):
    """测试DecisionOutput结构"""

    def test_basic_structure(self):
        """测试基础结构"""
        decision = DecisionOutput(
            action_distribution={'fold': 0.2, 'call': 0.6, 'raise': 0.2},
            recommended_action='call',
            reasoning={'test': 'reason'},
            confidence=0.85
        )

        self.assertEqual(decision.recommended_action, 'call')
        self.assertEqual(decision.confidence, 0.85)
        self.assertAlmostEqual(decision.action_distribution['call'], 0.6)

    def test_merge_decisions(self):
        """测试决策合并"""
        d1 = DecisionOutput(
            action_distribution={'fold': 0.3, 'call': 0.5, 'raise': 0.2},
            recommended_action='call',
            reasoning={},
            confidence=0.8
        )
        d2 = DecisionOutput(
            action_distribution={'fold': 0.1, 'call': 0.4, 'raise': 0.5},
            recommended_action='raise',
            reasoning={},
            confidence=0.9
        )

        merged = merge_decisions(
            {'gto': d1, 'exploit': d2},
            {'gto': 0.6, 'exploit': 0.4}
        )

        # 检查概率分布
        self.assertAlmostEqual(
            merged.action_distribution['call'],
            0.5 * 0.6 + 0.4 * 0.4,
            places=2
        )

        # 检查推荐动作是概率最高的
        max_action = max(merged.action_distribution, key=merged.action_distribution.get)
        self.assertEqual(merged.recommended_action, max_action)


class TestGameState(unittest.TestCase):
    """测试GameState结构"""

    def test_basic_gamestate(self):
        """测试基础GameState创建"""
        gs = GameState(
            street='preflop',
            position='BTN',
            is_in_position=True,
            hero_hand=Hand.from_str('AsKd'),
            pot_size=7.5,
            effective_stack=100.0,
            hero_stack=100.0
        )

        self.assertEqual(gs.street, 'preflop')
        self.assertEqual(gs.position, 'BTN')
        self.assertTrue(gs.is_in_position)
        self.assertIsNotNone(gs.spr)

    def test_spr_calculation(self):
        """测试SPR自动计算"""
        gs = GameState(
            street='preflop',
            position='BTN',
            is_in_position=True,
            hero_hand=Hand.from_str('AsKd'),
            pot_size=10.0,
            effective_stack=50.0,
            hero_stack=50.0
        )

        self.assertAlmostEqual(gs.spr, 5.0, places=1)

    def test_facing_bet_fields(self):
        """测试facing_bet字段"""
        gs = GameState(
            street='preflop',
            position='BB',
            is_in_position=False,
            hero_hand=Hand.from_str('QsQh'),
            pot_size=10.0,
            effective_stack=100.0,
            hero_stack=100.0,
            facing_bet=7.5,
            bet_to_call=7.5,
            action_history=['open', '3bet']
        )

        self.assertEqual(gs.facing_bet, 7.5)
        self.assertEqual(gs.bet_to_call, 7.5)
        self.assertEqual(len(gs.action_history), 2)


class TestProLevelAdvisor(unittest.TestCase):
    """测试ProLevelAdvisor核心功能"""

    def setUp(self):
        self.advisor = create_advisor(exploit_weight=0.4)

    def test_advisor_creation(self):
        """测试advisor创建"""
        self.assertIsNotNone(self.advisor)
        self.assertAlmostEqual(self.advisor.exploit_weight, 0.4, places=1)
        self.assertAlmostEqual(self.advisor.gto_weight, 0.6, places=1)

    def test_preflop_decision_structure(self):
        """测试翻前决策输出结构"""
        gs = GameState(
            street='preflop',
            position='BTN',
            is_in_position=True,
            hero_hand=Hand.from_str('AsAh'),
            pot_size=7.5,
            effective_stack=100.0,
            hero_stack=100.0,
            action_history=[]
        )

        decision = self.advisor.advise(gs)

        # 检查输出结构
        self.assertIsInstance(decision, DecisionOutput)
        self.assertIsNotNone(decision.action_distribution)
        self.assertIsNotNone(decision.recommended_action)
        self.assertIsInstance(decision.confidence, float)
        self.assertGreater(decision.confidence, 0.0)
        self.assertLessEqual(decision.confidence, 1.0)

    def test_aa_preflop_aggression(self):
        """测试AA翻前应该激进"""
        gs = GameState(
            street='preflop',
            position='BTN',
            is_in_position=True,
            hero_hand=Hand.from_str('AsAh'),
            pot_size=7.5,
            effective_stack=100.0,
            hero_stack=100.0,
            action_history=[]
        )

        decision = self.advisor.advise(gs)

        # AA应该主要raise
        self.assertGreater(
            decision.action_distribution.get('raise', 0.0),
            0.8,
            "AA应该raise >80%"
        )

    def test_72o_preflop_fold(self):
        """测试72o翻前应该弃牌"""
        gs = GameState(
            street='preflop',
            position='UTG',
            is_in_position=False,
            hero_hand=Hand.from_str('7c2d'),
            pot_size=1.5,
            effective_stack=100.0,
            hero_stack=100.0,
            action_history=[]
        )

        decision = self.advisor.advise(gs)

        # 72o应该主要fold
        self.assertGreater(
            decision.action_distribution.get('fold', 0.0),
            0.8,
            "72o在UTG应该fold >80%"
        )

    def test_dynamic_weights_low_sample(self):
        """测试动态权重：样本少 -> 更GTO"""
        gs = GameState(
            street='preflop',
            position='BTN',
            is_in_position=True,
            hero_hand=Hand.from_str('AsKd'),
            pot_size=7.5,
            effective_stack=100.0,
            hero_stack=100.0,
            opponent_stats=OpponentStats(player_id='test', hands_played=10)  # 样本少
        )

        weights = self.advisor._calculate_dynamic_weights(gs)

        # 样本少应该更依赖GTO
        self.assertGreater(weights['gto'], weights['exploit'])

    def test_dynamic_weights_shallow_stack(self):
        """测试动态权重：浅筹码 -> 更GTO"""
        gs = GameState(
            street='preflop',
            position='BTN',
            is_in_position=True,
            hero_hand=Hand.from_str('AsKd'),
            pot_size=20.0,
            effective_stack=40.0,  # SPR = 2
            hero_stack=40.0
        )

        weights = self.advisor._calculate_dynamic_weights(gs)

        # 浅筹码应该更依赖GTO
        self.assertGreater(weights['gto'], weights['exploit'])

    def test_context_aware_iterations(self):
        """测试上下文感知的迭代次数"""
        # 场景1: 翻前深筹码 -> 1000
        gs1 = GameState(
            street='preflop',
            position='BTN',
            is_in_position=True,
            hero_hand=Hand.from_str('AsKd'),
            pot_size=7.5,
            effective_stack=200.0,
            hero_stack=200.0
        )
        iterations1 = self.advisor._get_iterations(gs1, 0.5)
        self.assertEqual(iterations1, 1000)

        # 场景2: 小底池 + 浅筹码 (SPR < 10) -> 300
        gs2 = GameState(
            street='preflop',
            position='BTN',
            is_in_position=True,
            hero_hand=Hand.from_str('AsKd'),
            pot_size=3.0,
            effective_stack=20.0,  # SPR = 20/3 = 6.7 < 10
            hero_stack=20.0
        )
        iterations2 = self.advisor._get_iterations(gs2, 0.5)
        self.assertEqual(iterations2, 300)

        # 场景3: 边缘决策 -> 1000
        gs3 = GameState(
            street='preflop',
            position='BTN',
            is_in_position=True,
            hero_hand=Hand.from_str('AsKd'),
            pot_size=10.0,
            effective_stack=100.0,
            hero_stack=100.0
        )
        iterations3 = self.advisor._get_iterations(gs3, 0.50)  # 边缘
        self.assertEqual(iterations3, 1000)

        # 场景4: 明显决策 -> 300
        iterations4 = self.advisor._get_iterations(gs3, 0.80)  # 明显
        self.assertEqual(iterations4, 300)


class TestExploitAdjustments(unittest.TestCase):
    """测试Exploit调整"""

    def setUp(self):
        self.advisor = create_advisor(exploit_weight=0.6)  # 更高的exploit权重

    def test_vs_fish_wider_valuebet(self):
        """测试vs Fish应该用更宽的价值下注范围"""
        gs = GameState(
            street='flop',
            position='BTN',
            is_in_position=True,
            hero_hand=Hand.from_str('AhTd'),
            board=Board.from_str('As9c3h'),
            pot_size=15.0,
            effective_stack=85.0,
            hero_stack=85.0,
            opponent_type=PlayerType.FISH
        )

        decision = self.advisor.advise(gs)

        # vs Fish，TPTK应该下注
        bet_freq = decision.action_distribution.get('bet', 0.0)
        self.assertGreater(bet_freq, 0.5, "vs Fish应该更多价值下注")

    def test_vs_nit_fold_more(self):
        """测试vs Nit面对下注应该更多fold"""
        gs = GameState(
            street='flop',
            position='BB',
            is_in_position=False,
            hero_hand=Hand.from_str('Kh9d'),
            board=Board.from_str('Ac8c3h'),
            pot_size=20.0,
            effective_stack=80.0,
            hero_stack=80.0,
            facing_bet=15.0,
            bet_to_call=15.0,
            opponent_type=PlayerType.NIT
        )

        decision = self.advisor.advise(gs)

        # vs Nit下注，弱牌应该fold
        fold_freq = decision.action_distribution.get('fold', 0.0)
        # Nit很少bluff，我们应该respect他们的下注
        self.assertGreater(fold_freq, 0.3, "vs Nit的下注应该更respect")


class TestSizingRecommendations(unittest.TestCase):
    """测试下注尺寸建议"""

    def setUp(self):
        self.advisor = create_advisor()

    def test_sizing_options_provided(self):
        """测试尺寸选项被提供"""
        gs = GameState(
            street='flop',
            position='BTN',
            is_in_position=True,
            hero_hand=Hand.from_str('AsAh'),
            board=Board.from_str('Kh9c3d'),
            pot_size=15.0,
            effective_stack=85.0,
            hero_stack=85.0
        )

        decision = self.advisor.advise(gs)

        if 'bet' in decision.recommended_action or 'raise' in decision.recommended_action:
            self.assertIsNotNone(decision.sizing_options, "应该提供尺寸选项")
            self.assertIsNotNone(decision.optimal_sizing, "应该提供最优尺寸")

    def test_vs_fish_larger_sizing(self):
        """测试vs Fish应该用更大的尺寸"""
        gs_fish = GameState(
            street='flop',
            position='BTN',
            is_in_position=True,
            hero_hand=Hand.from_str('AsAh'),
            board=Board.from_str('Kh9c3d'),
            pot_size=15.0,
            effective_stack=85.0,
            hero_stack=85.0,
            opponent_type=PlayerType.FISH
        )

        decision = self.advisor.advise(gs_fish)

        if decision.optimal_sizing:
            # vs Fish的尺寸应该 >= 75% pot
            sizing_pct = decision.optimal_sizing / gs_fish.pot_size
            self.assertGreaterEqual(sizing_pct, 0.66, "vs Fish应该用更大尺寸")


def run_tests():
    """运行所有测试"""
    suite = unittest.TestSuite()

    # 添加所有测试
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestDecisionOutput))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestGameState))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestProLevelAdvisor))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestExploitAdjustments))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestSizingRecommendations))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
