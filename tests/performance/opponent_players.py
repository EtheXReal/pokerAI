#!/usr/bin/env python
"""
可插拔的对手玩家接口

定义了统一的对手接口，支持多种对手策略：
- RandomPlayer: 随机决策
- RuleBasedPlayer: 基于规则（未来实现）
- GTOPlayer: GTO策略（未来实现）
- ExploitativePlayer: 针对性策略（未来实现）
"""
import random
from abc import ABC, abstractmethod
from typing import Tuple


class OpponentPlayer(ABC):
    """对手玩家基类 - 定义统一接口"""

    def __init__(self, name: str = "Opponent"):
        self.name = name

    @abstractmethod
    def decide(self, pot: float, facing_bet: float, stack: float) -> Tuple[str, float]:
        """
        做决策

        Args:
            pot: 底池大小
            facing_bet: 面对的下注金额（0表示未面对下注）
            stack: 当前筹码量

        Returns:
            (action, amount) where:
                action: 'fold', 'check', 'call', 'bet', 'raise'
                amount: 下注金额（仅对bet/raise有效）
        """
        pass

    def reset(self):
        """重置对手状态（用于带记忆的对手）"""
        pass


class RandomPlayer(OpponentPlayer):
    """随机决策玩家"""

    def __init__(self, name: str = "Random",
                 fold_rate: float = 0.4,
                 raise_rate: float = 0.2):
        """
        Args:
            name: 玩家名称
            fold_rate: 面对下注时fold的概率（0-1）
            raise_rate: 面对下注时raise的概率，剩余为call
                       未面对下注时bet的概率，剩余为check
        """
        super().__init__(name)
        self.fold_rate = fold_rate
        self.raise_rate = raise_rate

    def decide(self, pot: float, facing_bet: float, stack: float) -> Tuple[str, float]:
        """
        随机决策
        - 未面对下注: raise_rate% bet, (1-raise_rate)% check
        - 面对下注: fold_rate% fold, raise_rate% raise, 剩余% call

        Returns:
            (action, amount)
        """
        r = random.random()

        if facing_bet > 0:
            # 面对下注
            if r < self.fold_rate:
                return 'fold', 0.0
            elif r < self.fold_rate + self.raise_rate:
                # Raise: 随机尺度 2.0-3.5x
                raise_size = facing_bet * random.uniform(2.0, 3.5)
                return 'raise', min(raise_size, stack)
            else:
                # Call
                return 'call', 0.0
        else:
            # 未面对下注
            if r < self.raise_rate:
                # Bet: 随机尺度 0.33-1.0 pot
                bet_size = pot * random.uniform(0.33, 1.0)
                return 'bet', min(bet_size, stack)
            else:
                return 'check', 0.0


class PassivePlayer(OpponentPlayer):
    """被动玩家 - 很少主动下注，经常call"""

    def __init__(self, name: str = "Passive"):
        super().__init__(name)

    def decide(self, pot: float, facing_bet: float, stack: float) -> Tuple[str, float]:
        """
        被动策略：
        - 未面对下注: 10% bet, 90% check
        - 面对下注: 30% fold, 5% raise, 65% call
        """
        r = random.random()

        if facing_bet > 0:
            if r < 0.30:
                return 'fold', 0.0
            elif r < 0.35:
                raise_size = facing_bet * random.uniform(2.0, 3.0)
                return 'raise', min(raise_size, stack)
            else:
                return 'call', 0.0
        else:
            if r < 0.10:
                bet_size = pot * random.uniform(0.5, 0.75)
                return 'bet', min(bet_size, stack)
            else:
                return 'check', 0.0


class AggressivePlayer(OpponentPlayer):
    """激进玩家 - 经常下注和加注"""

    def __init__(self, name: str = "Aggressive"):
        super().__init__(name)

    def decide(self, pot: float, facing_bet: float, stack: float) -> Tuple[str, float]:
        """
        激进策略：
        - 未面对下注: 70% bet, 30% check
        - 面对下注: 20% fold, 40% raise, 40% call
        """
        r = random.random()

        if facing_bet > 0:
            if r < 0.20:
                return 'fold', 0.0
            elif r < 0.60:
                raise_size = facing_bet * random.uniform(2.5, 4.0)
                return 'raise', min(raise_size, stack)
            else:
                return 'call', 0.0
        else:
            if r < 0.70:
                bet_size = pot * random.uniform(0.66, 1.5)
                return 'bet', min(bet_size, stack)
            else:
                return 'check', 0.0


class TightPlayer(OpponentPlayer):
    """紧凶玩家 - 很少进池，但进池后很激进"""

    def __init__(self, name: str = "Tight"):
        super().__init__(name)

    def decide(self, pot: float, facing_bet: float, stack: float) -> Tuple[str, float]:
        """
        紧凶策略：
        - 未面对下注: 50% bet (大尺度), 50% check
        - 面对下注: 50% fold, 30% raise (大尺度), 20% call
        """
        r = random.random()

        if facing_bet > 0:
            if r < 0.50:
                return 'fold', 0.0
            elif r < 0.80:
                raise_size = facing_bet * random.uniform(3.0, 4.5)
                return 'raise', min(raise_size, stack)
            else:
                return 'call', 0.0
        else:
            if r < 0.50:
                bet_size = pot * random.uniform(0.75, 1.5)
                return 'bet', min(bet_size, stack)
            else:
                return 'check', 0.0


# 工厂函数
def create_opponent(opponent_type: str = "random", **kwargs) -> OpponentPlayer:
    """
    创建对手玩家

    Args:
        opponent_type: 对手类型
            - 'random': 随机玩家
            - 'passive': 被动玩家
            - 'aggressive': 激进玩家
            - 'tight': 紧凶玩家
        **kwargs: 传递给对手构造函数的参数

    Returns:
        OpponentPlayer实例
    """
    opponent_map = {
        'random': RandomPlayer,
        'passive': PassivePlayer,
        'aggressive': AggressivePlayer,
        'tight': TightPlayer,
    }

    opponent_class = opponent_map.get(opponent_type.lower())
    if not opponent_class:
        raise ValueError(f"Unknown opponent type: {opponent_type}. "
                        f"Available: {list(opponent_map.keys())}")

    return opponent_class(**kwargs)
