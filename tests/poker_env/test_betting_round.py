"""
Betting round回合完成逻辑的回归测试

覆盖2026-07修复的三个连环缺陷（用户实战发现"all-in只输1BB"）：
1. all-in后对手从未被要求应对（回合结束判定无视all-in注）
2. "只剩一个非all-in玩家"被误判为"其他人都弃牌"直接判胜
3. SB limp后BB的option被跳过
"""

import pytest

from poker_env import PokerGame, GameConfig, Player, PlayerAction


class AllInPlayer(Player):
    """永远all-in"""
    def decide(self, gs):
        if gs.to_call > 0.01:
            return PlayerAction('raise', gs.hero_stack - gs.to_call)
        return PlayerAction('bet', gs.hero_stack)


class CallerPlayer(Player):
    """永远call/check，记录被询问次数"""
    def __init__(self, *a):
        super().__init__(*a)
        self.asked = 0

    def decide(self, gs):
        self.asked += 1
        return PlayerAction('call' if gs.to_call > 0.01 else 'check', 0.0)


class FolderPlayer(Player):
    """面对下注就fold"""
    def __init__(self, *a):
        super().__init__(*a)
        self.asked = 0

    def decide(self, gs):
        self.asked += 1
        return PlayerAction('fold' if gs.to_call > 0.01 else 'check', 0.0)


def make_game(p0, p1):
    return PokerGame([p0, p1], GameConfig(
        num_players=2, starting_stack=100.0,
        small_blind=0.5, big_blind=1.0, verbose=False))


class TestAllInResponse:

    def test_allin_must_be_answered_and_pot_full(self):
        """all-in后对手必须获得应对机会；被call后底池是全额"""
        allin = AllInPlayer('AllIn', 0, 100.0)
        caller = CallerPlayer('Caller', 1, 100.0)
        r = make_game(allin, caller).play_hand(0, btn_seat=0, seed=99)

        assert caller.asked >= 1, "对手必须被要求应对all-in"
        assert r.pot == pytest.approx(200.0), f"call all-in后底池应为200, 实际{r.pot}"
        assert abs(r.player_profits[0]) == pytest.approx(100.0), \
            f"输家应输整个100BB, 实际{r.player_profits}"

    def test_fold_to_allin_wins_blinds_only(self):
        """对手fold时all-in方只赢盲注，未被跟的注退回"""
        allin = AllInPlayer('AllIn', 0, 100.0)
        folder = FolderPlayer('Folder', 1, 100.0)
        r = make_game(allin, folder).play_hand(0, btn_seat=0, seed=99)

        assert folder.asked >= 1
        assert r.player_profits[0] == pytest.approx(1.0), \
            f"fold后all-in方应只赢1BB盲注, 实际{r.player_profits}"
        assert not r.showdown

    def test_allin_not_declared_loser_by_default(self):
        """all-in玩家仍是active，不能因'无法行动'被判负"""
        allin = AllInPlayer('AllIn', 0, 100.0)
        caller = CallerPlayer('Caller', 1, 100.0)
        r = make_game(allin, caller).play_hand(0, btn_seat=0, seed=99)

        # 必须走到摊牌决定胜负
        assert r.showdown, "all-in被call后必须摊牌"


class TestBBOption:

    def test_bb_gets_option_after_limp(self):
        """SB limp后BB必须获得行动机会（option）"""
        class LimpPlayer(Player):
            def decide(self, gs):
                return PlayerAction('call' if gs.to_call > 0.01 else 'check', 0.0)

        class BBCounter(Player):
            def __init__(self, *a):
                super().__init__(*a)
                self.preflop_asked = 0

            def decide(self, gs):
                if gs.street == 'preflop':
                    self.preflop_asked += 1
                return PlayerAction('check' if gs.to_call <= 0.01 else 'call', 0.0)

        limper = LimpPlayer('Limper', 0, 100.0)
        bb = BBCounter('BB', 1, 100.0)
        make_game(limper, bb).play_hand(0, btn_seat=0, seed=7)

        assert bb.preflop_asked >= 1, "BB在limped pot必须获得option"


class TestChipConservation:

    def test_chips_conserved_over_many_hands(self):
        """多手随机对局筹码守恒（双方盈亏之和为0）"""
        import random as _r

        class RandomActor(Player):
            def __init__(self, *a):
                super().__init__(*a)
                self.rng = _r.Random(self.name)

            def decide(self, gs):
                r = self.rng.random()
                if gs.to_call > 0.01:
                    if r < 0.3:
                        return PlayerAction('fold', 0.0)
                    if r < 0.5:
                        return PlayerAction('raise', min(gs.to_call * 2, gs.hero_stack - gs.to_call))
                    return PlayerAction('call', 0.0)
                if r < 0.4:
                    return PlayerAction('bet', min(gs.pot * 0.75, gs.hero_stack))
                return PlayerAction('check', 0.0)

        p0 = RandomActor('R0', 0, 100.0)
        p1 = RandomActor('R1', 1, 100.0)
        game = make_game(p0, p1)
        for i in range(50):
            r = game.play_hand(i, btn_seat=i % 2, seed=31337 + i)
            assert sum(r.player_profits) == pytest.approx(0.0, abs=0.02), \
                f"第{i}手筹码不守恒: {r.player_profits}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
