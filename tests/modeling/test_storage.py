#!/usr/bin/env python
"""
SQLite存储单元测试

测试:
1. SQLiteStorage 基础CRUD操作
2. 数据持久化和恢复
3. 与StatsTracker的集成
4. 跨session数据保留
5. 数据库信息查询
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import unittest
import tempfile
from pathlib import Path

from advisor.modeling import (
    OpponentStats,
    create_opponent_stats,
    SQLiteStorage,
    create_storage,
    StatsTracker,
    create_tracker,
    HandResult,
    PositionType,
)


class TestSQLiteStorageBasic(unittest.TestCase):
    """测试SQLiteStorage基础功能"""

    def setUp(self):
        """每个测试前创建临时数据库"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.storage = create_storage(self.db_path)

    def tearDown(self):
        """清理临时文件"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_create_storage(self):
        """测试创建存储"""
        self.assertIsNotNone(self.storage)
        self.assertTrue(Path(self.db_path).exists())

    def test_save_and_load(self):
        """测试保存和加载"""
        # 创建统计
        stats = create_opponent_stats("player1")
        stats.hands_played = 100
        stats.vpip = 0.28
        stats.pfr = 0.22
        stats.af = 2.3

        # 保存
        success = self.storage.save_stats(stats)
        self.assertTrue(success)

        # 加载
        loaded = self.storage.load_stats("player1")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.player_id, "player1")
        self.assertEqual(loaded.hands_played, 100)
        self.assertAlmostEqual(loaded.vpip, 0.28)
        self.assertAlmostEqual(loaded.pfr, 0.22)
        self.assertAlmostEqual(loaded.af, 2.3)

    def test_load_nonexistent(self):
        """测试加载不存在的玩家"""
        loaded = self.storage.load_stats("nonexistent")
        self.assertIsNone(loaded)

    def test_update_existing(self):
        """测试更新已存在的统计"""
        # 第一次保存
        stats = create_opponent_stats("player1")
        stats.hands_played = 50
        stats.vpip = 0.30
        self.storage.save_stats(stats)

        # 更新
        stats.hands_played = 100
        stats.vpip = 0.28
        self.storage.save_stats(stats)

        # 验证
        loaded = self.storage.load_stats("player1")
        self.assertEqual(loaded.hands_played, 100)
        self.assertAlmostEqual(loaded.vpip, 0.28)

    def test_delete_stats(self):
        """测试删除统计"""
        # 保存
        stats = create_opponent_stats("player1")
        self.storage.save_stats(stats)

        # 删除
        success = self.storage.delete_stats("player1")
        self.assertTrue(success)

        # 验证已删除
        loaded = self.storage.load_stats("player1")
        self.assertIsNone(loaded)

    def test_delete_nonexistent(self):
        """测试删除不存在的玩家"""
        success = self.storage.delete_stats("nonexistent")
        self.assertFalse(success)

    def test_list_all_players(self):
        """测试列出所有玩家"""
        # 保存多个玩家
        for i in range(5):
            stats = create_opponent_stats(f"player{i}")
            self.storage.save_stats(stats)

        # 列出
        players = self.storage.list_all_players()
        self.assertEqual(len(players), 5)
        self.assertIn("player0", players)
        self.assertIn("player4", players)

    def test_clear_all(self):
        """测试清空所有数据"""
        # 保存多个玩家
        for i in range(3):
            stats = create_opponent_stats(f"player{i}")
            self.storage.save_stats(stats)

        # 清空
        success = self.storage.clear_all()
        self.assertTrue(success)

        # 验证
        players = self.storage.list_all_players()
        self.assertEqual(len(players), 0)


class TestDataPersistence(unittest.TestCase):
    """测试数据持久化"""

    def setUp(self):
        """创建临时数据库"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")

    def tearDown(self):
        """清理临时文件"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_persistence_across_sessions(self):
        """测试跨session数据持久化"""
        # Session 1: 保存数据
        storage1 = create_storage(self.db_path)
        stats = create_opponent_stats("player1")
        stats.hands_played = 100
        stats.vpip = 0.28
        stats.pfr = 0.22
        storage1.save_stats(stats)
        del storage1  # 模拟session结束

        # Session 2: 加载数据
        storage2 = create_storage(self.db_path)
        loaded = storage2.load_stats("player1")

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.hands_played, 100)
        self.assertAlmostEqual(loaded.vpip, 0.28)
        self.assertAlmostEqual(loaded.pfr, 0.22)

    def test_internal_counters_persistence(self):
        """测试内部计数器的持久化"""
        # 创建有具体数据的统计
        storage = create_storage(self.db_path)
        stats = create_opponent_stats("player1")

        # 通过update_from_hand更新（会设置内部计数器）
        for i in range(10):
            hand = HandResult(
                hand_id=f"h{i:03d}",
                position=PositionType.BTN,
                vpip=(i < 7),
                pfr=(i < 5),
            )
            stats.update_from_hand(hand)

        storage.save_stats(stats)
        del storage

        # 重新加载并验证
        storage2 = create_storage(self.db_path)
        loaded = storage2.load_stats("player1")

        # 验证统计值正确
        self.assertEqual(loaded.hands_played, 10)
        self.assertAlmostEqual(loaded.vpip, 0.7, places=1)
        self.assertAlmostEqual(loaded.pfr, 0.5, places=1)

        # 再次更新应该能正确工作
        hand = HandResult(
            hand_id="h_new",
            position=PositionType.BTN,
            vpip=True,
            pfr=True,
        )
        loaded.update_from_hand(hand)
        self.assertEqual(loaded.hands_played, 11)


class TestTrackerIntegration(unittest.TestCase):
    """测试StatsTracker集成"""

    def setUp(self):
        """创建临时数据库"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.storage = create_storage(self.db_path)

    def tearDown(self):
        """清理临时文件"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_tracker_with_storage(self):
        """测试Tracker使用存储后端"""
        # 创建带存储的tracker
        tracker = create_tracker(storage_backend=self.storage)

        # 添加手牌
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

        # 验证自动保存到了数据库
        loaded = self.storage.load_stats('player1')
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.hands_played, 1)

    def test_tracker_loads_from_storage(self):
        """测试Tracker从存储加载已有数据"""
        # 预先保存数据
        stats = create_opponent_stats("player1")
        stats.hands_played = 50
        stats.vpip = 0.30
        self.storage.save_stats(stats)

        # 创建tracker并获取统计
        tracker = create_tracker(storage_backend=self.storage)
        loaded = tracker.get_stats("player1")

        # 应该从数据库加载而非创建新的
        self.assertEqual(loaded.hands_played, 50)
        self.assertAlmostEqual(loaded.vpip, 0.30)

    def test_tracker_persistence_workflow(self):
        """测试完整的持久化工作流"""
        # Session 1: 处理一些手牌
        tracker1 = create_tracker(storage_backend=self.storage)

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

        stats1 = tracker1.get_stats('player1')
        self.assertEqual(stats1.hands_played, 5)

        del tracker1  # Session结束

        # Session 2: 继续处理更多手牌
        storage2 = create_storage(self.db_path)
        tracker2 = create_tracker(storage_backend=storage2)

        # 应该能加载之前的数据
        stats2 = tracker2.get_stats('player1')
        self.assertEqual(stats2.hands_played, 5, "应该加载之前的5手牌")

        # 添加新手牌
        for i in range(5, 10):
            hand_history = {
                'hand_id': f'h{i:03d}',
                'players': [{'id': 'player1', 'pos': 'BTN'}],
                'actions': [
                    {'street': 'preflop', 'actor': 'player1', 'action': 'fold'},
                ],
                'winners': [],
                'showdown': False,
            }
            tracker2.update_from_hand(hand_history)

        stats2 = tracker2.get_stats('player1')
        self.assertEqual(stats2.hands_played, 10, "应该累计到10手牌")


class TestDatabaseInfo(unittest.TestCase):
    """测试数据库信息查询"""

    def setUp(self):
        """创建临时数据库"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.storage = create_storage(self.db_path)

    def tearDown(self):
        """清理临时文件"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_get_stats_count(self):
        """测试获取统计数量"""
        self.assertEqual(self.storage.get_stats_count(), 0)

        # 添加数据
        for i in range(3):
            stats = create_opponent_stats(f"player{i}")
            self.storage.save_stats(stats)

        self.assertEqual(self.storage.get_stats_count(), 3)

    def test_get_database_info(self):
        """测试获取数据库信息"""
        info = self.storage.get_database_info()

        self.assertIn('db_path', info)
        self.assertIn('total_players', info)
        self.assertIn('total_hands', info)
        self.assertIn('db_size_bytes', info)
        self.assertIn('schema_version', info)

        self.assertEqual(info['total_players'], 0)

        # 添加数据后再次检查
        stats = create_opponent_stats("player1")
        stats.hands_played = 100
        self.storage.save_stats(stats)

        info = self.storage.get_database_info()
        self.assertEqual(info['total_players'], 1)
        self.assertEqual(info['total_hands'], 100)

    def test_repr(self):
        """测试__repr__方法"""
        repr_str = repr(self.storage)
        self.assertIn("SQLiteStorage", repr_str)
        self.assertIn("players=", repr_str)


def run_tests():
    """运行所有测试"""
    suite = unittest.TestSuite()

    # 添加所有测试类
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestSQLiteStorageBasic))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestDataPersistence))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestTrackerIntegration))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestDatabaseInfo))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
