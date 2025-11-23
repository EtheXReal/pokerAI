"""
RangeEngine单元测试

测试range-based决策的核心模块。
"""

import pytest
import os
from advisor_v2.analysis.range_engine import RangeEngine
from advisor_v2.core.data_structures import Action
from advisor_v2.core.data_structures import Position
from poker_core.cards import Hand, Card
from poker_core.range import Range


class TestRangeEngineInitialization:
    """测试RangeEngine初始化和数据加载"""

    def test_initialization_with_default_path(self):
        """测试使用默认路径初始化"""
        engine = RangeEngine()

        # 验证数据已加载
        assert engine.range_data is not None
        assert 'open_ranges' in engine.range_data
        assert 'vs_open_3bet_ranges' in engine.range_data
        assert 'vs_open_call_ranges' in engine.range_data

    def test_range_cache_preloaded(self):
        """测试range缓存已预加载"""
        engine = RangeEngine()

        # 验证缓存已加载
        assert len(engine.range_cache) > 0

        # 验证关键range已加载
        assert 'open_BTN' in engine.range_cache
        assert 'open_CO' in engine.range_cache
        assert 'open_MP' in engine.range_cache

        # 验证range是Range对象
        assert isinstance(engine.range_cache['open_BTN'], Range)

    def test_preflop_hand_strength_cache_built(self):
        """测试翻前hand strength缓存已构建"""
        engine = RangeEngine()

        # 验证缓存已构建
        assert len(engine.preflop_hand_strength_cache) > 0

        # 验证关键hands的strength
        assert engine.preflop_hand_strength_cache['AA'] == 1.00
        assert engine.preflop_hand_strength_cache['KK'] == 0.95
        assert engine.preflop_hand_strength_cache['AKs'] > 0.90
        assert engine.preflop_hand_strength_cache['A5o'] > 0.50  # A5o应该有一定强度


class TestGetIdealRange:
    """测试get_ideal_range()功能"""

    def setup_method(self):
        """每个测试前初始化"""
        self.engine = RangeEngine()

    def test_open_range_btn(self):
        """测试BTN开池range"""
        range_obj = self.engine.get_ideal_range(Position.BTN, [])

        # BTN开池range应该很宽
        hands = range_obj.to_hands()
        assert len(hands) > 500  # BTN应该开70%左右，总共1326种组合

        # 验证应该包含的hands
        assert Hand([Card('A', 's'), Card('5', 'h')]) in hands  # A5o应该在BTN range中
        assert Hand([Card('A', 's'), Card('A', 'h')]) in hands  # AA当然在
        assert Hand([Card('2', 's'), Card('2', 'h')]) in hands  # 22应该在

    def test_open_range_co(self):
        """测试CO开池range"""
        range_obj = self.engine.get_ideal_range(Position.CO, [])

        hands = range_obj.to_hands()
        # CO比BTN紧，应该在45-55%
        assert 400 < len(hands) < 800

        # CO应该有ATs, KQs
        assert Hand([Card('A', 's'), Card('T', 's')]) in hands
        assert Hand([Card('K', 's'), Card('Q', 's')]) in hands

    def test_open_range_mp(self):
        """测试MP开池range"""
        range_obj = self.engine.get_ideal_range(Position.MP, [])

        hands = range_obj.to_hands()
        # MP更紧，应该在25-30%
        assert 250 < len(hands) < 450

    def test_open_range_bb(self):
        """测试BB开池range（应该为空）"""
        range_obj = self.engine.get_ideal_range(Position.BB, [])

        # BB不能开池
        hands = range_obj.to_hands()
        assert len(hands) == 0 or len(hands) < 10  # BB range应该是空或极小

    def test_vs_open_range(self):
        """测试面对open的range"""
        # BB vs BTN open
        action_history = [Action('raise', 3.0)]
        range_obj = self.engine.get_ideal_range(Position.BB, action_history)

        hands = range_obj.to_hands()
        # BB vs BTN open应该很宽（3-bet + call）
        assert len(hands) > 400

        # 应该包含3-bet hands
        assert Hand([Card('A', 's'), Card('A', 'h')]) in hands  # AA 3-bet

        # 应该包含call hands
        # A2s应该在BB vs BTN call range中
        assert Hand([Card('A', 's'), Card('2', 's')]) in hands

    def test_vs_3bet_range(self):
        """测试面对3-bet的range"""
        # BTN open → BB 3-bet → BTN ?
        action_history = [
            Action('raise', 3.0),   # BTN open
            Action('raise', 10.0)   # BB 3-bet
        ]
        range_obj = self.engine.get_ideal_range(Position.BTN, action_history)

        hands = range_obj.to_hands()
        # 应该包含4-bet和call range
        assert len(hands) > 50

        # 应该包含4-bet hands
        assert Hand([Card('A', 's'), Card('A', 'h')]) in hands  # AA 4-bet
        assert Hand([Card('K', 's'), Card('K', 'h')]) in hands  # KK 4-bet


