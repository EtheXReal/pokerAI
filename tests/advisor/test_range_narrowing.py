"""
翻后范围动态收缩测试

验证 RangeEngine.narrow_range_postflop 和 DecisionIntegrator 的行动驱动范围推断。
"""

import pytest

from advisor.analysis.range_engine import RangeEngine
from advisor.integration.decision_integrator import DecisionIntegrator
from advisor.core.data_structures import GameState
from poker_core.cards import Hand, Card
from poker_core.range import Range
from poker_core.position import Position


@pytest.fixture(scope='module')
def engine():
    return RangeEngine()


BOARD_K72 = [Card.from_str("Ks"), Card.from_str("7h"), Card.from_str("2c")]


class TestNarrowRangePostflop:

    def test_bet_narrows_range(self, engine):
        """bet后范围应显著收缩且保留强牌"""
        btn_range = engine.get_ideal_range(Position.BTN, [])
        narrowed = engine.narrow_range_postflop(btn_range, BOARD_K72, 'bet')

        assert len(narrowed) < len(btn_range) * 0.7, "bet后范围应明显收缩"
        # 顶对强牌保留
        hands = narrowed.to_hands()
        assert Hand.from_str("KdQd") in hands or Hand.from_str("KhQh") in hands, "KQ顶对应保留"

    def test_bet_keeps_flush_draws(self, engine):
        """bet后同花听牌应作为半bluff保留"""
        # 单色board上给一个含花听的范围
        board = [Card.from_str("Kh"), Card.from_str("7h"), Card.from_str("2c")]
        r = Range.from_string("AhQh,Ah5h,KdQd,8s3d,9c4d,QsJs,TsTd,6d6c,AsKc,JhTh,"
                              "9h8h,5s4d,QcJd,Th7c,8c6s,3s3d,AdAc,KsKc,2s2d,4h4c,7s7c")
        narrowed = engine.narrow_range_postflop(r, board, 'bet')
        hands = narrowed.to_hands()

        assert Hand.from_str("AhQh") in hands, "坚果花听应保留（半bluff）"

    def test_check_drops_top(self, engine):
        """check后最强的顶部应被移除"""
        btn_range = engine.get_ideal_range(Position.BTN, [])
        narrowed = engine.narrow_range_postflop(btn_range, BOARD_K72, 'check')

        hands = narrowed.to_hands()
        # 顶set通常不会check（简化模型下KK被移除）
        assert Hand.from_str("KdKh") not in hands, "KK set在check后应被移除"
        # 弱牌保留
        assert len(narrowed) > len(btn_range) * 0.7, "check只移除顶部小部分"

    def test_raise_narrows_more_than_bet(self, engine):
        """raise比bet收缩更多"""
        btn_range = engine.get_ideal_range(Position.BTN, [])
        after_bet = engine.narrow_range_postflop(btn_range, BOARD_K72, 'bet')
        after_raise = engine.narrow_range_postflop(btn_range, BOARD_K72, 'raise')

        assert len(after_raise) <= len(after_bet)

    def test_sequential_narrowing(self, engine):
        """连续动作逐步收缩"""
        btn_range = engine.get_ideal_range(Position.BTN, [])
        step1 = engine.narrow_range_postflop(btn_range, BOARD_K72, 'bet')
        step2 = engine.narrow_range_postflop(step1, BOARD_K72, 'raise')

        assert len(step2) <= len(step1) <= len(btn_range)

    def test_small_range_not_narrowed(self, engine):
        """小范围不收缩（防塌缩）"""
        small = Range.from_string("AA,KK")
        narrowed = engine.narrow_range_postflop(small, BOARD_K72, 'bet')
        assert len(narrowed) == len(small)

    def test_preflop_or_invalid_action_noop(self, engine):
        """无board或无效动作不收缩"""
        btn_range = engine.get_ideal_range(Position.BTN, [])
        assert engine.narrow_range_postflop(btn_range, [], 'bet') is btn_range
        assert engine.narrow_range_postflop(btn_range, BOARD_K72, 'fold') is btn_range


class TestStrongDrawDetection:

    def test_flush_draw(self, engine):
        board = [Card.from_str("Kh"), Card.from_str("7h"), Card.from_str("2c")]
        assert engine._has_strong_draw(Hand.from_str("AhQh"), board)
        assert not engine._has_strong_draw(Hand.from_str("AsQd"), board)

    def test_oesd(self, engine):
        board = [Card.from_str("9h"), Card.from_str("8c"), Card.from_str("2d")]
        assert engine._has_strong_draw(Hand.from_str("JsTs"), board), "JT on 982 是两头顺听"
        assert not engine._has_strong_draw(Hand.from_str("AsKd"), board)

    def test_no_draw_on_river(self, engine):
        board = [Card.from_str(s) for s in ("Kh", "7h", "2c", "3d", "9s")]
        assert not engine._has_strong_draw(Hand.from_str("AhQh"), board)


class TestVillainBaseRange:
    """DecisionIntegrator根据villain翻前行动定基准范围"""

    def setup_method(self):
        self.integrator = DecisionIntegrator(range_engine=RangeEngine())

    def _gs(self, villain_actions):
        return GameState(
            street='flop',
            position='BB',
            is_in_position=False,
            hero_hand=Hand.from_str("AsKh"),
            pot_size=5.0,
            effective_stack=100.0,
            hero_stack=100.0,
            villain_actions=villain_actions,
        )

    def test_villain_raised_gets_open_range(self):
        gs = self._gs([{'street': 'preflop', 'action': 'raise'}])
        r = self.integrator._estimate_villain_base_range(gs, Position.BTN, Position.BB)
        open_range = self.integrator.range_engine.get_ideal_range(Position.BTN, [])
        assert len(r) == len(open_range)

    def test_villain_called_gets_caller_range(self):
        gs = self._gs([{'street': 'preflop', 'action': 'call'}])
        r = self.integrator._estimate_villain_base_range(gs, Position.BTN, Position.BB)
        open_range = self.integrator.range_engine.get_ideal_range(Position.BTN, [])
        # 跟注范围应不同于（一般小于）open range，且不含AA（AA会3bet）
        assert len(r) != len(open_range)
        assert Hand.from_str("AsAh") not in r.to_hands(), "跟注范围不应含AA"


class TestPercentileWiring:
    """percentile从RangeEngine接入策略层"""

    def test_percentile_flows_to_strategy(self):
        from advisor.analysis.equity_engine import EquityEngine
        from advisor.analysis.board_analyzer import BoardAnalyzer

        integrator = DecisionIntegrator(
            range_engine=RangeEngine(),
            equity_engine=EquityEngine(),
            board_analyzer=BoardAnalyzer(),
        )
        gs = GameState(
            street='preflop',
            position='BTN',
            is_in_position=True,
            hero_hand=Hand.from_str("AsAh"),
            pot_size=1.5,
            effective_stack=100.0,
            hero_stack=100.0,
        )
        trace = integrator.decide(gs)
        # AA的percentile应接近1.0，且被策略使用（key_factors记录）
        p = trace.gto_decision.key_factors.get('hand_percentile')
        assert p is not None and p > 0.95, f"AA percentile应>0.95, 实际{p}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
