"""
GTOStrategy单元测试

测试GTOStrategy的核心决策逻辑，确保：
1. 翻前基于range percentile做决策（NOT hand_strength）
2. 翻后基于equity + range advantage做决策
3. 正确的bet sizing和frequency
4. 生成完整的key_factors（确保模块不被架空）
"""

import unittest
from typing import List

from advisor_v2.strategy.gto_strategy import GTOStrategy
from advisor_v2.core.data_structures import (
    StrategyContext,
    StrategyDecision,
    EquityInfo,
    RangeAdvantage,
    BoardAnalysis,
    Action,
)
from poker_core.cards import Hand, Card
from poker_core.range import Range
from advisor_v2.core.data_structures import Position


class TestGTOStrategyPreflop(unittest.TestCase):
    """测试GTOStrategy的翻前决策"""

    def setUp(self):
        """初始化测试"""
        self.strategy = GTOStrategy()

    def test_preflop_open_premium_hand(self):
        """
        测试翻前open premium hand（AA）

        期望：100% raise
        """
        # 构建context
        hero_hand = Hand.from_str('AsAd')
        hero_range = Range()
        villain_range = Range()

        ctx = StrategyContext(
            street='preflop',
            position=Position.BTN,
            action_history=[],
            pot_size=1.5,
            effective_stack=100.0,
            hero_hand=hero_hand,
            hero_range=hero_range,
            villain_range=villain_range,
            villain_position=Position.BB,
            villain_tendencies={},
        )

        # 决策
        decision = self.strategy.decide(ctx)

        # 验证
        self.assertIsInstance(decision, StrategyDecision)
        self.assertGreater(decision.action_distribution.get('raise', 0), 0.8)
        self.assertIn('hand_percentile', decision.key_factors)
        self.assertEqual(decision.key_factors['street'], 'preflop')
        self.assertEqual(decision.key_factors['strategy'], 'GTOStrategy')

    def test_preflop_open_marginal_hand(self):
        """
        测试翻前open marginal hand（A5o）

        关键测试：
        - advisor: A5o在BTN，hand_strength=0.47 → fold
        - advisor_v2: A5o在BTN range的percentile=0.65 → raise
        """
        hero_hand = Hand.from_str('As5h')
        hero_range = Range()
        villain_range = Range()

        ctx = StrategyContext(
            street='preflop',
            position=Position.BTN,
            action_history=[],
            pot_size=1.5,
            effective_stack=100.0,
            hero_hand=hero_hand,
            hero_range=hero_range,
            villain_range=villain_range,
            villain_position=Position.BB,
            villain_tendencies={},
        )

        decision = self.strategy.decide(ctx)

        # 验证：A5o应该有raise的频率（即使不是100%）
        # 关键是不应该100% fold
        fold_freq = decision.action_distribution.get('fold', 0)
        self.assertLess(fold_freq, 0.50, "A5o at BTN should not fold >50%")

        # 验证key_factors
        self.assertIn('hand_percentile', decision.key_factors)

    def test_preflop_facing_raise_strong_hand(self):
        """
        测试翻前facing raise，strong hand（QQ）

        期望：高频率3bet
        """
        hero_hand = Hand.from_str('QhQd')
        hero_range = Range()
        villain_range = Range()

        # Villain已经raise
        action_history = [
            Action(action='raise', amount=2.5)
        ]

        ctx = StrategyContext(
            street='preflop',
            position=Position.BTN,
            action_history=action_history,
            pot_size=4.0,
            effective_stack=100.0,
            hero_hand=hero_hand,
            hero_range=hero_range,
            villain_range=villain_range,
            villain_position=Position.CO,
            villain_tendencies={},
        )

        decision = self.strategy.decide(ctx)

        # 验证：QQ应该有高频率3bet
        raise_freq = decision.action_distribution.get('raise', 0)
        self.assertGreater(raise_freq, 0.60, "QQ should 3bet >60% vs CO open")

        # 验证key_factors
        self.assertEqual(decision.key_factors['decision_type'], 'facing_raise')
        self.assertIn('facing_bet_size', decision.key_factors)

    def test_preflop_facing_raise_weak_hand(self):
        """
        测试翻前facing raise，weak hand（72o）

        期望：100% fold
        """
        hero_hand = Hand.from_str('7s2h')
        hero_range = Range()
        villain_range = Range()

        action_history = [
            Action(action='raise', amount=2.5)
        ]

        ctx = StrategyContext(
            street='preflop',
            position=Position.BTN,
            action_history=action_history,
            pot_size=4.0,
            effective_stack=100.0,
            hero_hand=hero_hand,
            hero_range=hero_range,
            villain_range=villain_range,
            villain_position=Position.CO,
            villain_tendencies={},
        )

        decision = self.strategy.decide(ctx)

        # 验证：72o应该fold
        fold_freq = decision.action_distribution.get('fold', 0)
        self.assertGreater(fold_freq, 0.80, "72o should fold >80% vs raise")


