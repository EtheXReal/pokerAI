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
        """翻前决策 - VPIP 22%, PFR 18%, 3-bet ~6%

        注意：在2人游戏中调整facing raise范围以维持目标VPIP
        """
        rand = random.random()

        # 检测2人游戏
        is_heads_up = game_state.num_active_players == 2

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
            # BUG FIX: 在2人游戏中，TAG需要放宽范围以维持22% VPIP
            if is_heads_up:
                # 2人游戏：使用接近目标VPIP的范围
                facing_raise_range = 0.20  # 20%范围（稍紧因为有风险）
            else:
                # 多人游戏：较紧
                facing_raise_range = 0.07

            if rand < facing_raise_range:
                # TAG激进地3-bet
                if random.random() < 0.70:  # 70% 3-bet
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
        """翻前决策 - VPIP 40%, PFR 28%, 3-bet ~10%

        注意：在2人游戏中调整facing raise范围以维持目标VPIP
        """
        rand = random.random()

        # 检测2人游戏
        is_heads_up = game_state.num_active_players == 2

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
            # BUG FIX: 在2人游戏中，LAG需要放宽范围以维持40% VPIP
            if is_heads_up:
                # 2人游戏：使用接近目标VPIP的范围
                facing_raise_range = 0.38  # 38%范围（稍紧因为有风险）
            else:
                # 多人游戏：较紧
                facing_raise_range = 0.12

            if rand < facing_raise_range:
                # LAG激进地3-bet
                if random.random() < 0.60:  # 60% 3-bet
                    # 3-bet
                    self.was_preflop_raiser = True
                    raise_size = game_state.facing_bet * random.uniform(2.5, 3.5)
                    return PlayerAction(action='raise', amount=min(raise_size, game_state.hero_stack))
                else:
                    # Call (LAG也会call一些)
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
        """翻前决策 - VPIP 18%, PFR 6%, 3-bet ~2%

        注意：在2人游戏中需要稍微放宽facing raise范围
        Nit即使在heads-up中也非常紧，但不能完全不玩
        """
        rand = random.random()

        # 检测2人游戏
        is_heads_up = game_state.num_active_players == 2

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
            # BUG FIX: 在2人游戏中，Nit需要稍微放宽范围，否则VPIP会过低
            if is_heads_up:
                # 2人游戏：使用稍宽的范围（但仍然很紧）
                facing_raise_range = 0.15  # 15%范围（Nit在heads-up中仍然很紧）
            else:
                # 多人游戏：极紧
                facing_raise_range = 0.03

            if rand < facing_raise_range:
                # Nit大部分是call，少量3-bet
                if random.random() < 0.20:  # 20% 3-bet
                    # 3-bet
                    self.was_preflop_raiser = True
                    raise_size = game_state.facing_bet * random.uniform(2.5, 3.0)
                    return PlayerAction(action='raise', amount=min(raise_size, game_state.hero_stack))
                else:
                    # Call (Nit主要是call)
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
        """翻前决策 - VPIP 58%, PFR 14%, 3-bet ~5%

        注意：在2人游戏中，我们需要调整facing raise时的范围，
        因为你总是在盲注位，且经常面对raise。
        为了维持58% VPIP，我们需要：
        - 从Button (SB): 58% VPIP (limp/raise)
        - 从BB facing raise: 也需要~58% VPIP (call/3bet)
        """
        rand = random.random()

        # 检测2人游戏：如果只有2个active players
        is_heads_up = game_state.num_active_players == 2

        # 区分：面对BB vs 面对raise
        facing_raise = game_state.facing_bet > 1.0  # BB = 1.0

        if game_state.to_call == 0:
            # BB position, no raise yet (can check or bet)
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
            # Button/SB position or can open raise
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
            # Facing a raise
            # BUG FIX: 在2人游戏中，Fish应该用更宽的范围面对raise
            # 否则整体VPIP会远低于目标58%
            if is_heads_up:
                # 2人游戏：使用接近目标VPIP的范围（稍微紧一点因为有风险）
                facing_raise_range = 0.55  # 略低于58%因为面对raise
            else:
                # 多人游戏：更紧的范围
                facing_raise_range = 0.10

            if rand < facing_raise_range:
                # Fish很被动，大部分是call，少量3-bet
                if random.random() < 0.10:  # 只有10%是3-bet（Fish不爱加注）
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


