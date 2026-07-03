"""
EquityEngine精度测试

用已知的经典对局验证Monte Carlo equity计算的准确性。
（替代v1 EquityCalculator的精度测试，经典数值来自标准equity计算器）
"""

import pytest
import random

from advisor.analysis.equity_engine import EquityEngine
from poker_core.cards import Hand, Card
from poker_core.range import Range


@pytest.fixture
def engine():
    random.seed(42)  # 固定种子，避免Monte Carlo方差导致的flaky
    return EquityEngine()


class TestClassicMatchups:
    """经典对局的equity精度（阈值考虑Monte Carlo方差放宽±6%）"""

    def test_aa_vs_kk_preflop(self, engine):
        """AA vs KK 翻前：AA约82%"""
        aa = Hand.from_str("AsAh")
        kk_range = Range.from_string("KK")

        info = engine.calculate_equity(aa, kk_range, [], iterations=500)
        assert 0.76 < info.point_equity < 0.88, f"AA vs KK equity异常: {info.point_equity}"

    def test_aks_vs_qq_preflop(self, engine):
        """AKs vs QQ 翻前：接近coin flip，AKs约46%"""
        aks = Hand.from_str("AsKs")
        qq_range = Range.from_string("QQ")

        info = engine.calculate_equity(aks, qq_range, [], iterations=500)
        assert 0.40 < info.point_equity < 0.52, f"AKs vs QQ equity异常: {info.point_equity}"

    def test_dominated_hand(self, engine):
        """AK vs AQ（被支配）：AK约73%"""
        ak = Hand.from_str("AsKh")
        aq_range = Range.from_string("AQ")

        info = engine.calculate_equity(ak, aq_range, [], iterations=500)
        assert 0.65 < info.point_equity < 0.81, f"AK vs AQ equity异常: {info.point_equity}"

    def test_pair_vs_undercards(self, engine):
        """QQ vs 87s：QQ约77%"""
        qq = Hand.from_str("QsQh")
        low_range = Range.from_string("87s")

        info = engine.calculate_equity(qq, low_range, [], iterations=500)
        assert 0.70 < info.point_equity < 0.85, f"QQ vs 87s equity异常: {info.point_equity}"


class TestPostflopEquity:
    """翻后equity"""

    def test_set_vs_overpair_on_flop(self, engine):
        """KK set vs AA overpair on Ks7h2c：set约91%"""
        kk = Hand.from_str("KdKh")
        aa_range = Range.from_string("AA")
        board = [Card.from_str("Ks"), Card.from_str("7h"), Card.from_str("2c")]

        info = engine.calculate_equity(kk, aa_range, board, iterations=500)
        assert info.point_equity > 0.85, f"KK set vs AA应该>85%: {info.point_equity}"

    def test_flush_draw_on_flop(self, engine):
        """同花听牌 vs 顶对 on flop：约35-45%"""
        fd = Hand.from_str("Ah5h")  # nut flush draw
        top_pair = Range.from_string("KdQs")
        board = [Card.from_str("Kh"), Card.from_str("8h"), Card.from_str("2c")]

        info = engine.calculate_equity(fd, top_pair, board, iterations=500)
        assert 0.28 < info.point_equity < 0.55, f"flush draw equity异常: {info.point_equity}"


class TestEquityVsRange:
    """hand vs range equity"""

    def test_aa_vs_wide_range(self, engine):
        """AA vs 宽range：应该>80%"""
        aa = Hand.from_str("AsAh")
        wide = Range.from_string("22+,A2s+,K5s+,Q8s+,A5o+,K9o+")

        info = engine.calculate_equity(aa, wide, [], iterations=300)
        assert info.point_equity > 0.75, f"AA vs 宽range应该>75%: {info.point_equity}"

    def test_trash_vs_tight_range(self, engine):
        """72o vs 紧range：应该<35%"""
        trash = Hand.from_str("7s2h")
        tight = Range.from_string("TT+,AQs+,AKo")

        info = engine.calculate_equity(trash, tight, [], iterations=300)
        assert info.point_equity < 0.40, f"72o vs 紧range应该<40%: {info.point_equity}"

    def test_equity_symmetry_sanity(self, engine):
        """相同range对抗，equity应接近50%"""
        hand = Hand.from_str("TsTh")
        tt_range = Range.from_string("TT")

        # TT vs TT (排除撞牌后剩1组合)，基本平分
        info = engine.calculate_equity(hand, tt_range, [], iterations=500)
        assert 0.40 < info.point_equity < 0.60, f"TT vs TT应接近50%: {info.point_equity}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