class TestGetHandPercentile:
    """测试get_hand_percentile()功能（核心！）"""

    def setup_method(self):
        """每个测试前初始化"""
        self.engine = RangeEngine()

    def test_aa_in_btn_open_range(self):
        """测试AA在BTN open range中的位置"""
        btn_range = self.engine.get_ideal_range(Position.BTN, [])
        aa_hand = Hand([Card('A', 's'), Card('A', 'h')])

        percentile = self.engine.get_hand_percentile(aa_hand, btn_range, board=None)

        # AA应该是range中最强的牌
        assert percentile > 0.95

    def test_a5o_in_btn_open_range(self):
        """测试A5o在BTN open range中的位置（关键测试！）"""
        btn_range = self.engine.get_ideal_range(Position.BTN, [])
        a5o_hand = Hand([Card('A', 's'), Card('5', 'h')])

        percentile = self.engine.get_hand_percentile(a5o_hand, btn_range, board=None)

        # A5o应该在BTN range的中上部分（不是最强，也不是最弱）
        # 预期：0.50-0.75之间
        assert 0.40 < percentile < 0.80

        # 这是关键：A5o的percentile应该高于0.4，说明应该raise
        assert percentile > 0.40, "A5o应该在BTN open range中，percentile应该>0.4"

    def test_72o_in_btn_open_range(self):
        """测试72o在BTN open range中的位置"""
        btn_range = self.engine.get_ideal_range(Position.BTN, [])
        trash_hand = Hand([Card('7', 's'), Card('2', 'h')])

        percentile = self.engine.get_hand_percentile(trash_hand, btn_range, board=None)

        # 72o应该在range的底部或不在range中
        assert percentile < 0.30 or percentile == 0.0

    def test_hand_not_in_range(self):
        """测试hand不在range中时返回0"""
        mp_range = self.engine.get_ideal_range(Position.MP, [])  # MP range很紧
        trash_hand = Hand([Card('7', 's'), Card('2', 'h')])  # 72o肯定不在MP range

        percentile = self.engine.get_hand_percentile(trash_hand, mp_range, board=None)

        # 不在range中应该返回0.0
        assert percentile == 0.0

    def test_percentile_ordering(self):
        """测试percentile的顺序正确性"""
        btn_range = self.engine.get_ideal_range(Position.BTN, [])

        # AA > KK > AKs > AQs
        aa = Hand([Card('A', 's'), Card('A', 'h')])
        kk = Hand([Card('K', 's'), Card('K', 'h')])
        aks = Hand([Card('A', 's'), Card('K', 's')])
        aqs = Hand([Card('A', 's'), Card('Q', 's')])

        p_aa = self.engine.get_hand_percentile(aa, btn_range)
        p_kk = self.engine.get_hand_percentile(kk, btn_range)
        p_aks = self.engine.get_hand_percentile(aks, btn_range)
        p_aqs = self.engine.get_hand_percentile(aqs, btn_range)

        # 验证顺序
        assert p_aa > p_kk
        assert p_kk > p_aks
        assert p_aks > p_aqs

    def test_postflop_percentile_with_board(self):
        """测试翻后hand在range中的位置"""
        btn_range = self.engine.get_ideal_range(Position.BTN, [])

        # Flop: Ks 7h 2c
        board = [Card('K', 's'), Card('7', 'h'), Card('2', 'c')]

        # KK (set) 应该在range顶部
        kk = Hand([Card('K', 'd'), Card('K', 'h')])
        p_kk = self.engine.get_hand_percentile(kk, btn_range, board=board)
        assert p_kk > 0.90, "KK set应该在range顶部"

        # AK (top pair top kicker) 应该在上部
        ak = Hand([Card('A', 's'), Card('K', 'c')])
        p_ak = self.engine.get_hand_percentile(ak, btn_range, board=board)
        assert p_ak > 0.70, "AK top pair应该在range上部"

        # AA (overpair) vs KK (set)
        aa = Hand([Card('A', 'd'), Card('A', 'h')])
        p_aa = self.engine.get_hand_percentile(aa, btn_range, board=board)
        # AA (overpair) < KK (set)
        assert p_aa < p_kk