class TestGTOStrategyPostflop(unittest.TestCase):
    """测试GTOStrategy的翻后决策"""

    def setUp(self):
        """初始化测试"""
        self.strategy = GTOStrategy()

    def test_postflop_value_bet_strong_equity(self):
        """
        测试翻后value bet（strong equity）

        场景：Flop，hero有0.70 equity，应该高频率bet
        """
        hero_hand = Hand.from_str('AsKs')
        board = [Card.from_str('Ah'), Card.from_str('Kh'), Card.from_str('2d')]

        # 构建equity info
        equity_info = EquityInfo(
            point_equity=0.70,
            equity_distribution={
                'crushing': 0.20,
                'strong': 0.40,
                'ahead': 0.25,
                'flip': 0.10,
                'behind': 0.05
            },
            outs=0,
            clean_outs=0,
            implied_odds_factor=1.0
        )

        # Range advantage
        range_advantage = RangeAdvantage(
            advantage_score=0.30,
            advantage_type='range',
            hero_nut_advantage=0.20
        )

        # Board analysis
        board_analysis = BoardAnalysis(
            board=board,
            street='flop',
            texture='dry',
            texture_score=0.25,
            equity_realization_factor=0.90
        )

        ctx = StrategyContext(
            street='flop',
            position=Position.BTN,
            action_history=[],
            pot_size=10.0,
            effective_stack=100.0,
            hero_hand=hero_hand,
            hero_range=Range(),
            villain_range=Range(),
            villain_position=Position.BB,
            villain_tendencies={},
            equity_info=equity_info,
            range_advantage=range_advantage,
            board_analysis=board_analysis,
        )

        decision = self.strategy.decide(ctx)

        # 验证：应该高频率bet
        bet_freq = decision.action_distribution.get('bet', 0)
        self.assertGreater(bet_freq, 0.60, "Should bet >60% with strong equity")

        # 验证sizing
        self.assertGreater(len(decision.sizing_distribution), 0, "Should have sizing")

        # 验证key_factors（确保模块不被架空）
        self.assertIn('point_equity', decision.key_factors)
        self.assertIn('equity_distribution', decision.key_factors)
        self.assertIn('range_advantage_score', decision.key_factors)
        self.assertIn('board_texture', decision.key_factors)
        self.assertEqual(decision.key_factors['point_equity'], 0.70)
        self.assertEqual(decision.key_factors['board_texture'], 'dry')

    def test_postflop_facing_bet_strong_equity(self):
        """
        测试翻后facing bet，strong equity

        场景：Villain bet，hero有0.68 equity，应该raise/call
        """
        hero_hand = Hand.from_str('AsKd')
        board = [Card.from_str('Ah'), Card.from_str('Kh'), Card.from_str('3d')]

        equity_info = EquityInfo(
            point_equity=0.68,
            equity_distribution={
                'crushing': 0.15,
                'strong': 0.35,
                'ahead': 0.30,
                'flip': 0.15,
                'behind': 0.05
            },
            implied_odds_factor=1.0
        )

        range_advantage = RangeAdvantage(
            advantage_score=0.20,
            advantage_type='range'
        )

        board_analysis = BoardAnalysis(
            board=board,
            street='flop',
            texture='dry',
            texture_score=0.20,
            equity_realization_factor=0.90
        )

        action_history = [
            Action(action='bet', amount=6.0)
        ]

        ctx = StrategyContext(
            street='flop',
            position=Position.BTN,
            action_history=action_history,
            pot_size=10.0,
            effective_stack=100.0,
            hero_hand=hero_hand,
            hero_range=Range(),
            villain_range=Range(),
            villain_position=Position.BB,
            villain_tendencies={},
            equity_info=equity_info,
            range_advantage=range_advantage,
            board_analysis=board_analysis,
        )

        decision = self.strategy.decide(ctx)

        # 验证：应该raise或call（不fold）
        fold_freq = decision.action_distribution.get('fold', 0)
        self.assertLess(fold_freq, 0.20, "Should not fold >20% with strong equity")

        # 验证key_factors
        self.assertIn('pot_odds', decision.key_factors)
        self.assertIn('adjusted_equity', decision.key_factors)
        self.assertEqual(decision.key_factors['decision_type'], 'facing_bet')

    def test_postflop_facing_bet_insufficient_equity(self):
        """
        测试翻后facing bet，equity不足

        场景：Villain bet pot，hero只有0.35 equity，应该fold
        """
        hero_hand = Hand.from_str('7s6s')
        board = [Card.from_str('Ah'), Card.from_str('Kh'), Card.from_str('Qd')]

        equity_info = EquityInfo(
            point_equity=0.35,
            equity_distribution={
                'crushing': 0.0,
                'strong': 0.0,
                'ahead': 0.10,
                'flip': 0.30,
                'behind': 0.40,
                'weak': 0.20
            },
            implied_odds_factor=1.0
        )

        board_analysis = BoardAnalysis(
            board=board,
            street='flop',
            texture='dry',
            texture_score=0.15,
            equity_realization_factor=0.85
        )

        action_history = [
            Action(action='bet', amount=10.0)
        ]

        ctx = StrategyContext(
            street='flop',
            position=Position.BTN,
            action_history=action_history,
            pot_size=10.0,
            effective_stack=100.0,
            hero_hand=hero_hand,
            hero_range=Range(),
            villain_range=Range(),
            villain_position=Position.BB,
            villain_tendencies={},
            equity_info=equity_info,
            range_advantage=None,
            board_analysis=board_analysis,
        )

        decision = self.strategy.decide(ctx)

        # 验证：应该fold（可能有少量bluff raise）
        fold_freq = decision.action_distribution.get('fold', 0)
        self.assertGreater(fold_freq, 0.70, "Should fold >70% with insufficient equity")

    def test_postflop_wet_board_equity_realization(self):
        """
        测试翻后wet board的equity realization调整

        场景：OOP在wet board，equity realization降低
        """
        hero_hand = Hand.from_str('9s8s')
        board = [Card.from_str('Ts'), Card.from_str('7s'), Card.from_str('6h')]  # Wet board (flush draw + straight draw)

        equity_info = EquityInfo(
            point_equity=0.55,
            equity_distribution={
                'ahead': 0.40,
                'flip': 0.35,
                'behind': 0.25
            },
            implied_odds_factor=1.2,  # Draws有implied odds
            outs=15
        )

        board_analysis = BoardAnalysis(
            board=board,
            street='flop',
            texture='wet',
            texture_score=0.80,
            draw_heavy=True,
            flush_draw_possible=True,
            straight_draw_possible=True,
            equity_realization_factor=0.75  # OOP在wet board实现率低
        )

        action_history = [
            Action(action='bet', amount=7.0)
        ]

        ctx = StrategyContext(
            street='flop',
            position=Position.BB,  # OOP
            action_history=action_history,
            pot_size=10.0,
            effective_stack=100.0,
            hero_hand=hero_hand,
            hero_range=Range(),
            villain_range=Range(),
            villain_position=Position.BTN,
            villain_tendencies={},
            equity_info=equity_info,
            range_advantage=None,
            board_analysis=board_analysis,
        )

        decision = self.strategy.decide(ctx)

        # 验证：equity被调整（implied odds提升，但equity realization降低）
        # adjusted_equity应该在key_factors中
        self.assertIn('equity_realization_factor', decision.key_factors)
        self.assertIn('implied_odds_factor', decision.key_factors)
        self.assertEqual(decision.key_factors['equity_realization_factor'], 0.75)


