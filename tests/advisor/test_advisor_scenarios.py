#!/usr/bin/env python
"""
Advisor Scenario Tests - 关键场景验证

验证CRITICAL_BUGS.md中提到的问题已修复:
1. QQ vs LAG 3-bet → 不应该fold
2. AA preflop → 应该激进
3. 72o UTG → 应该fold
4. Equity被正确使用
5. Pot odds计算正确

还包含其他重要场景测试
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import unittest
from advisor.strategy_engine import ProLevelAdvisor, GameState, create_advisor
from advisor.range_engine import Hand, Board
from advisor.opponent_modeling import PlayerType


class TestCriticalBugFixes(unittest.TestCase):
    """
    测试CRITICAL_BUGS.md中的所有bug已修复

    这些是最重要的测试，必须全部通过
    """

    def setUp(self):
        self.advisor = create_advisor(exploit_weight=0.4)

    def test_bug_fix_qq_vs_lag_3bet(self):
        """
        Bug修复验证: QQ vs LAG 3-bet

        原Bug: QQ被建议fold 60%
        修复后: QQ应该call或4-bet
        """
        gs = GameState(
            street='preflop',
            position='BTN',
            is_in_position=True,
            hero_hand=Hand.from_str('QsQh'),
            pot_size=10.0,
            effective_stack=100.0,
            hero_stack=100.0,
            facing_bet=7.5,
            bet_to_call=7.5,
            action_history=['open', '3bet'],
            opponent_type=PlayerType.LAG
        )

        decision = self.advisor.advise(gs)

        # QQ vs LAG 3-bet不应该fold
        fold_freq = decision.action_distribution.get('fold', 1.0)
        call_4bet_freq = decision.action_distribution.get('call', 0) + decision.action_distribution.get('4bet', 0)

        self.assertLess(fold_freq, 0.3, f"QQ vs LAG 3-bet不应该fold！fold_freq={fold_freq:.2%}")
        self.assertGreater(call_4bet_freq, 0.7, f"QQ应该call或4-bet！call+4bet={call_4bet_freq:.2%}")

    def test_bug_fix_aa_aggression(self):
        """
        Bug修复验证: AA应该激进

        原Bug: 所有手牌strength=0.7
        修复后: AA strength应该>0.95
        """
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
        raise_freq = decision.action_distribution.get('raise', 0.0)
        self.assertGreater(raise_freq, 0.85, f"AA应该raise >85%！raise_freq={raise_freq:.2%}")

    def test_bug_fix_72o_fold(self):
        """
        Bug修复验证: 72o应该fold

        原Bug: 所有手牌strength=0.7
        修复后: 72o strength应该<0.20
        """
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
        fold_freq = decision.action_distribution.get('fold', 0.0)
        self.assertGreater(fold_freq, 0.85, f"72o在UTG应该fold >85%！fold_freq={fold_freq:.2%}")

    def test_bug_fix_equity_used(self):
        """
        Bug修复验证: Equity被使用

        原Bug: Equity计算但不用
        修复后: 决策应该基于equity
        """
        # JJ vs TAG 3-bet
        gs = GameState(
            street='preflop',
            position='CO',
            is_in_position=True,
            hero_hand=Hand.from_str('JhJd'),
            pot_size=10.0,
            effective_stack=100.0,
            hero_stack=100.0,
            facing_bet=7.5,
            bet_to_call=7.5,
            action_history=['open', '3bet'],
            opponent_type=PlayerType.TAG
        )

        decision = self.advisor.advise(gs)

        # 检查equity在reasoning中
        self.assertIn('equity', decision.reasoning, "Equity应该在reasoning中")
        equity = decision.reasoning['equity']
        self.assertGreater(equity, 0, "Equity应该被计算")

        # JJ vs TAG 3-bet的equity应该在42-52%之间，接近pot odds
        # 决策应该混合call/fold
        fold_freq = decision.action_distribution.get('fold', 1.0)
        self.assertLess(fold_freq, 0.7, f"JJ不应该总是fold！fold_freq={fold_freq:.2%}")

    def test_bug_fix_pot_odds_formula(self):
        """
        Bug修复验证: Pot odds公式正确

        原Bug: pot_odds = pot / (pot + call) [错误]
        修复后: pot_odds = call / (pot + call) [正确]
        """
        gs = GameState(
            street='flop',
            position='BB',
            is_in_position=False,
            hero_hand=Hand.from_str('KhQd'),
            board=Board.from_str('As9c3h'),
            pot_size=20.0,
            effective_stack=80.0,
            hero_stack=80.0,
            facing_bet=15.0,
            bet_to_call=15.0,
            action_history=['bet']
        )

        decision = self.advisor.advise(gs)

        # 检查pot odds计算
        pot_odds = decision.reasoning.get('pot_odds', 0)
        expected_pot_odds = 15.0 / (20.0 + 15.0)  # = 0.4286

        self.assertAlmostEqual(pot_odds, expected_pot_odds, places=2,
                              msg=f"Pot odds应该是{expected_pot_odds:.2%}，实际是{pot_odds:.2%}")


class TestPreflopScenarios(unittest.TestCase):
    """翻前场景测试"""

    def setUp(self):
        self.advisor = create_advisor(exploit_weight=0.4)

    def test_btn_steal_vs_tight_blinds(self):
        """BTN偷盲 vs紧的盲注"""
        gs = GameState(
            street='preflop',
            position='BTN',
            is_in_position=True,
            hero_hand=Hand.from_str('Kh9d'),
            pot_size=1.5,
            effective_stack=100.0,
            hero_stack=100.0,
            action_history=[]
        )

        decision = self.advisor.advise(gs)

        # K9o在BTN应该open
        raise_freq = decision.action_distribution.get('raise', 0.0)
        self.assertGreater(raise_freq, 0.5, "K9o在BTN应该open")

    def test_bb_vs_btn_steal(self):
        """BB防守BTN偷盲"""
        gs = GameState(
            street='preflop',
            position='BB',
            is_in_position=False,
            hero_hand=Hand.from_str('Ah7d'),
            pot_size=5.0,
            effective_stack=97.5,
            hero_stack=97.5,
            facing_bet=2.5,
            bet_to_call=2.5,
            action_history=['open'],
            opponent_type=PlayerType.LAG  # LAG偷盲范围宽
        )

        decision = self.advisor.advise(gs)

        # A7o vs LAG偷盲应该defend
        fold_freq = decision.action_distribution.get('fold', 1.0)
        self.assertLess(fold_freq, 0.5, "A7o vs LAG偷盲应该defend")

    def test_sb_complete_vs_fold(self):
        """SB补盲 vs弃牌"""
        # 弱牌应该fold
        gs_weak = GameState(
            street='preflop',
            position='SB',
            is_in_position=False,
            hero_hand=Hand.from_str('9c4d'),
            pot_size=1.5,
            effective_stack=99.5,
            hero_stack=99.5,
            action_history=[]
        )

        decision_weak = self.advisor.advise(gs_weak)
        fold_freq_weak = decision_weak.action_distribution.get('fold', 0.0)
        self.assertGreater(fold_freq_weak, 0.6, "94o在SB应该fold")


class TestPostflopScenarios(unittest.TestCase):
    """翻后场景测试"""

    def setUp(self):
        self.advisor = create_advisor(exploit_weight=0.5)  # 更多exploit

    def test_cbet_dry_board_ip(self):
        """干燥面C-bet (有位置)"""
        gs = GameState(
            street='flop',
            position='BTN',
            is_in_position=True,
            hero_hand=Hand.from_str('AsKd'),
            board=Board.from_str('Ah9c3d'),
            pot_size=15.0,
            effective_stack=85.0,
            hero_stack=85.0,
            action_history=['open', 'call']  # 翻前open, 对手call
        )

        decision = self.advisor.advise(gs)

        # 干燥面TPTK应该c-bet
        bet_freq = decision.action_distribution.get('bet', 0.0)
        self.assertGreater(bet_freq, 0.7, "TPTK干燥面应该c-bet")

    def test_defense_vs_cbet_with_pair(self):
        """防守C-bet (有对子)"""
        gs = GameState(
            street='flop',
            position='BB',
            is_in_position=False,
            hero_hand=Hand.from_str('Th9d'),
            board=Board.from_str('Ts6c2h'),
            pot_size=15.0,
            effective_stack=85.0,
            hero_stack=85.0,
            facing_bet=10.0,
            bet_to_call=10.0,
            action_history=['open', 'call', 'bet']
        )

        decision = self.advisor.advise(gs)

        # Top pair应该call
        fold_freq = decision.action_distribution.get('fold', 1.0)
        self.assertLess(fold_freq, 0.3, "Top pair不应该fold")

    def test_vs_fish_wider_valuebet(self):
        """vs Fish更宽的价值下注"""
        gs = GameState(
            street='flop',
            position='BTN',
            is_in_position=True,
            hero_hand=Hand.from_str('KhQd'),
            board=Board.from_str('Kc9s4h'),
            pot_size=15.0,
            effective_stack=85.0,
            hero_stack=85.0,
            opponent_type=PlayerType.FISH
        )

        decision = self.advisor.advise(gs)

        # vs Fish，top pair应该下注
        bet_freq = decision.action_distribution.get('bet', 0.0)
        self.assertGreater(bet_freq, 0.6, "vs Fish应该更多价值下注")


class TestExploitScenarios(unittest.TestCase):
    """Exploit场景测试"""

    def setUp(self):
        self.advisor = create_advisor(exploit_weight=0.6)  # 高exploit

    def test_vs_nit_fold_to_aggression(self):
        """vs Nit面对下注应该fold"""
        gs = GameState(
            street='flop',
            position='BB',
            is_in_position=False,
            hero_hand=Hand.from_str('Qh9d'),
            board=Board.from_str('Ac8c3h'),
            pot_size=20.0,
            effective_stack=80.0,
            hero_stack=80.0,
            facing_bet=15.0,
            bet_to_call=15.0,
            opponent_type=PlayerType.NIT
        )

        decision = self.advisor.advise(gs)

        # vs Nit的下注，弱牌应该fold
        fold_freq = decision.action_distribution.get('fold', 0.0)
        self.assertGreater(fold_freq, 0.5, "vs Nit下注应该more respect")

    def test_vs_calling_station_valuebet_thin(self):
        """vs Calling Station薄价值下注"""
        gs = GameState(
            street='river',
            position='BTN',
            is_in_position=True,
            hero_hand=Hand.from_str('AhJd'),
            board=Board.from_str('As9c4h2d7s'),
            pot_size=50.0,
            effective_stack=50.0,
            hero_stack=50.0,
            opponent_type=PlayerType.CALLING_STATION
        )

        decision = self.advisor.advise(gs)

        # vs Calling Station，one pair应该价值下注
        bet_freq = decision.action_distribution.get('bet', 0.0)
        self.assertGreater(bet_freq, 0.5, "vs Calling Station应该薄价值下注")


class TestMultiwayPots(unittest.TestCase):
    """多人底池测试"""

    def setUp(self):
        self.advisor = create_advisor()

    def test_multiway_tighten_up(self):
        """多人底池应该收紧"""
        # 单挑
        gs_hu = GameState(
            street='preflop',
            position='BTN',
            is_in_position=True,
            hero_hand=Hand.from_str('JhTs'),
            pot_size=7.5,
            effective_stack=100.0,
            hero_stack=100.0,
            num_opponents=1,
            action_history=['open']
        )

        # 3人底池
        gs_3way = GameState(
            street='preflop',
            position='BTN',
            is_in_position=True,
            hero_hand=Hand.from_str('JhTs'),
            pot_size=10.0,
            effective_stack=100.0,
            hero_stack=100.0,
            num_opponents=2,
            action_history=['open', 'call']
        )

        decision_hu = self.advisor.advise(gs_hu)
        decision_3way = self.advisor.advise(gs_3way)

        # 多人底池fold频率应该更高
        fold_hu = decision_hu.action_distribution.get('fold', 0)
        fold_3way = decision_3way.action_distribution.get('fold', 0)

        # 由于equity在多人底池下降，应该更保守
        self.assertGreaterEqual(fold_3way, fold_hu * 0.8,
                               "多人底池应该更保守（fold频率接近或更高）")


def run_tests():
    """运行所有测试"""
    suite = unittest.TestSuite()

    # 添加所有测试
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestCriticalBugFixes))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestPreflopScenarios))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestPostflopScenarios))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestExploitScenarios))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestMultiwayPots))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
