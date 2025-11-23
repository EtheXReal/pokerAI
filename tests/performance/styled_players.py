"""
特定风格的玩家 - 用于测试对手建模系统

每个玩家都有明确的统计特征，用于验证统计追踪的准确性：
- TAG (Tight-Aggressive): VPIP 20-25%, PFR 16-20%, AF 2.5-3.5
- LAG (Loose-Aggressive): VPIP 35-45%, PFR 21-31%, AF 2.5-3.5
- Nit (Tight-Passive): VPIP 15-20%, PFR 4-8%, AF 0.5-1.0
- Fish (Loose-Passive): VPIP 50-65%, PFR 10-19%, AF 0.5-1.0
"""
import random
from poker_env import Player, PlayerAction, GameState


class TAGPlayer(Player):
    """
    TAG (Tight-Aggressive) 玩家

    特征：
    - VPIP: 22% (紧)
    - PFR: 18% (PFR/VPIP = 82%)
    - AF: 3.0 (激进)
    - C-Bet: 75%
    - Fold to C-Bet: 45%
    """

    def __init__(self, name: str, seat: int, stack: float):
        super().__init__(name, seat, stack)
        self.was_preflop_raiser = False
        self.saw_flop = False

    def decide(self, game_state: GameState) -> PlayerAction:
        """TAG决策逻辑"""
        is_preflop = game_state.street == 'preflop'

        if is_preflop:
            self.was_preflop_raiser = False
            self.saw_flop = False
            return self._decide_preflop(game_state)
        else:
            if not self.saw_flop:
                self.saw_flop = True
            return self._decide_postflop(game_state)

    def _decide_preflop(self, game_state: GameState) -> PlayerAction:
        """翻前决策 - VPIP 22%, PFR 18%"""
        rand = random.random()

        if game_state.to_call == 0:
            # 无需跟注 (盲注位或所有人都弃牌)
            if rand < 0.22:  # VPIP 22%
                if random.random() < 0.82:  # PFR/VPIP = 82%
                    # Raise
                    self.was_preflop_raiser = True
                    raise_size = game_state.pot * random.uniform(2.5, 3.5)
                    return PlayerAction(action='bet', amount=min(raise_size, game_state.hero_stack))
                else:
                    # Limp (不常见，TAG偶尔limp)
                    return PlayerAction(action='check', amount=0)
            else:
                return PlayerAction(action='check', amount=0)
        else:
            # 面对下注
            if rand < 0.22:  # VPIP 22%
                if random.random() < 0.82:  # PFR/VPIP = 82%
                    # 3-bet
                    self.was_preflop_raiser = True
                    raise_size = game_state.facing_bet * random.uniform(2.5, 3.5)
                    return PlayerAction(action='raise', amount=min(raise_size, game_state.hero_stack))
                else:
                    # Call
                    return PlayerAction(action='call', amount=game_state.to_call)
            else:
                return PlayerAction(action='fold', amount=0)

    def _decide_postflop(self, game_state: GameState) -> PlayerAction:
        """翻后决策 - AF 3.0, C-Bet 75%"""
        rand = random.random()

        # 如果是翻前加注者且是翻牌圈第一次行动
        is_cbet_spot = (self.was_preflop_raiser and
                       game_state.street == 'flop' and
                       game_state.to_call == 0)

        if game_state.to_call == 0:
            # 无需跟注
            if is_cbet_spot:
                # C-bet spot: 75% 下注
                if rand < 0.75:
                    bet_size = game_state.pot * random.uniform(0.5, 0.75)
                    return PlayerAction(action='bet', amount=min(bet_size, game_state.hero_stack))
                else:
                    return PlayerAction(action='check', amount=0)
            else:
                # 一般情况: AF 3.0 -> bet/(bet+check+call) = 3/(3+1+0) = 0.75
                if rand < 0.60:  # 激进下注
                    bet_size = game_state.pot * random.uniform(0.5, 0.75)
                    return PlayerAction(action='bet', amount=min(bet_size, game_state.hero_stack))
                else:
                    return PlayerAction(action='check', amount=0)
        else:
            # 面对下注: AF 3.0 -> raise/(call+fold)
            # raise:call:fold = 0.75:0.20:0.05
            if rand < 0.45:  # Fold to C-bet: 45%
                return PlayerAction(action='fold', amount=0)
            elif rand < 0.90:  # Call: 45%
                return PlayerAction(action='call', amount=game_state.to_call)
            else:  # Raise: 10%
                raise_size = game_state.facing_bet * random.uniform(2.5, 3.5)
                return PlayerAction(action='raise', amount=min(raise_size, game_state.hero_stack))


