"""
Player Interface for Poker Environment
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Tuple, Optional
from poker_core import Hand, Board
from .utils import ALLIN_THRESHOLD, round_amount, ZERO_THRESHOLD


@dataclass
class PlayerAction:
    """玩家行动"""
    action: str  # 'fold', 'check', 'call', 'bet', 'raise'
    amount: float  # 对于bet/raise，是raise增量（不是raise to的总额）


class Player(ABC):
    """
    玩家基类

    所有玩家实现（AI、对手、人类）都应该继承这个类
    """

    def __init__(self, name: str, seat: int, stack: float):
        """
        Args:
            name: 玩家名称
            seat: 座位索引（0开始）
            stack: 起始筹码量
        """
        self.name = name
        self.seat = seat
        self.stack = stack
        self.invested = 0.0  # 本手牌总投入
        self.street_invested = 0.0  # 当前街道投入
        self.hand: Optional[Hand] = None
        self.is_active = True  # 是否还在游戏中（未fold）
        self.is_allin = False  # 是否all-in

    @abstractmethod
    def decide(self, game_state: 'GameState') -> PlayerAction:
        """
        做决策

        Args:
            game_state: 当前游戏状态

        Returns:
            PlayerAction对象
        """
        pass

    def on_hand_complete(self, game_result: 'GameResult') -> None:
        """
        手牌结束时的回调（生命周期钩子）

        当一手牌结束时，poker_env会调用此方法通知玩家。
        AI玩家可以利用此机会更新对手建模数据。

        默认实现：什么都不做（对于不需要学习的玩家，如RandomPlayer）

        Args:
            game_result: 手牌结果，包含所有行动、赢家、公共牌等信息
        """
        pass  # 默认不做任何事

    def reset_for_new_street(self):
        """新街道开始时重置"""
        self.street_invested = 0.0

    def reset_for_new_hand(self, stack: float):
        """新手牌开始时重置"""
        self.stack = stack
        self.invested = 0.0
        self.street_invested = 0.0
        self.hand = None
        self.is_active = True
        self.is_allin = False

    def invest(self, amount: float):
        """投入筹码"""
        amount = round_amount(min(amount, self.stack))
        self.stack = round_amount(self.stack - amount)
        self.invested = round_amount(self.invested + amount)
        self.street_invested = round_amount(self.street_invested + amount)

        # 检查是否all-in（使用统一的ALLIN_THRESHOLD）
        if self.stack <= ALLIN_THRESHOLD:
            self.is_allin = True
            self.stack = 0.0  # 精确归零

        return amount

    def return_chips(self, amount: float):
        """退回筹码（uncalled bet）"""
        amount = round_amount(amount)
        self.stack = round_amount(self.stack + amount)
        self.invested = round_amount(self.invested - amount)
        self.street_invested = round_amount(self.street_invested - amount)

    def __str__(self):
        return f"{self.name}(seat={self.seat}, stack={self.stack:.2f}BB)"


@dataclass
class GameState:
    """
    游戏状态（传递给玩家的决策接口）
    """
    # 街道信息
    street: str  # 'preflop', 'flop', 'turn', 'river'

    # 玩家信息
    player: Player  # 当前决策的玩家
    position: str  # 位置名称 (BTN, SB, BB, etc.)

    # 手牌和公共牌
    hand: Hand
    board: Board

    # 筹码信息
    pot: float
    effective_stack: float  # 最小的有效筹码
    hero_stack: float  # 当前玩家的筹码

    # 下注信息
    facing_bet: float  # 面对的下注金额（当前街道最大投入）
    to_call: float  # 需要call的金额
    min_raise: float  # 最小加注金额

    # 对手信息
    num_active_players: int  # 还在游戏中的玩家数量
    num_allin_players: int  # 已all-in的玩家数量

    # 是否在位置优势
    is_in_position: bool


class SimplePlayer(Player):
    """
    简单玩家实现（用于测试）
    总是fold
    """

    def decide(self, game_state: GameState) -> PlayerAction:
        if game_state.to_call <= ZERO_THRESHOLD:
            return PlayerAction('check', 0.0)
        else:
            return PlayerAction('fold', 0.0)