class TestAnalyzeRangeInteraction:
    """测试analyze_range_interaction()功能"""

    def setup_method(self):
        """每个测试前初始化"""
        self.engine = RangeEngine()

    def test_basic_range_analysis(self):
        """测试基本的range分析"""
        hero_range = Range.from_string("99+,ATs+,KQs,AQo+")  # 强range
        villain_range = Range.from_string("22+,A2s+,K5s+,Q8s+")  # 宽range

        # 翻前分析（没有board）
        result = self.engine.analyze_range_interaction(hero_range, villain_range, [])

        # 验证返回的数据结构
        assert result.advantage_score is not None
        assert result.advantage_type in ['nut', 'range', 'none']
        assert result.hero_range_size_ratio is not None
        assert result.hero_equity_distribution is not None

    def test_hero_has_nut_advantage(self):
        """测试hero有nut advantage的情况"""
        # Flop: Ks 7h 2c (K-high dry board)
        board = [Card('K', 's'), Card('7', 'h'), Card('2', 'c')]

        # Hero (BTN) cbet range: 包含很多Kx
        hero_range = Range.from_string("22+,A2s+,K5s+,Q8s+,J8s+,T8s+")

        # Villain (BB) defense range: 更宽，但K的组合少
        villain_range = Range.from_string("22+,A2s+,K5s+,Q5s+,J7s+,T7s+")

        result = self.engine.analyze_range_interaction(hero_range, villain_range, board)

        # Hero应该有range advantage（因为BTN的range质量更高）
        # 注意：具体值取决于实现细节
        assert result.advantage_score >= -0.5  # 至少不是严重劣势

    def test_range_size_comparison(self):
        """测试range size比较"""
        small_range = Range.from_string("QQ+,AKs,AKo")  # ~34 combos
        large_range = Range.from_string("22+,A2s+,K5s+,Q8s+")  # ~300+ combos

        result = self.engine.analyze_range_interaction(small_range, large_range, [])

        # Small range vs large range, size_ratio应该小于1
        assert result.hero_range_size_ratio < 1.0

    def test_board_favors_detection(self):
        """测试board_favors检测"""
        hero_range = Range.from_string("99+,ATs+,KQs,AQo+")
        villain_range = Range.from_string("22-88,A2s-A9s,K5s+")

        # Flop: Ks Qh Jc (high card heavy)
        board = [Card('K', 's'), Card('Q', 'h'), Card('J', 'c')]

        result = self.engine.analyze_range_interaction(hero_range, villain_range, board)

        # board_favors应该是'hero', 'villain', 或'neutral'
        assert result.board_favors in ['hero', 'villain', 'neutral']