class TestGTOStrategyDecisionValidation(unittest.TestCase):
    """测试GTOStrategy决策的有效性验证"""

    def setUp(self):
        """初始化测试"""
        self.strategy = GTOStrategy()

    def test_action_distribution_sums_to_one(self):
        """
        测试action_distribution总和为1
        """
        hero_hand = Hand.from_str('AsKs')
        hero_range = Range()
        villain_range = Range()

        ctx = StrategyContext(
            street='preflop',
            position=Position.BTN,
            action_history=[],
            pot_size=1.5,
            effective_stack=100.0,
            hero_hand=hero_hand,
            hero_range=hero_range,
            villain_range=villain_range,
            villain_position=Position.BB,
            villain_tendencies={},
        )

        decision = self.strategy.decide(ctx)

        # 验证总和
        total = sum(decision.action_distribution.values())
        self.assertAlmostEqual(total, 1.0, places=2, msg="Action distribution should sum to 1.0")

    def test_sizing_distribution_sums_to_one(self):
        """
        测试sizing_distribution总和为1（如果存在）
        """
        hero_hand = Hand.from_str('AsKd')
        board = [Card.from_str('Ah'), Card.from_str('Kh'), Card.from_str('2d')]

        equity_info = EquityInfo(
            point_equity=0.70,
            equity_distribution={'ahead': 0.70, 'behind': 0.30}
        )

        ctx = StrategyContext(
            street='flop',
            position=Position.BTN,
            action_history=[],
            pot_size=10.0,
            effective_stack=100.0,
            hero_hand=hero_hand,
            hero_range=Range(),
            villain_range=Range(),
            villain_position=Position.BB,
            villain_tendencies={},
            equity_info=equity_info,
        )

        decision = self.strategy.decide(ctx)

        # 如果有sizing，验证总和
        if decision.sizing_distribution:
            total = sum(decision.sizing_distribution.values())
            self.assertAlmostEqual(total, 1.0, places=2, msg="Sizing distribution should sum to 1.0")

    def test_key_factors_populated(self):
        """
        测试key_factors被正确填充（确保模块不被架空）
        """
        hero_hand = Hand.from_str('AsKd')
        board = [Card.from_str('Ah'), Card.from_str('Kh'), Card.from_str('2d')]

        equity_info = EquityInfo(
            point_equity=0.68,
            equity_distribution={'ahead': 0.65, 'behind': 0.35}
        )

        range_advantage = RangeAdvantage(
            advantage_score=0.25,
            advantage_type='range'
        )

        board_analysis = BoardAnalysis(
            board=board,
            street='flop',
            texture='dry',
            texture_score=0.20
        )

        ctx = StrategyContext(
            street='flop',
            position=Position.BTN,
            action_history=[],
            pot_size=10.0,
            effective_stack=100.0,
            hero_hand=hero_hand,
            hero_range=Range(),
            villain_range=Range(),
            villain_position=Position.BB,
            villain_tendencies={},
            equity_info=equity_info,
            range_advantage=range_advantage,
            board_analysis=board_analysis,
        )

        decision = self.strategy.decide(ctx)

        # 验证key_factors包含关键信息
        required_keys = ['strategy', 'street', 'decision_type']
        for key in required_keys:
            self.assertIn(key, decision.key_factors, f"Missing key: {key}")

        # 翻后应该包含equity信息
        self.assertIn('point_equity', decision.key_factors)
        self.assertIn('equity_distribution', decision.key_factors)

    def test_missing_equity_info_defensive_decision(self):
        """
        测试缺少equity_info时的defensive决策
        """
        hero_hand = Hand.from_str('AsKd')
        board = [Card.from_str('Ah'), Card.from_str('Kh'), Card.from_str('2d')]

        ctx = StrategyContext(
            street='flop',
            position=Position.BTN,
            action_history=[],
            pot_size=10.0,
            effective_stack=100.0,
            hero_hand=hero_hand,
            hero_range=Range(),
            villain_range=Range(),
            villain_position=Position.BB,
            villain_tendencies={},
            equity_info=None,  # 缺少equity info
        )

        decision = self.strategy.decide(ctx)

        # 验证：应该check（defensive）
        check_freq = decision.action_distribution.get('check', 0)
        self.assertEqual(check_freq, 1.0, "Should check when equity_info is missing")
        self.assertEqual(decision.key_factors['decision_type'], 'defensive')


class TestGTOStrategyInterface(unittest.TestCase):
    """测试GTOStrategy的接口实现"""

    def test_get_name(self):
        """测试get_name()"""
        strategy = GTOStrategy()
        self.assertEqual(strategy.get_name(), "GTOStrategy")

    def test_reset(self):
        """测试reset()（无状态策略，应该不报错）"""
        strategy = GTOStrategy()
        strategy.reset()  # 应该不报错


if __name__ == '__main__':
    unittest.main()
