#!/usr/bin/env python
"""
StatsTracker 单元测试

测试:
1. ActionParser 解析行动序列
2. StatsTracker 基础功能
3. 多玩家追踪
4. 批量更新
5. 序列化和反序列化
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import unittest
from advisor.opponent_modeling import (
    StatsTracker,
    ActionParser,
    create_tracker,
    PositionType,
    StreetType,
    ActionType,
)


class TestActionParser(unittest.TestCase):
    """测试ActionParser"""

    def test_parse_simple_vpip(self):
        """测试解析简单的VPIP"""
        actions = [
            {'street': 'preflop', 'actor': 'player1', 'action': 'call', 'amount': 1.0},
        ]

        result = ActionParser.parse_hand_actions(actions, 'player1')

        self.assertTrue(result.vpip, "Call应该算VPIP")
        self.assertFalse(result.pfr, "Call不算PFR")

    def test_parse_pfr(self):
        """测试解析PFR"""
        actions = [
            {'street': 'preflop', 'actor': 'player1', 'action': 'raise', 'amount': 3.0},
        ]

        result = ActionParser.parse_hand_actions(actions, 'player1')

        self.assertTrue(result.vpip, "Raise应该算VPIP")
        self.assertTrue(result.pfr, "Raise算PFR")

    def test_parse_3bet(self):
        """测试解析3-bet"""
        actions = [
            {'street': 'preflop', 'actor': 'player1', 'action': 'raise', 'amount': 3.0},
            {'street': 'preflop', 'actor': 'player2', 'action': 'raise', 'amount': 9.0},
        ]

        result = ActionParser.parse_hand_actions(actions, 'player2')

        self.assertTrue(result.vpip)
        self.assertTrue(result.pfr)
        self.assertTrue(result.three_bet, "第二次加注应该是3-bet")

    def test_parse_4bet(self):
        """测试解析4-bet"""
        actions = [
            {'street': 'preflop', 'actor': 'player1', 'action': 'raise', 'amount': 3.0},
            {'street': 'preflop', 'actor': 'player2', 'action': 'raise', 'amount': 9.0},
            {'street': 'preflop', 'actor': 'player1', 'action': 'raise', 'amount': 24.0},
        ]

        result = ActionParser.parse_hand_actions(actions, 'player1')

        self.assertTrue(result.four_bet, "第三次加注应该是4-bet")

    def test_parse_cbet(self):
        """测试解析C-bet"""
        actions = [
            {'street': 'preflop', 'actor': 'player1', 'action': 'raise', 'amount': 3.0},
            {'street': 'preflop', 'actor': 'player2', 'action': 'call', 'amount': 3.0},
            {'street': 'flop', 'actor': 'player1', 'action': 'bet', 'amount': 6.0},
        ]

        result = ActionParser.parse_hand_actions(actions, 'player1')

        self.assertTrue(result.saw_flop)
        self.assertTrue(result.cbet_flop, "翻前加注者翻牌圈下注应该算c-bet")

    def test_parse_no_cbet(self):
        """测试没有c-bet的情况"""
        actions = [
            {'street': 'preflop', 'actor': 'player1', 'action': 'raise', 'amount': 3.0},
            {'street': 'preflop', 'actor': 'player2', 'action': 'call', 'amount': 3.0},
            {'street': 'flop', 'actor': 'player1', 'action': 'check', 'amount': 0},
            {'street': 'flop', 'actor': 'player2', 'action': 'bet', 'amount': 6.0},
        ]

        result = ActionParser.parse_hand_actions(actions, 'player1')

        self.assertTrue(result.saw_flop)
        self.assertFalse(result.cbet_flop, "Check后没有下注不算c-bet")


class TestStatsTracker(unittest.TestCase):
    """测试StatsTracker基础功能"""

    def test_create_tracker(self):
        """测试创建追踪器"""
        tracker = create_tracker()

        self.assertIsNotNone(tracker)
        self.assertEqual(tracker.get_player_count(), 0)

    def test_get_stats_auto_create(self):
        """测试获取统计时自动创建"""
        tracker = create_tracker()

        stats = tracker.get_stats('player1')

        self.assertIsNotNone(stats)
        self.assertEqual(stats.player_id, 'player1')
        self.assertEqual(stats.hands_played, 0)
        self.assertEqual(tracker.get_player_count(), 1)

    def test_update_from_simple_hand(self):
        """测试从简单手牌更新"""
        tracker = create_tracker()

        # 构造简单手牌历史
        hand_history = {
            'hand_id': 'h001',
            'players': [
                {'id': 'player1', 'pos': 'BTN'},
                {'id': 'player2', 'pos': 'BB'},
            ],
            'actions': [
                {'street': 'preflop', 'actor': 'player1', 'action': 'raise', 'amount': 3.0},
                {'street': 'preflop', 'actor': 'player2', 'action': 'call', 'amount': 3.0},
            ],
            'winners': [{'seat': 'player1', 'amount': 6.0}],
            'showdown': False,
        }

        tracker.update_from_hand(hand_history)

        # 验证player1的统计
        stats1 = tracker.get_stats('player1')
        self.assertEqual(stats1.hands_played, 1)
        self.assertTrue(stats1.vpip > 0)
        self.assertTrue(stats1.pfr > 0)

        # 验证player2的统计
        stats2 = tracker.get_stats('player2')
        self.assertEqual(stats2.hands_played, 1)
        self.assertTrue(stats2.vpip > 0)
        self.assertFalse(stats2.pfr > 0)


class TestMultiPlayerTracking(unittest.TestCase):
    """测试多玩家追踪"""

    def test_track_multiple_players(self):
        """测试同时追踪多个玩家"""
        tracker = create_tracker()

        # 模拟5手牌，3个玩家
        for i in range(5):
            hand_history = {
                'hand_id': f'h{i:03d}',
                'players': [
                    {'id': 'alice', 'pos': 'BTN'},
                    {'id': 'bob', 'pos': 'SB'},
                    {'id': 'charlie', 'pos': 'BB'},
                ],
                'actions': [
                    {'street': 'preflop', 'actor': 'alice', 'action': 'raise', 'amount': 3.0},
                    {'street': 'preflop', 'actor': 'bob', 'action': 'fold', 'amount': 0},
                    {'street': 'preflop', 'actor': 'charlie', 'action': 'call', 'amount': 3.0},
                ],
                'winners': [{'seat': 'alice', 'amount': 6.5}],
                'showdown': False,
            }
            tracker.update_from_hand(hand_history)

        # 验证追踪了3个玩家
        self.assertEqual(tracker.get_player_count(), 3)

        # 验证每个玩家都有5手牌
        stats_alice = tracker.get_stats('alice')
        stats_bob = tracker.get_stats('bob')
        stats_charlie = tracker.get_stats('charlie')

        self.assertEqual(stats_alice.hands_played, 5)
        self.assertEqual(stats_bob.hands_played, 5)
        self.assertEqual(stats_charlie.hands_played, 5)

    def test_avoid_duplicate_processing(self):
        """测试避免重复处理相同手牌"""
        tracker = create_tracker()

        hand_history = {
            'hand_id': 'h001',
            'players': [{'id': 'player1', 'pos': 'BTN'}],
            'actions': [
                {'street': 'preflop', 'actor': 'player1', 'action': 'raise', 'amount': 3.0},
            ],
            'winners': [],
            'showdown': False,
        }

        # 处理两次
        tracker.update_from_hand(hand_history)
        tracker.update_from_hand(hand_history)

        # 应该只计数一次
        stats = tracker.get_stats('player1')
        self.assertEqual(stats.hands_played, 1)


class TestBatchUpdate(unittest.TestCase):
    """测试批量更新"""

    def test_update_from_multiple_hands(self):
        """测试批量更新多手牌"""
        tracker = create_tracker()

        # 构造10手牌历史
        hands = []
        for i in range(10):
            hands.append({
                'hand_id': f'h{i:03d}',
                'players': [
                    {'id': 'player1', 'pos': 'BTN'},
                ],
                'actions': [
                    {'street': 'preflop', 'actor': 'player1', 'action': 'raise' if i < 7 else 'fold'},
                ],
                'winners': [],
                'showdown': False,
            })

        tracker.update_from_hands(hands)

        stats = tracker.get_stats('player1')
        self.assertEqual(stats.hands_played, 10)
        # 7/10 应该有PFR
        self.assertAlmostEqual(stats.pfr, 0.7, places=1)


class TestSerialization(unittest.TestCase):
    """测试序列化"""

    def test_export_to_dict(self):
        """测试导出为字典"""
        tracker = create_tracker()

        # 添加一些数据
        hand_history = {
            'hand_id': 'h001',
            'players': [{'id': 'player1', 'pos': 'BTN'}],
            'actions': [
                {'street': 'preflop', 'actor': 'player1', 'action': 'raise', 'amount': 3.0},
            ],
            'winners': [],
            'showdown': False,
        }
        tracker.update_from_hand(hand_history)

        # 导出
        data = tracker.export_to_dict()

        self.assertIn('players', data)
        self.assertIn('processed_hands', data)
        self.assertIn('player1', data['players'])
        self.assertIn('h001', data['processed_hands'])

    def test_export_to_json(self):
        """测试导出为JSON"""
        tracker = create_tracker()

        hand_history = {
            'hand_id': 'h001',
            'players': [{'id': 'player1', 'pos': 'BTN'}],
            'actions': [
                {'street': 'preflop', 'actor': 'player1', 'action': 'raise', 'amount': 3.0},
            ],
            'winners': [],
            'showdown': False,
        }
        tracker.update_from_hand(hand_history)

        json_str = tracker.export_to_json()

        self.assertIsInstance(json_str, str)
        self.assertIn('"player1"', json_str)

    def test_from_dict(self):
        """测试从字典创建"""
        # 构造数据
        data = {
            'players': {
                'player1': {
                    'player_id': 'player1',
                    'hands_played': 50,
                    'vpip': 0.28,
                    'pfr': 0.22,
                    'af': 2.3,
                }
            },
            'processed_hands': ['h001', 'h002']
        }

        tracker = StatsTracker.from_dict(data)

        self.assertEqual(tracker.get_player_count(), 1)
        stats = tracker.get_stats('player1')
        self.assertEqual(stats.hands_played, 50)
        self.assertAlmostEqual(stats.vpip, 0.28)

    def test_round_trip(self):
        """测试序列化往返"""
        tracker1 = create_tracker()

        # 添加数据
        for i in range(5):
            hand_history = {
                'hand_id': f'h{i:03d}',
                'players': [{'id': 'player1', 'pos': 'BTN'}],
                'actions': [
                    {'street': 'preflop', 'actor': 'player1', 'action': 'raise', 'amount': 3.0},
                ],
                'winners': [],
                'showdown': False,
            }
            tracker1.update_from_hand(hand_history)

        # 导出再导入
        data = tracker1.export_to_dict()
        tracker2 = StatsTracker.from_dict(data)

        # 验证数据一致
        stats1 = tracker1.get_stats('player1')
        stats2 = tracker2.get_stats('player1')

        self.assertEqual(stats1.hands_played, stats2.hands_played)
        self.assertEqual(stats1.vpip, stats2.vpip)
        self.assertEqual(stats1.pfr, stats2.pfr)


class TestTrackerSummary(unittest.TestCase):
    """测试追踪器摘要"""

    def test_repr(self):
        """测试__repr__方法"""
        tracker = create_tracker()

        tracker.get_stats('player1')
        tracker.get_stats('player2')

        repr_str = repr(tracker)

        self.assertIn("StatsTracker", repr_str)
        self.assertIn("players=2", repr_str)

    def test_summary(self):
        """测试summary方法"""
        tracker = create_tracker()

        # 添加数据
        hand_history = {
            'hand_id': 'h001',
            'players': [
                {'id': 'alice', 'pos': 'BTN'},
                {'id': 'bob', 'pos': 'BB'},
            ],
            'actions': [
                {'street': 'preflop', 'actor': 'alice', 'action': 'raise', 'amount': 3.0},
                {'street': 'preflop', 'actor': 'bob', 'action': 'call', 'amount': 3.0},
            ],
            'winners': [],
            'showdown': False,
        }
        tracker.update_from_hand(hand_history)

        summary = tracker.summary()

        self.assertIsInstance(summary, str)
        self.assertIn("StatsTracker Summary", summary)
        self.assertIn("alice", summary)
        self.assertIn("bob", summary)


def run_tests():
    """运行所有测试"""
    suite = unittest.TestSuite()

    # 添加所有测试类
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestActionParser))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestStatsTracker))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestMultiPlayerTracking))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestBatchUpdate))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestSerialization))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestTrackerSummary))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