class CallingStationPlayer(Player):
    """
    Calling Station (超级被动跟注站)

    特征：
    - VPIP: 65% (玩几乎所有牌)
    - PFR: 8% (几乎不加注)
    - AF: 0.4 (极被动)
    - C-Bet: 20%
    - Fold to C-Bet: 25% (几乎不弃牌)
    """

    def __init__(self, name: str, seat: int, stack: float):
        super().__init__(name, seat, stack)
        self.was_preflop_raiser = False
        self.saw_flop = False

    def decide(self, game_state: GameState) -> PlayerAction:
        """Calling Station决策逻辑"""
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
        """翻前决策 - VPIP 65%, PFR 8%

        注意：在2人游戏中调整facing raise范围以维持目标VPIP
        Calling Station的特点是几乎从不弃牌，喜欢call
        """
        rand = random.random()

        # 检测2人游戏
        is_heads_up = game_state.num_active_players == 2
        facing_raise = game_state.facing_bet > 1.0

        if game_state.to_call == 0:
            if rand < 0.65:  # VPIP 65%
                if random.random() < 0.12:  # PFR/VPIP = 12%
                    self.was_preflop_raiser = True
                    raise_size = game_state.pot * random.uniform(2.0, 2.5)
                    return PlayerAction(action='bet', amount=min(raise_size, game_state.hero_stack))
                else:
                    return PlayerAction(action='check', amount=0)
            else:
                return PlayerAction(action='check', amount=0)
        elif not facing_raise:
            if rand < 0.65:
                if random.random() < 0.12:
                    self.was_preflop_raiser = True
                    raise_size = game_state.facing_bet * random.uniform(2.0, 2.5)
                    return PlayerAction(action='raise', amount=min(raise_size, game_state.hero_stack))
                else:
                    return PlayerAction(action='call', amount=game_state.to_call)
            else:
                return PlayerAction(action='fold', amount=0)
        else:
            # 面对raise：几乎总是call（很少弃牌或3-bet）
            # BUG FIX: 在2人游戏中，Calling Station应该几乎从不弃牌
            if is_heads_up:
                # 2人游戏：65% VPIP，几乎全是call（极被动）
                if rand < 0.03:  # 只有3% fold
                    return PlayerAction(action='fold', amount=0)
                elif rand < 0.95:  # 92% call (calling station核心特征)
                    return PlayerAction(action='call', amount=game_state.to_call)
                else:  # 5% 3-bet
                    self.was_preflop_raiser = True
                    raise_size = game_state.facing_bet * random.uniform(2.0, 2.5)
                    return PlayerAction(action='raise', amount=min(raise_size, game_state.hero_stack))
            else:
                # 多人游戏：稍微紧一点
                if rand < 0.10:  # 10% fold
                    return PlayerAction(action='fold', amount=0)
                elif rand < 0.95:  # 85% call
                    return PlayerAction(action='call', amount=game_state.to_call)
                else:  # 5% 3-bet
                    self.was_preflop_raiser = True
                    raise_size = game_state.facing_bet * random.uniform(2.0, 2.5)
                    return PlayerAction(action='raise', amount=min(raise_size, game_state.hero_stack))

    def _decide_postflop(self, game_state: GameState) -> PlayerAction:
        """翻后决策 - AF 0.4, 几乎不弃牌"""
        rand = random.random()
        is_cbet_situation = (self.was_preflop_raiser and game_state.street == 'flop')

        if game_state.to_call == 0:
            if is_cbet_situation:
                if rand < 0.20:  # C-bet 20%
                    bet_size = game_state.pot * random.uniform(0.5, 0.75)
                    return PlayerAction(action='bet', amount=min(bet_size, game_state.hero_stack))
                else:
                    return PlayerAction(action='check', amount=0)
            else:
                if rand < 0.15:  # 极被动
                    bet_size = game_state.pot * random.uniform(0.5, 0.75)
                    return PlayerAction(action='bet', amount=min(bet_size, game_state.hero_stack))
                else:
                    return PlayerAction(action='check', amount=0)
        else:
            # 面对下注：几乎总是call（Calling Station特征）
            if rand < 0.25:  # 只有25% fold
                return PlayerAction(action='fold', amount=0)
            elif rand < 0.97:  # 72% call
                return PlayerAction(action='call', amount=game_state.to_call)
            else:  # 3% raise
                raise_size = game_state.facing_bet * random.uniform(2.0, 2.5)
                return PlayerAction(action='raise', amount=min(raise_size, game_state.hero_stack))