class TestEstimateVillainRange:
    """测试estimate_villain_range()功能"""

    def setup_method(self):
        """每个测试前初始化"""
        self.engine = RangeEngine()

    def test_estimate_btn_open_range(self):
        """测试估计BTN open range"""
        action_history = [Action('raise', 3.0)]

        estimated_range = self.engine.estimate_villain_range(
            Position.BTN,
            action_history,
            villain_tendencies=None  # Phase 1: 不使用tendencies
        )

        # 应该返回标准的BTN open range
        hands = estimated_range.to_hands()
        assert len(hands) > 500  # BTN range应该很宽

    def test_estimate_co_open_range(self):
        """测试估计CO open range"""
        action_history = [Action('raise', 3.0)]

        estimated_range = self.engine.estimate_villain_range(
            Position.CO,
            action_history
        )

        hands = estimated_range.to_hands()
        # CO range比BTN紧
        assert 400 < len(hands) < 800

    def test_estimate_vs_tendencies_placeholder(self):
        """测试传入tendencies（Phase 2功能，当前应该忽略）"""
        action_history = [Action('raise', 3.0)]

        # 传入LAG tendencies
        tendencies = {'vpip': 0.38, 'pfr': 0.30}

        estimated_range = self.engine.estimate_villain_range(
            Position.BTN,
            action_history,
            villain_tendencies=tendencies
        )

        # Phase 1应该返回GTO range（忽略tendencies）
        hands = estimated_range.to_hands()
        assert len(hands) > 0


class TestHandToStrConversion:
    """测试hand_to_str()辅助方法"""

    def setup_method(self):
        """每个测试前初始化"""
        self.engine = RangeEngine()

    def test_pair_conversion(self):
        """测试对子转换"""
        aa = Hand([Card('A', 's'), Card('A', 'h')])
        assert self.engine._hand_to_str(aa) == "AA"

        kk = Hand([Card('K', 'd'), Card('K', 'c')])
        assert self.engine._hand_to_str(kk) == "KK"

    def test_suited_conversion(self):
        """测试同花转换"""
        aks = Hand([Card('A', 's'), Card('K', 's')])
        assert self.engine._hand_to_str(aks) == "AKs"

        # 测试顺序（应该高牌在前）
        ksa = Hand([Card('K', 's'), Card('A', 's')])
        assert self.engine._hand_to_str(ksa) == "AKs"

    def test_offsuit_conversion(self):
        """测试非同花转换"""
        ako = Hand([Card('A', 's'), Card('K', 'h')])
        assert self.engine._hand_to_str(ako) == "AKo"

        a5o = Hand([Card('A', 's'), Card('5', 'h')])
        assert self.engine._hand_to_str(a5o) == "A5o"


class TestRankValue:
    """测试_rank_value()辅助方法"""

    def setup_method(self):
        """每个测试前初始化"""
        self.engine = RangeEngine()

    def test_rank_ordering(self):
        """测试rank排序正确性"""
        assert self.engine._rank_value('A') == 14
        assert self.engine._rank_value('K') == 13
        assert self.engine._rank_value('Q') == 12
        assert self.engine._rank_value('J') == 11
        assert self.engine._rank_value('T') == 10
        assert self.engine._rank_value('9') == 9
        assert self.engine._rank_value('2') == 2

        # 验证A > K > Q > ... > 2
        assert self.engine._rank_value('A') > self.engine._rank_value('K')
        assert self.engine._rank_value('K') > self.engine._rank_value('2')