class LAGPlayer(Player):
    """
    LAG (Loose-Aggressive) 玩家

    特征：
    - VPIP: 40%
    - PFR: 28% (PFR/VPIP = 70%)
    - AF: 3.0
    - C-Bet: 65%
    - Fold to C-Bet: 50%
    """

    def __init__(self, name: str, seat: int, stack: float):
        super().__init__(name, seat, stack)
        self.was_preflop_raiser = False
        self.saw_flop = False

    def decide(self, game_state: GameState) -> PlayerAction:
        """LAG决策逻辑"""
        is_preflop = game_state.street == 'preflop'

        if is_preflop:
            self.was_preflop_raiser = False
            self.saw_flop = False
            return self._decide_preflop(game_state)
        else:
            if not self.saw_flop:
                self.saw_flop = True
            return self._decide_postflop(game_state)

    def _decide_preflop(self, game_state: GameState) -> PlayerAction:
        """翻前决策 - VPIP 40%, PFR 28%"""
        rand = random.random()

        if game_state.to_call == 0:
            if rand < 0.40:  # VPIP 40%
                if random.random() < 0.70:  # PFR/VPIP = 70%
                    self.was_preflop_raiser = True
                    raise_size = game_state.pot * random.uniform(2.5, 3.5)
                    return PlayerAction(action='bet', amount=min(raise_size, game_state.hero_stack))
                else:
                    return PlayerAction(action='check', amount=0)
            else:
                return PlayerAction(action='check', amount=0)
        else:
            if rand < 0.40:  # VPIP 40%
                if random.random() < 0.70:  # PFR/VPIP = 70%
                    self.was_preflop_raiser = True
                    raise_size = game_state.facing_bet * random.uniform(2.5, 3.5)
                    return PlayerAction(action='raise', amount=min(raise_size, game_state.hero_stack))
                else:
                    return PlayerAction(action='call', amount=game_state.to_call)
            else:
                return PlayerAction(action='fold', amount=0)

    def _decide_postflop(self, game_state: GameState) -> PlayerAction:
        """翻后决策 - AF 3.0, C-Bet 65%"""
        rand = random.random()

        is_cbet_spot = (self.was_preflop_raiser and
                       game_state.street == 'flop' and
                       game_state.to_call == 0)

        if game_state.to_call == 0:
            if is_cbet_spot:
                if rand < 0.65:  # C-bet 65%
                    bet_size = game_state.pot * random.uniform(0.5, 0.75)
                    return PlayerAction(action='bet', amount=min(bet_size, game_state.hero_stack))
                else:
                    return PlayerAction(action='check', amount=0)
            else:
                if rand < 0.65:  # 激进
                    bet_size = game_state.pot * random.uniform(0.5, 0.75)
                    return PlayerAction(action='bet', amount=min(bet_size, game_state.hero_stack))
                else:
                    return PlayerAction(action='check', amount=0)
        else:
            if rand < 0.50:  # Fold to C-bet: 50%
                return PlayerAction(action='fold', amount=0)
            elif rand < 0.85:  # Call: 35%
                return PlayerAction(action='call', amount=game_state.to_call)
            else:  # Raise: 15%
                raise_size = game_state.facing_bet * random.uniform(2.5, 3.5)
                return PlayerAction(action='raise', amount=min(raise_size, game_state.hero_stack))


class NitPlayer(Player):
    """
    Nit (Tight-Passive) 玩家

    特征：
    - VPIP: 18%
    - PFR: 6% (PFR/VPIP = 33%)
    - AF: 0.7
    - C-Bet: 35%
    - Fold to C-Bet: 75%
    """

    def __init__(self, name: str, seat: int, stack: float):
        super().__init__(name, seat, stack)
        self.was_preflop_raiser = False
        self.saw_flop = False

    def decide(self, game_state: GameState) -> PlayerAction:
        """Nit决策逻辑"""
        is_preflop = game_state.street == 'preflop'

        if is_preflop:
            self.was_preflop_raiser = False
            self.saw_flop = False
            return self._decide_preflop(game_state)
        else:
            if not self.saw_flop:
                self.saw_flop = True
            return self._decide_postflop(game_state)

    def _decide_preflop(self, game_state: GameState) -> PlayerAction:
        """翻前决策 - VPIP 18%, PFR 6%"""
        rand = random.random()

        if game_state.to_call == 0:
            if rand < 0.18:  # VPIP 18%
                if random.random() < 0.33:  # PFR/VPIP = 33%
                    self.was_preflop_raiser = True
                    raise_size = game_state.pot * random.uniform(2.5, 3.0)
                    return PlayerAction(action='bet', amount=min(raise_size, game_state.hero_stack))
                else:
                    return PlayerAction(action='check', amount=0)
            else:
                return PlayerAction(action='check', amount=0)
        else:
            if rand < 0.18:  # VPIP 18%
                if random.random() < 0.33:  # PFR/VPIP = 33%
                    self.was_preflop_raiser = True
                    raise_size = game_state.facing_bet * random.uniform(2.5, 3.0)
                    return PlayerAction(action='raise', amount=min(raise_size, game_state.hero_stack))
                else:
                    return PlayerAction(action='call', amount=game_state.to_call)
            else:
                return PlayerAction(action='fold', amount=0)

    def _decide_postflop(self, game_state: GameState) -> PlayerAction:
        """翻后决策 - AF 0.7, C-Bet 35%"""
        rand = random.random()

        is_cbet_spot = (self.was_preflop_raiser and
                       game_state.street == 'flop' and
                       game_state.to_call == 0)

        if game_state.to_call == 0:
            if is_cbet_spot:
                if rand < 0.35:  # C-bet 35%
                    bet_size = game_state.pot * random.uniform(0.5, 0.75)
                    return PlayerAction(action='bet', amount=min(bet_size, game_state.hero_stack))
                else:
                    return PlayerAction(action='check', amount=0)
            else:
                if rand < 0.25:  # 被动，很少下注
                    bet_size = game_state.pot * random.uniform(0.5, 0.75)
                    return PlayerAction(action='bet', amount=min(bet_size, game_state.hero_stack))
                else:
                    return PlayerAction(action='check', amount=0)
        else:
            if rand < 0.75:  # Fold to C-bet: 75%
                return PlayerAction(action='fold', amount=0)
            elif rand < 0.97:  # Call: 22%
                return PlayerAction(action='call', amount=game_state.to_call)
            else:  # Raise: 3%
                raise_size = game_state.facing_bet * random.uniform(2.5, 3.0)
                return PlayerAction(action='raise', amount=min(raise_size, game_state.hero_stack))