class ManiacPlayer(Player):
    """
    Maniac (疯狂激进玩家)

    特征：
    - VPIP: 75% (玩几乎所有牌)
    - PFR: 60% (疯狂加注)
    - AF: 5.0 (极度激进)
    - C-Bet: 90%
    - Fold to C-Bet: 30%
    - 3-bet: 25%
    """

    def __init__(self, name: str, seat: int, stack: float):
        super().__init__(name, seat, stack)
        self.was_preflop_raiser = False
        self.saw_flop = False

    def decide(self, game_state: GameState) -> PlayerAction:
        """Maniac决策逻辑"""
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
        """翻前决策 - VPIP 75%, PFR 60%

        注意：在2人游戏中调整facing raise范围以维持目标VPIP
        """
        rand = random.random()

        # 检测2人游戏
        is_heads_up = game_state.num_active_players == 2
        facing_raise = game_state.facing_bet > 1.0

        if game_state.to_call == 0:
            if rand < 0.75:  # VPIP 75%
                if random.random() < 0.80:  # PFR/VPIP = 80%
                    self.was_preflop_raiser = True
                    raise_size = game_state.pot * random.uniform(3.0, 5.0)
                    return PlayerAction(action='bet', amount=min(raise_size, game_state.hero_stack))
                else:
                    return PlayerAction(action='check', amount=0)
            else:
                return PlayerAction(action='check', amount=0)
        elif not facing_raise:
            if rand < 0.75:
                if random.random() < 0.80:
                    self.was_preflop_raiser = True
                    raise_size = game_state.facing_bet * random.uniform(3.0, 5.0)
                    return PlayerAction(action='raise', amount=min(raise_size, game_state.hero_stack))
                else:
                    return PlayerAction(action='call', amount=game_state.to_call)
            else:
                return PlayerAction(action='fold', amount=0)
        else:
            # 面对raise：疯狂3-bet
            # BUG FIX: 在2人游戏中，Maniac应该几乎从不弃牌
            if is_heads_up:
                # 2人游戏：75% VPIP，非常激进地面对raise
                if rand < 0.05:  # 只有5% fold
                    return PlayerAction(action='fold', amount=0)
                elif rand < 0.30:  # 25% call
                    return PlayerAction(action='call', amount=game_state.to_call)
                else:  # 70% 3-bet (疯狂激进)
                    self.was_preflop_raiser = True
                    raise_size = game_state.facing_bet * random.uniform(3.0, 5.0)
                    return PlayerAction(action='raise', amount=min(raise_size, game_state.hero_stack))
            else:
                # 多人游戏：稍微紧一点
                if rand < 0.20:  # 20% fold
                    return PlayerAction(action='fold', amount=0)
                elif rand < 0.50:  # 30% call
                    return PlayerAction(action='call', amount=game_state.to_call)
                else:  # 50% 3-bet
                    self.was_preflop_raiser = True
                    raise_size = game_state.facing_bet * random.uniform(3.0, 5.0)
                    return PlayerAction(action='raise', amount=min(raise_size, game_state.hero_stack))

    def _decide_postflop(self, game_state: GameState) -> PlayerAction:
        """翻后决策 - AF 5.0, C-Bet 90%"""
        rand = random.random()
        is_cbet_situation = (self.was_preflop_raiser and game_state.street == 'flop')

        if game_state.to_call == 0:
            if is_cbet_situation:
                if rand < 0.90:  # C-bet 90%
                    bet_size = game_state.pot * random.uniform(0.75, 1.5)
                    return PlayerAction(action='bet', amount=min(bet_size, game_state.hero_stack))
                else:
                    return PlayerAction(action='check', amount=0)
            else:
                if rand < 0.80:  # 极度激进
                    bet_size = game_state.pot * random.uniform(0.75, 1.5)
                    return PlayerAction(action='bet', amount=min(bet_size, game_state.hero_stack))
                else:
                    return PlayerAction(action='check', amount=0)
        else:
            # 面对下注：经常raise
            if rand < 0.30:  # 30% fold
                return PlayerAction(action='fold', amount=0)
            elif rand < 0.55:  # 25% call
                return PlayerAction(action='call', amount=game_state.to_call)
            else:  # 45% raise
                raise_size = game_state.facing_bet * random.uniform(3.0, 5.0)
                return PlayerAction(action='raise', amount=min(raise_size, game_state.hero_stack))


def create_styled_player(style: str, name: str = None, seat: int = 0, stack: float = 100.0) -> Player:
    """
    创建特定风格的玩家

    Args:
        style: 玩家风格 ('tag', 'lag', 'nit', 'fish', 'calling_station', 'maniac')
        name: 玩家名称
        seat: 座位号
        stack: 筹码量

    Returns:
        Player实例
    """
    style = style.lower()
    if name is None:
        name = style.upper()

    style_map = {
        'tag': TAGPlayer,
        'lag': LAGPlayer,
        'nit': NitPlayer,
        'fish': FishPlayer,
        'calling_station': CallingStationPlayer,
        'maniac': ManiacPlayer,
    }

    player_class = style_map.get(style)
    if not player_class:
        raise ValueError(f"Unknown player style: {style}. Available: {list(style_map.keys())}")

    return player_class(name, seat, stack)
