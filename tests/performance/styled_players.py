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
        """翻前决策 - VPIP 22%, PFR 18%, 3-bet ~6%"""
        rand = random.random()

        # 区分：面对BB vs 面对raise
        facing_raise = game_state.facing_bet > 1.0  # BB = 1.0

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
        elif not facing_raise:
            # 面对BB但没有raise（可以open raise）
            if rand < 0.22:  # VPIP 22%
                if random.random() < 0.82:  # PFR/VPIP = 82%
                    # Open raise
                    self.was_preflop_raiser = True
                    raise_size = game_state.facing_bet * random.uniform(2.5, 3.5)
                    return PlayerAction(action='raise', amount=min(raise_size, game_state.hero_stack))
                else:
                    # Limp (call BB)
                    return PlayerAction(action='call', amount=game_state.to_call)
            else:
                return PlayerAction(action='fold', amount=0)
        else:
            # 面对raise（真正的3-bet决策）
            # TAG面对raise时收紧：只用~7%最强牌，其中90%是3-bet
            if rand < 0.07:  # 面对raise时的范围
                if random.random() < 0.90:  # 90% 3-bet, 10% call
                    # 3-bet
                    self.was_preflop_raiser = True
                    raise_size = game_state.facing_bet * random.uniform(2.5, 3.5)
                    return PlayerAction(action='raise', amount=min(raise_size, game_state.hero_stack))
                else:
                    # Call (用于平衡)
                    return PlayerAction(action='call', amount=game_state.to_call)
            else:
                return PlayerAction(action='fold', amount=0)

    def _decide_postflop(self, game_state: GameState) -> PlayerAction:
        """翻后决策 - AF 3.0, C-Bet 75%"""
        rand = random.random()

        # C-bet逻辑：翻前加注者在翻牌圈
        is_cbet_situation = (self.was_preflop_raiser and game_state.street == 'flop')

        if game_state.to_call == 0:
            # 无需跟注
            if is_cbet_situation:
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
            # 面对下注 - C-bet opportunity已失去（别人先下注了）
            # 按正常策略应对: Fold to C-bet 45%, Call 45%, Raise 10%
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
        """翻前决策 - VPIP 40%, PFR 28%, 3-bet ~10%"""
        rand = random.random()

        # 区分：面对BB vs 面对raise
        facing_raise = game_state.facing_bet > 1.0  # BB = 1.0

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
        elif not facing_raise:
            # 面对BB但没有raise（可以open raise）
            if rand < 0.40:  # VPIP 40%
                if random.random() < 0.70:  # PFR/VPIP = 70%
                    # Open raise
                    self.was_preflop_raiser = True
                    raise_size = game_state.facing_bet * random.uniform(2.5, 3.5)
                    return PlayerAction(action='raise', amount=min(raise_size, game_state.hero_stack))
                else:
                    # Limp (call BB)
                    return PlayerAction(action='call', amount=game_state.to_call)
            else:
                return PlayerAction(action='fold', amount=0)
        else:
            # 面对raise（真正的3-bet决策）
            # LAG面对raise时：用~12%牌，其中85%是3-bet
            if rand < 0.12:  # 面对raise时的范围
                if random.random() < 0.85:  # 85% 3-bet, 15% call
                    # 3-bet
                    self.was_preflop_raiser = True
                    raise_size = game_state.facing_bet * random.uniform(2.5, 3.5)
                    return PlayerAction(action='raise', amount=min(raise_size, game_state.hero_stack))
                else:
                    # Call (用于平衡)
                    return PlayerAction(action='call', amount=game_state.to_call)
            else:
                return PlayerAction(action='fold', amount=0)

    def _decide_postflop(self, game_state: GameState) -> PlayerAction:
        """翻后决策 - AF 3.0, C-Bet 65%"""
        rand = random.random()

        is_cbet_situation = (self.was_preflop_raiser and game_state.street == 'flop')

        if game_state.to_call == 0:
            if is_cbet_situation:
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
            # 面对下注 - C-bet opportunity已失去（别人先下注了）
            # 按正常策略应对: Fold to C-bet 50%, Call 35%, Raise 15%
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
        """翻前决策 - VPIP 18%, PFR 6%, 3-bet ~2%"""
        rand = random.random()

        # 区分：面对BB vs 面对raise
        facing_raise = game_state.facing_bet > 1.0  # BB = 1.0

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
        elif not facing_raise:
            # 面对BB但没有raise（可以open raise）
            if rand < 0.18:  # VPIP 18%
                if random.random() < 0.33:  # PFR/VPIP = 33%
                    # Open raise
                    self.was_preflop_raiser = True
                    raise_size = game_state.facing_bet * random.uniform(2.5, 3.0)
                    return PlayerAction(action='raise', amount=min(raise_size, game_state.hero_stack))
                else:
                    # Limp (call BB)
                    return PlayerAction(action='call', amount=game_state.to_call)
            else:
                return PlayerAction(action='fold', amount=0)
        else:
            # 面对raise（真正的3-bet决策）
            # Nit面对raise时非常紧：只用~3%最强牌，其中70%是3-bet
            if rand < 0.03:  # 面对raise时的范围
                if random.random() < 0.70:  # 70% 3-bet, 30% call
                    # 3-bet
                    self.was_preflop_raiser = True
                    raise_size = game_state.facing_bet * random.uniform(2.5, 3.0)
                    return PlayerAction(action='raise', amount=min(raise_size, game_state.hero_stack))
                else:
                    # Call (用于平衡)
                    return PlayerAction(action='call', amount=game_state.to_call)
            else:
                return PlayerAction(action='fold', amount=0)

    def _decide_postflop(self, game_state: GameState) -> PlayerAction:
        """翻后决策 - AF 0.7, C-Bet 35%"""
        rand = random.random()

        is_cbet_situation = (self.was_preflop_raiser and game_state.street == 'flop')

        if game_state.to_call == 0:
            if is_cbet_situation:
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
            # 面对下注 - C-bet opportunity已失去（别人先下注了）
            # 按正常策略应对: Fold to C-bet 75%, Call 22%, Raise 3%
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
        """翻前决策 - VPIP 58%, PFR 14%, 3-bet ~5%"""
        rand = random.random()

        # 区分：面对BB vs 面对raise
        facing_raise = game_state.facing_bet > 1.0  # BB = 1.0

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
        elif not facing_raise:
            # 面对BB但没有raise（可以open raise）
            if rand < 0.58:  # VPIP 58%
                if random.random() < 0.24:  # PFR/VPIP = 24%
                    # Open raise
                    self.was_preflop_raiser = True
                    raise_size = game_state.facing_bet * random.uniform(2.0, 3.0)
                    return PlayerAction(action='raise', amount=min(raise_size, game_state.hero_stack))
                else:
                    # Limp (call BB)
                    return PlayerAction(action='call', amount=game_state.to_call)
            else:
                return PlayerAction(action='fold', amount=0)
        else:
            # 面对raise（真正的3-bet决策）
            # Fish面对raise时：用~10%牌（太宽），其中50%是3-bet（被动）
            if rand < 0.10:  # 面对raise时的范围
                if random.random() < 0.50:  # 50% 3-bet, 50% call（Fish很被动）
                    # 3-bet
                    self.was_preflop_raiser = True
                    raise_size = game_state.facing_bet * random.uniform(2.0, 3.0)
                    return PlayerAction(action='raise', amount=min(raise_size, game_state.hero_stack))
                else:
                    # Call (Fish喜欢call)
                    return PlayerAction(action='call', amount=game_state.to_call)
            else:
                return PlayerAction(action='fold', amount=0)

    def _decide_postflop(self, game_state: GameState) -> PlayerAction:
        """翻后决策 - AF 0.6, C-Bet 25%"""
        rand = random.random()

        is_cbet_situation = (self.was_preflop_raiser and game_state.street == 'flop')

        if game_state.to_call == 0:
            if is_cbet_situation:
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
            # 面对下注 - C-bet opportunity已失去（别人先下注了）
            # 按正常策略应对: Fold to C-bet 65%, Call 32%, Raise 3%
            if rand < 0.65:  # Fold to C-bet: 65%
                return PlayerAction(action='fold', amount=0)
            elif rand < 0.97:  # Call: 32%
                return PlayerAction(action='call', amount=game_state.to_call)
            else:  # Raise: 3%
                raise_size = game_state.facing_bet * random.uniform(2.0, 3.0)
                return PlayerAction(action='raise', amount=min(raise_size, game_state.hero_stack))