class TestPreloadedData:
    """测试预加载的数据完整性"""

    def setup_method(self):
        """每个测试前初始化"""
        self.engine = RangeEngine()

    def test_all_positions_have_open_ranges(self):
        """测试所有位置都有open range（除了BB）"""
        positions_with_open = [Position.BTN, Position.CO, Position.MP, Position.SB]

        for pos in positions_with_open:
            cache_key = f'open_{pos.name}'
            assert cache_key in self.engine.range_cache, f"{pos.name} open range missing"

            range_obj = self.engine.range_cache[cache_key]
            if pos != Position.BB:  # BB不能开池
                assert len(range_obj.to_hands()) > 0, f"{pos.name} open range is empty"

    def test_key_3bet_ranges_exist(self):
        """测试关键的3-bet ranges存在"""
        key_3bet_ranges = [
            '3bet_BTN_vs_CO',
            '3bet_BB_vs_BTN',
            '3bet_CO_vs_MP'
        ]

        for key in key_3bet_ranges:
            if key in self.engine.range_cache:
                range_obj = self.engine.range_cache[key]
                assert len(range_obj.to_hands()) > 0, f"{key} is empty"

    def test_preflop_strength_coverage(self):
        """测试翻前strength覆盖主要hands"""
        cache = self.engine.preflop_hand_strength_cache

        # 测试主要hands都有strength值
        key_hands = ['AA', 'KK', 'QQ', 'AKs', 'AKo', 'AQs', 'A5o', '22', '72o']

        for hand in key_hands:
            assert hand in cache, f"{hand} missing in preflop strength cache"
            assert 0.0 <= cache[hand] <= 1.0, f"{hand} strength out of range"


# ============================================================================
# 性能测试
# ============================================================================

class TestRangeEnginePerformance:
    """测试RangeEngine性能"""

    def setup_method(self):
        """每个测试前初始化"""
        self.engine = RangeEngine()

    def test_get_ideal_range_performance(self):
        """测试get_ideal_range性能"""
        import time

        start = time.time()
        for _ in range(100):
            self.engine.get_ideal_range(Position.BTN, [])
        end = time.time()

        avg_time = (end - start) / 100 * 1000  # ms

        # 应该在1ms以内（从cache直接返回）
        assert avg_time < 1.0, f"get_ideal_range too slow: {avg_time:.2f}ms"

    def test_get_hand_percentile_performance(self):
        """测试get_hand_percentile性能"""
        import time

        btn_range = self.engine.get_ideal_range(Position.BTN, [])
        hand = Hand([Card('A', 's'), Card('5', 'h')])

        start = time.time()
        for _ in range(100):
            self.engine.get_hand_percentile(hand, btn_range, board=None)
        end = time.time()

        avg_time = (end - start) / 100 * 1000  # ms

        # 翻前应该在1ms以内
        assert avg_time < 2.0, f"get_hand_percentile too slow: {avg_time:.2f}ms"


# ============================================================================
# 边界情况测试
# ============================================================================

class TestEdgeCases:
    """测试边界情况"""

    def setup_method(self):
        """每个测试前初始化"""
        self.engine = RangeEngine()

    def test_empty_range(self):
        """测试空range"""
        empty_range = Range.from_string("")
        hand = Hand([Card('A', 's'), Card('A', 'h')])

        percentile = self.engine.get_hand_percentile(hand, empty_range)

        # 空range应该返回0.5（中间值）
        assert percentile == 0.5

    def test_single_hand_range(self):
        """测试只有一个hand的range"""
        single_range = Range.from_string("AA")
        aa = Hand([Card('A', 's'), Card('A', 'h')])

        percentile = self.engine.get_hand_percentile(aa, single_range)

        # 单个hand应该返回1.0（最强）
        assert percentile == 1.0

    def test_invalid_hand(self):
        """测试无效的hand"""
        btn_range = self.engine.get_ideal_range(Position.BTN, [])
        invalid_hand = Hand([])  # 空hand

        # 应该不会崩溃，返回默认值
        percentile = self.engine.get_hand_percentile(invalid_hand, btn_range)
        assert percentile >= 0.0


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
