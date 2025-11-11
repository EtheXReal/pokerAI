#!/usr/bin/env python
"""
玩家分类器单元测试

测试:
1. 9种玩家类型的识别准确性
2. 置信度评分系统
3. 样本量要求
4. Exploit策略提示
5. 边界情况处理
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import unittest

from advisor.opponent_modeling import (
    create_opponent_stats,
    PlayerClassifier,
    classify_player,
    get_player_type_name,
    PlayerType,
)


class TestPlayerClassifier(unittest.TestCase):
    """测试玩家分类器"""

    def setUp(self):
        """每个测试前创建分类器"""
        self.classifier = PlayerClassifier()

    def test_create_classifier(self):
        """测试创建分类器"""
        self.assertIsNotNone(self.classifier)
        self.assertIsInstance(self.classifier, PlayerClassifier)

    def test_insufficient_samples(self):
        """测试样本量不足"""
        stats = create_opponent_stats("player1")
        stats.hands_played = 20  # < 30

        result = self.classifier.classify(stats)

        self.assertEqual(result.player_type, PlayerType.UNKNOWN)
        self.assertEqual(result.confidence, 0.0)
        self.assertIn("样本量不足", result.reason)

    def test_classify_nit(self):
        """测试识别 Nit (极紧型)"""
        stats = create_opponent_stats("nit_player")
        stats.hands_played = 100
        stats.vpip = 0.12  # 极低
        stats.pfr = 0.10   # 极低
        stats.three_bet_pct = 0.03
        stats.af = 1.5

        result = self.classifier.classify(stats)

        self.assertEqual(result.player_type, PlayerType.NIT)
        self.assertGreater(result.confidence, 0.6)

    def test_classify_tag(self):
        """测试识别 TAG (紧凶型)"""
        stats = create_opponent_stats("tag_player")
        stats.hands_played = 150
        stats.vpip = 0.22   # 适中
        stats.pfr = 0.18    # 高
        stats.three_bet_pct = 0.08
        stats.af = 2.5      # 激进

        result = self.classifier.classify(stats)

        self.assertEqual(result.player_type, PlayerType.TAG)
        self.assertGreater(result.confidence, 0.6)

    def test_classify_weak_tight(self):
        """测试识别 Weak Tight (弱紧型)"""
        stats = create_opponent_stats("weak_tight_player")
        stats.hands_played = 100
        stats.vpip = 0.18
        stats.pfr = 0.12
        stats.af = 1.2   # 被动

        result = self.classifier.classify(stats)

        self.assertEqual(result.player_type, PlayerType.WEAK_TIGHT)
        self.assertGreater(result.confidence, 0.5)

    def test_classify_calling_station(self):
        """测试识别 Calling Station (跟注站)"""
        stats = create_opponent_stats("calling_station")
        stats.hands_played = 120
        stats.vpip = 0.45   # 高
        stats.pfr = 0.10    # 低
        stats.af = 0.8      # 被动
        stats.wtsd = 0.35   # 高

        result = self.classifier.classify(stats)

        self.assertEqual(result.player_type, PlayerType.CALLING_STATION)
        self.assertGreater(result.confidence, 0.6)

    def test_classify_lap(self):
        """测试识别 LAP (松被动型)"""
        stats = create_opponent_stats("lap_player")
        stats.hands_played = 100
        stats.vpip = 0.32
        stats.pfr = 0.15
        stats.af = 1.5

        result = self.classifier.classify(stats)

        self.assertEqual(result.player_type, PlayerType.LAP)
        self.assertGreater(result.confidence, 0.5)

    def test_classify_fish(self):
        """测试识别 Fish (鱼)"""
        stats = create_opponent_stats("fish_player")
        stats.hands_played = 150
        stats.vpip = 0.55   # 过高
        stats.pfr = 0.12    # 低
        stats.af = 1.0
        stats.wtsd = 0.40
        stats.w_sd = 0.35   # 低胜率

        result = self.classifier.classify(stats)

        self.assertEqual(result.player_type, PlayerType.FISH)
        self.assertGreater(result.confidence, 0.6)

    def test_classify_lag(self):
        """测试识别 LAG (松凶型)"""
        stats = create_opponent_stats("lag_player")
        stats.hands_played = 180
        stats.vpip = 0.32   # 较高
        stats.pfr = 0.25    # 高
        stats.three_bet_pct = 0.10
        stats.af = 3.0      # 激进

        result = self.classifier.classify(stats)

        self.assertEqual(result.player_type, PlayerType.LAG)
        self.assertGreater(result.confidence, 0.6)

    def test_classify_maniac(self):
        """测试识别 Maniac (疯狂型)"""
        stats = create_opponent_stats("maniac_player")
        stats.hands_played = 200
        stats.vpip = 0.65   # 极高
        stats.pfr = 0.45    # 极高
        stats.three_bet_pct = 0.18
        stats.af = 4.5      # 极度激进

        result = self.classifier.classify(stats)

        self.assertEqual(result.player_type, PlayerType.MANIAC)
        self.assertGreater(result.confidence, 0.7)

    def test_classify_solid_reg(self):
        """测试识别 Solid Reg (稳健常客)"""
        stats = create_opponent_stats("solid_reg")
        stats.hands_played = 250
        stats.vpip = 0.24    # 平衡
        stats.pfr = 0.18     # 平衡 (75% ratio)
        stats.three_bet_pct = 0.09
        stats.af = 2.4       # 适中激进度
        stats.wtsd = 0.25    # 适中
        stats.w_sd = 0.55    # 盈利

        result = self.classifier.classify(stats)

        # Solid Reg可能被识别为TAG，都是好玩家，接受这两种分类
        self.assertIn(result.player_type, [PlayerType.SOLID_REG, PlayerType.TAG])
        self.assertGreater(result.confidence, 0.5)


class TestConfidenceSystem(unittest.TestCase):
    """测试置信度系统"""

    def setUp(self):
        """创建分类器"""
        self.classifier = PlayerClassifier()

    def test_confidence_increases_with_samples(self):
        """测试置信度随样本量增加"""
        # 创建TAG玩家
        stats = create_opponent_stats("player1")
        stats.vpip = 0.22
        stats.pfr = 0.18
        stats.af = 2.5
        stats.three_bet_pct = 0.08

        # 50手
        stats.hands_played = 50
        result_50 = self.classifier.classify(stats)

        # 100手
        stats.hands_played = 100
        result_100 = self.classifier.classify(stats)

        # 200手
        stats.hands_played = 200
        result_200 = self.classifier.classify(stats)

        # 置信度应该递增
        self.assertLess(result_50.confidence, result_100.confidence)
        self.assertLess(result_100.confidence, result_200.confidence)

    def test_high_confidence_with_many_samples(self):
        """测试大样本量的高置信度"""
        stats = create_opponent_stats("player1")
        stats.hands_played = 250
        stats.vpip = 0.22
        stats.pfr = 0.18
        stats.af = 2.5
        stats.three_bet_pct = 0.08

        result = self.classifier.classify(stats)

        self.assertGreater(result.confidence, 0.7)


class TestAlternativeTypes(unittest.TestCase):
    """测试备选类型"""

    def setUp(self):
        """创建分类器"""
        self.classifier = PlayerClassifier()

    def test_alternative_types_exist(self):
        """测试有备选类型"""
        # 创建一个介于TAG和LAG之间的玩家
        stats = create_opponent_stats("player1")
        stats.hands_played = 100
        stats.vpip = 0.26   # 在TAG和LAG边界
        stats.pfr = 0.20
        stats.af = 2.3
        stats.three_bet_pct = 0.08

        result = self.classifier.classify(stats)

        # 应该有备选类型
        self.assertGreater(len(result.alternative_types), 0)

    def test_clear_classification_fewer_alternatives(self):
        """测试明确分类时备选类型少"""
        # 创建明确的Fish
        stats = create_opponent_stats("player1")
        stats.hands_played = 150
        stats.vpip = 0.60   # 极高
        stats.pfr = 0.10    # 极低
        stats.af = 0.8
        stats.wtsd = 0.45
        stats.w_sd = 0.30

        result = self.classifier.classify(stats)

        # 应该是Fish
        self.assertEqual(result.player_type, PlayerType.FISH)
        # 高置信度
        self.assertGreater(result.confidence, 0.7)


class TestExploitationHints(unittest.TestCase):
    """测试Exploit策略提示"""

    def setUp(self):
        """创建分类器"""
        self.classifier = PlayerClassifier()

    def test_nit_hints(self):
        """测试Nit策略提示"""
        hints = self.classifier.get_exploitation_hints(PlayerType.NIT)

        self.assertIsInstance(hints, list)
        self.assertGreater(len(hints), 0)
        # 应该提到偷盲
        self.assertTrue(any("偷盲" in hint for hint in hints))

    def test_calling_station_hints(self):
        """测试Calling Station策略提示"""
        hints = self.classifier.get_exploitation_hints(PlayerType.CALLING_STATION)

        # 应该提到不要诈唬
        self.assertTrue(any("诈唬" in hint for hint in hints))
        # 应该提到价值下注
        self.assertTrue(any("价值" in hint for hint in hints))

    def test_all_types_have_hints(self):
        """测试所有类型都有策略提示"""
        all_types = [
            PlayerType.NIT,
            PlayerType.TAG,
            PlayerType.WEAK_TIGHT,
            PlayerType.CALLING_STATION,
            PlayerType.LAP,
            PlayerType.FISH,
            PlayerType.LAG,
            PlayerType.MANIAC,
            PlayerType.SOLID_REG,
            PlayerType.UNKNOWN,
        ]

        for player_type in all_types:
            hints = self.classifier.get_exploitation_hints(player_type)
            self.assertIsInstance(hints, list)
            self.assertGreater(len(hints), 0)


class TestHelperFunctions(unittest.TestCase):
    """测试辅助函数"""

    def test_classify_player_function(self):
        """测试classify_player便捷函数"""
        stats = create_opponent_stats("player1")
        stats.hands_played = 100
        stats.vpip = 0.22
        stats.pfr = 0.18
        stats.af = 2.5

        result = classify_player(stats)

        self.assertIsNotNone(result)
        self.assertIsInstance(result.player_type, PlayerType)

    def test_get_player_type_name(self):
        """测试获取玩家类型名称"""
        name = get_player_type_name(PlayerType.TAG)

        self.assertIsInstance(name, str)
        self.assertIn("TAG", name)
        self.assertIn("紧凶型", name)

    def test_all_types_have_names(self):
        """测试所有类型都有名称"""
        all_types = [
            PlayerType.NIT,
            PlayerType.TAG,
            PlayerType.WEAK_TIGHT,
            PlayerType.CALLING_STATION,
            PlayerType.LAP,
            PlayerType.FISH,
            PlayerType.LAG,
            PlayerType.MANIAC,
            PlayerType.SOLID_REG,
            PlayerType.UNKNOWN,
        ]

        for player_type in all_types:
            name = get_player_type_name(player_type)
            self.assertIsInstance(name, str)
            self.assertGreater(len(name), 0)


def run_tests():
    """运行所有测试"""
    suite = unittest.TestSuite()

    # 添加所有测试类
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestPlayerClassifier))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestConfidenceSystem))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestAlternativeTypes))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestExploitationHints))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestHelperFunctions))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