class FishPlayer(Player):
    """
    Fish (Loose-Passive) 玩家

    特征：
    - VPIP: 58%
    - PFR: 14% (PFR/VPIP = 24%)
    - AF: 0.6
    - C-Bet: 25%
    - Fold to C-Bet: 65%
    """

    def __init__(self, name: str, seat: int, stack: float):
        super().__init__(name, seat, stack)
        self.was_preflop_raiser = False
        self.saw_flop = False

    def decide(self, game_state: GameState) -> PlayerAction:
        """Fish决策逻辑"""
        is_preflop = game_state.street == 'preflop'

        if is_preflop:
            self.was_preflop_raiser = False
            self.saw_flop = False
            return self._decide_preflop(game_state)
        else:
            if not self.saw_flop:
                self.saw_flop = True
            return self._decide_postflop(game_state)

    def _decide_preflop(self, game_state: GameState) -> PlayerAction:
        """翻前决策 - VPIP 58%, PFR 14%"""
        rand = random.random()

        if game_state.to_call == 0:
            if rand < 0.58:  # VPIP 58%
                if random.random() < 0.24:  # PFR/VPIP = 24%
                    self.was_preflop_raiser = True
                    raise_size = game_state.pot * random.uniform(2.0, 3.0)
                    return PlayerAction(action='bet', amount=min(raise_size, game_state.hero_stack))
                else:
                    return PlayerAction(action='check', amount=0)
            else:
                return PlayerAction(action='check', amount=0)
        else:
            if rand < 0.58:  # VPIP 58%
                if random.random() < 0.24:  # PFR/VPIP = 24%
                    self.was_preflop_raiser = True
                    raise_size = game_state.facing_bet * random.uniform(2.0, 3.0)
                    return PlayerAction(action='raise', amount=min(raise_size, game_state.hero_stack))
                else:
                    return PlayerAction(action='call', amount=game_state.to_call)
            else:
                return PlayerAction(action='fold', amount=0)

    def _decide_postflop(self, game_state: GameState) -> PlayerAction:
        """翻后决策 - AF 0.6, C-Bet 25%"""
        rand = random.random()

        is_cbet_spot = (self.was_preflop_raiser and
                       game_state.street == 'flop' and
                       game_state.to_call == 0)

        if game_state.to_call == 0:
            if is_cbet_spot:
                if rand < 0.25:  # C-bet 25%
                    bet_size = game_state.pot * random.uniform(0.5, 0.75)
                    return PlayerAction(action='bet', amount=min(bet_size, game_state.hero_stack))
                else:
                    return PlayerAction(action='check', amount=0)
            else:
                if rand < 0.20:  # 被动，很少下注
                    bet_size = game_state.pot * random.uniform(0.5, 0.75)
                    return PlayerAction(action='bet', amount=min(bet_size, game_state.hero_stack))
                else:
                    return PlayerAction(action='check', amount=0)
        else:
            if rand < 0.65:  # Fold to C-bet: 65%
                return PlayerAction(action='fold', amount=0)
            elif rand < 0.97:  # Call: 32%
                return PlayerAction(action='call', amount=game_state.to_call)
            else:  # Raise: 3%
                raise_size = game_state.facing_bet * random.uniform(2.0, 3.0)
                return PlayerAction(action='raise', amount=min(raise_size, game_state.hero_stack))
