#!/usr/bin/env python
"""
OpponentStats 单元测试

测试:
1. OpponentStats 基础功能
2. 统计指标更新逻辑
3. 增量更新的正确性
4. 序列化和反序列化
5. 置信度计算
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import unittest
from advisor_v2.modeling import (
    OpponentStats,
    PlayerType,
    ActionType,
    StreetType,
    PositionType
)
from advisor_v2.modeling.stats import create_opponent_stats
from advisor_v2.modeling.models import HandResult, ActionRecord


class TestOpponentStatsBasics(unittest.TestCase):
    """测试OpponentStats基础功能"""

    def test_create_opponent_stats(self):
        """测试创建对手统计"""
        stats = create_opponent_stats("player_001")

        self.assertEqual(stats.player_id, "player_001")
        self.assertEqual(stats.hands_played, 0)
        self.assertEqual(stats.vpip, 0.0)
        self.assertEqual(stats.pfr, 0.0)
        self.assertEqual(stats.af, 0.0)
        self.assertIsNotNone(stats.last_updated)

    def test_initial_confidence(self):
        """测试初始置信度"""
        stats = create_opponent_stats("player_001")
        self.assertEqual(stats.get_confidence(), 0.3)

    def test_confidence_scaling(self):
        """测试置信度随手数增长"""
        stats = create_opponent_stats("player_001")

        # < 30手
        stats.hands_played = 20
        self.assertEqual(stats.get_confidence(), 0.3)

        # 30-50手
        stats.hands_played = 40
        self.assertEqual(stats.get_confidence(), 0.6)

        # 50-100手
        stats.hands_played = 75
        self.assertEqual(stats.get_confidence(), 0.8)

        # 100-200手
        stats.hands_played = 150
        self.assertEqual(stats.get_confidence(), 0.9)

        # > 200手
        stats.hands_played = 250
        self.assertEqual(stats.get_confidence(), 0.95)


class TestVPIPPFRUpdates(unittest.TestCase):
    """测试VPIP和PFR更新"""

    def test_vpip_update_single_hand(self):
        """测试单手牌VPIP更新"""
        stats = create_opponent_stats("player_001")

        # 第一手: VPIP
        hand1 = HandResult(
            hand_id="h001",
            position=PositionType.BTN,
            vpip=True,
            pfr=False
        )
        stats.update_from_hand(hand1)

        self.assertEqual(stats.hands_played, 1)
        self.assertEqual(stats.vpip, 1.0)
        self.assertEqual(stats.pfr, 0.0)

    def test_vpip_multiple_hands(self):
        """测试多手牌VPIP计算"""
        stats = create_opponent_stats("player_001")

        # 10手牌, 6手VPIP
        for i in range(10):
            hand = HandResult(
                hand_id=f"h{i:03d}",
                position=PositionType.BTN,
                vpip=(i < 6),  # 前6手VPIP
                pfr=False
            )
            stats.update_from_hand(hand)

        self.assertEqual(stats.hands_played, 10)
        self.assertAlmostEqual(stats.vpip, 0.6, places=2)

    def test_pfr_update(self):
        """测试PFR更新"""
        stats = create_opponent_stats("player_001")

        # 10手牌, 3手PFR
        for i in range(10):
            hand = HandResult(
                hand_id=f"h{i:03d}",
                position=PositionType.BTN,
                vpip=(i < 6),
                pfr=(i < 3)  # 前3手PFR
            )
            stats.update_from_hand(hand)

        self.assertEqual(stats.hands_played, 10)
        self.assertAlmostEqual(stats.pfr, 0.3, places=2)


class TestPreflopStats(unittest.TestCase):
    """测试翻前统计"""

    def test_three_bet_update(self):
        """测试3-bet频率更新"""
        stats = create_opponent_stats("player_001")

        # 5手牌, 2次3-bet
        for i in range(5):
            hand = HandResult(
                hand_id=f"h{i:03d}",
                position=PositionType.BTN,
                vpip=True,
                pfr=True,
                three_bet=(i < 2)
            )
            stats.update_from_hand(hand)

        self.assertAlmostEqual(stats.three_bet_pct, 0.4, places=2)

    def test_fold_to_3bet(self):
        """测试面对3-bet的弃牌率"""
        stats = create_opponent_stats("player_001")

        # 面对5次3-bet, 弃牌3次, 跟注2次
        for i in range(5):
            hand = HandResult(
                hand_id=f"h{i:03d}",
                position=PositionType.BTN,
                vpip=True,
                pfr=True,
                fold_to_3bet=(i < 3),  # 前3次弃牌
                call_3bet=(i >= 3)     # 后2次跟注
            )
            stats.update_from_hand(hand)

        self.assertAlmostEqual(stats.fold_to_3bet, 0.6, places=2)


class TestPostflopStats(unittest.TestCase):
    """测试翻后统计"""

    def test_cbet_flop_update(self):
        """测试翻牌c-bet频率"""
        stats = create_opponent_stats("player_001")

        # 10次机会, 7次c-bet
        for i in range(10):
            hand = HandResult(
                hand_id=f"h{i:03d}",
                position=PositionType.BTN,
                vpip=True,
                pfr=True,
                saw_flop=True,
                cbet_flop=(i < 7)
            )
            stats.update_from_hand(hand)

        self.assertAlmostEqual(stats.cbet_flop, 0.7, places=2)

    def test_fold_to_cbet(self):
        """测试对c-bet弃牌率"""
        stats = create_opponent_stats("player_001")

        # 面对8次c-bet, 弃牌5次
        for i in range(8):
            hand = HandResult(
                hand_id=f"h{i:03d}",
                position=PositionType.BB,
                vpip=True,
                pfr=False,
                saw_flop=True,
                fold_to_cbet=(i < 5)
            )
            stats.update_from_hand(hand)

        self.assertAlmostEqual(stats.fold_to_cbet_flop, 0.625, places=2)


class TestShowdownStats(unittest.TestCase):
    """测试摊牌统计"""

    def test_wtsd_calculation(self):
        """测试摊牌率计算"""
        stats = create_opponent_stats("player_001")

        # 10手看到翻牌, 3手去摊牌
        for i in range(10):
            hand = HandResult(
                hand_id=f"h{i:03d}",
                position=PositionType.BTN,
                vpip=True,
                pfr=False,
                saw_flop=True,
                went_to_showdown=(i < 3)
            )
            stats.update_from_hand(hand)

        self.assertAlmostEqual(stats.wtsd, 0.3, places=2)

    def test_w_sd_calculation(self):
        """测试摊牌胜率计算"""
        stats = create_opponent_stats("player_001")

        # 5手摊牌, 3手获胜
        for i in range(5):
            hand = HandResult(
                hand_id=f"h{i:03d}",
                position=PositionType.BTN,
                vpip=True,
                pfr=False,
                saw_flop=True,
                went_to_showdown=True,
                won_at_showdown=(i < 3)
            )
            stats.update_from_hand(hand)

        self.assertAlmostEqual(stats.w_sd, 0.6, places=2)


class TestAggressionFactor(unittest.TestCase):
    """测试激进度因子"""

    def test_af_calculation(self):
        """测试AF计算: (bet+raise) / call"""
        stats = create_opponent_stats("player_001")

        # 创建行动序列: 3次激进动作, 2次跟注
        actions = [
            ActionRecord(
                street=StreetType.FLOP,
                position=PositionType.BTN,
                action=ActionType.BET,
                amount=6.0,
                pot_size=10.0
            ),
            ActionRecord(
                street=StreetType.TURN,
                position=PositionType.BTN,
                action=ActionType.RAISE,
                amount=12.0,
                pot_size=20.0
            ),
            ActionRecord(
                street=StreetType.RIVER,
                position=PositionType.BTN,
                action=ActionType.CALL,
                amount=10.0,
                pot_size=40.0
            ),
        ]

        hand = HandResult(
            hand_id="h001",
            position=PositionType.BTN,
            vpip=True,
            pfr=True,
            actions=actions
        )

        stats.update_from_hand(hand)

        # AF = 2 aggressive / 1 call = 2.0
        self.assertAlmostEqual(stats.af, 2.0, places=1)


class TestSerialization(unittest.TestCase):
    """测试序列化和反序列化"""

    def test_to_dict(self):
        """测试转换为字典"""
        stats = create_opponent_stats("player_001")
        stats.hands_played = 50
        stats.vpip = 0.28
        stats.pfr = 0.22

        data = stats.to_dict()

        self.assertIsInstance(data, dict)
        self.assertEqual(data['player_id'], "player_001")
        self.assertEqual(data['hands_played'], 50)
        self.assertAlmostEqual(data['vpip'], 0.28)
        self.assertAlmostEqual(data['pfr'], 0.22)

        # 确保不包含内部计数器
        self.assertNotIn('_vpip_opportunities', data)
        self.assertNotIn('_pfr_opportunities', data)

    def test_to_json(self):
        """测试JSON序列化"""
        stats = create_opponent_stats("player_001")
        stats.hands_played = 50
        stats.vpip = 0.28

        json_str = stats.to_json()

        self.assertIsInstance(json_str, str)
        self.assertIn('"player_id"', json_str)
        self.assertIn('"hands_played"', json_str)

    def test_from_dict(self):
        """测试从字典创建实例"""
        data = {
            'player_id': 'player_002',
            'hands_played': 100,
            'vpip': 0.32,
            'pfr': 0.25,
            'af': 2.5,
            'three_bet_pct': 0.08,
        }

        stats = OpponentStats.from_dict(data)

        self.assertEqual(stats.player_id, 'player_002')
        self.assertEqual(stats.hands_played, 100)
        self.assertAlmostEqual(stats.vpip, 0.32)
        self.assertAlmostEqual(stats.pfr, 0.25)
        self.assertAlmostEqual(stats.af, 2.5)

    def test_round_trip(self):
        """测试序列化往返"""
        original = create_opponent_stats("player_003")
        original.hands_played = 75
        original.vpip = 0.24
        original.pfr = 0.18
        original.af = 2.1

        # 转换为字典再转回来
        data = original.to_dict()
        restored = OpponentStats.from_dict(data)

        self.assertEqual(restored.player_id, original.player_id)
        self.assertEqual(restored.hands_played, original.hands_played)
        self.assertAlmostEqual(restored.vpip, original.vpip)
        self.assertAlmostEqual(restored.pfr, original.pfr)
        self.assertAlmostEqual(restored.af, original.af)


class TestStatsSummary(unittest.TestCase):
    """测试统计摘要"""

    def test_repr(self):
        """测试__repr__方法"""
        stats = create_opponent_stats("player_001")
        stats.hands_played = 50
        stats.vpip = 0.28
        stats.pfr = 0.22
        stats.af = 2.3

        repr_str = repr(stats)

        self.assertIn("player_001", repr_str)
        self.assertIn("hands=50", repr_str)
        self.assertIn("VPIP=28", repr_str)

    def test_summary(self):
        """测试summary方法"""
        stats = create_opponent_stats("player_001")
        stats.hands_played = 100
        stats.vpip = 0.28
        stats.pfr = 0.22
        stats.af = 2.3
        stats.cbet_flop = 0.65
        stats.wtsd = 0.25

        summary = stats.summary()

        self.assertIsInstance(summary, str)
        self.assertIn("player_001", summary)
        self.assertIn("100", summary)  # hands
        self.assertIn("VPIP", summary)
        self.assertIn("PFR", summary)


def run_tests():
    """运行所有测试"""
    suite = unittest.TestSuite()

    # 添加所有测试类
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestOpponentStatsBasics))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestVPIPPFRUpdates))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestPreflopStats))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestPostflopStats))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestShowdownStats))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestAggressionFactor))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestSerialization))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestStatsSummary))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
