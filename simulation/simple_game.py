#!/usr/bin/env python
"""
简单对局模拟 - 用于测试Strategy Engine
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List
import random

import sys
sys.path.append('/home/user/pokerAI')

from advisor.range_engine import Hand, Board, create_deck, Card
from advisor.range_engine.evaluator import HandEvaluator


@dataclass
class PlayerState:
    """玩家状态"""
    name: str
    stack: float
    hand: Optional[Hand] = None
    folded: bool = False
    invested: float = 0.0


class SimpleHeadsUpGame:
    """
    简化的单挑游戏

    仅模拟翻前决策和showdown，不涉及复杂的翻后流程
    """

    def __init__(self, starting_stack: float = 100.0, sb: float = 0.5, bb: float = 1.0):
        """
        Args:
            starting_stack: 起始筹码
            sb: 小盲注
            bb: 大盲注
        """
        self.starting_stack = starting_stack
        self.sb = sb
        self.bb = bb

    def play_hand(self,
                  player1: PlayerState,
                  player2: PlayerState,
                  p1_action: str,  # 'fold', 'call', 'raise'
                  p2_action: str,
                  raise_amount: float = 3.0) -> tuple[float, float]:
        """
        执行一手牌

        Args:
            player1: BTN位置玩家（小盲）
            player2: BB位置玩家（大盲）
            p1_action: player1的行动
            p2_action: player2的响应行动
            raise_amount: raise的数额（BB倍数）

        Returns:
            (player1_result, player2_result) - 本手盈亏
        """
        # 重置状态
        player1.folded = False
        player2.folded = False
        player1.invested = self.sb
        player2.invested = self.bb

        pot = self.sb + self.bb

        # 发牌
        deck = create_deck()
        random.shuffle(deck)

        player1.hand = Hand([deck[0], deck[1]])
        player2.hand = Hand([deck[2], deck[3]])

        # BTN行动
        if p1_action == 'fold':
            # BTN弃牌，BB赢得底池
            player1.folded = True
            return -self.sb, self.sb

        elif p1_action == 'call':
            # BTN跟注到BB
            player1.invested = self.bb
            pot = self.bb * 2
            # 直接showdown

        elif p1_action == 'raise':
            # BTN加注
            player1.invested = raise_amount
            pot = raise_amount + self.bb

            # BB响应
            if p2_action == 'fold':
                player2.folded = True
                return raise_amount - self.sb, -self.bb

            elif p2_action == 'call':
                # BB跟注
                player2.invested = raise_amount
                pot = raise_amount * 2

            elif p2_action == 'raise':
                # BB 3-bet（简化：固定3倍）
                three_bet_amount = raise_amount * 3
                player2.invested = three_bet_amount
                pot = raise_amount + three_bet_amount

                # BTN响应3-bet（简化：只能call或fold）
                if random.random() < 0.3:  # 30%弃牌
                    player1.folded = True
                    return -raise_amount, three_bet_amount - self.bb
                else:
                    # 跟注3-bet
                    player1.invested = three_bet_amount
                    pot = three_bet_amount * 2

        # Showdown
        if not player1.folded and not player2.folded:
            # 发出完整公共牌
            board_cards = deck[4:9]
            board = Board(board_cards)

            # 评估双方手牌
            p1_cards = list(player1.hand.cards) + board_cards
            p2_cards = list(player2.hand.cards) + board_cards

            p1_strength = HandEvaluator.evaluate_best_5(p1_cards)
            p2_strength = HandEvaluator.evaluate_best_5(p2_cards)

            if p1_strength > p2_strength:
                # Player1赢
                return pot - player1.invested, -player2.invested
            elif p1_strength < p2_strength:
                # Player2赢
                return -player1.invested, pot - player2.invested
            else:
                # 平局
                return 0, 0

        # 不应该到这里
        return 0, 0


class RandomPlayer:
    """随机决策的玩家"""

    def __init__(self, name: str = "Random", fold_rate: float = 0.3, raise_rate: float = 0.2):
        """
        Args:
            name: 玩家名称
            fold_rate: 弃牌概率
            raise_rate: 加注概率（剩余为跟注）
        """
        self.name = name
        self.fold_rate = fold_rate
        self.raise_rate = raise_rate

    def decide(self, position: str) -> str:
        """
        做决策

        Args:
            position: 'BTN' 或 'BB'

        Returns:
            'fold', 'call', 或 'raise'
        """
        r = random.random()

        if r < self.fold_rate:
            return 'fold'
        elif r < self.fold_rate + self.raise_rate:
            return 'raise'
        else:
            return 'call'


def simulate_session(num_hands: int = 100, verbose: bool = False) -> dict:
    """
    模拟一个session

    Args:
        num_hands: 手牌数
        verbose: 是否打印详细信息

    Returns:
        统计结果字典
    """
    game = SimpleHeadsUpGame(starting_stack=100.0)

    # 创建两个随机玩家
    player1 = RandomPlayer("Random1", fold_rate=0.3, raise_rate=0.2)
    player2 = RandomPlayer("Random2", fold_rate=0.3, raise_rate=0.2)

    p1_state = PlayerState(name="Random1", stack=100.0)
    p2_state = PlayerState(name="Random2", stack=100.0)

    p1_total = 0.0
    p2_total = 0.0

    p1_wins = 0
    p2_wins = 0
    ties = 0

    for i in range(num_hands):
        # 玩家1在BTN
        p1_action = player1.decide('BTN')
        p2_action = player2.decide('BB')

        p1_result, p2_result = game.play_hand(p1_state, p2_state, p1_action, p2_action)

        p1_total += p1_result
        p2_total += p2_result

        if p1_result > 0:
            p1_wins += 1
        elif p2_result > 0:
            p2_wins += 1
        else:
            ties += 1

        if verbose and i % 20 == 0:
            print(f"Hand {i}: P1={p1_total:.1f}BB, P2={p2_total:.1f}BB")

    return {
        'hands': num_hands,
        'p1_total': p1_total,
        'p2_total': p2_total,
        'p1_bb_per_hand': p1_total / num_hands,
        'p2_bb_per_hand': p2_total / num_hands,
        'p1_wins': p1_wins,
        'p2_wins': p2_wins,
        'ties': ties
    }


if __name__ == '__main__':
    print("测试简单对局模拟...")
    print("=" * 60)

    # 测试100手
    results = simulate_session(num_hands=100, verbose=True)

    print("\n" + "=" * 60)
    print("结果:")
    print(f"总手数: {results['hands']}")
    print(f"Player1: {results['p1_total']:.1f}BB ({results['p1_bb_per_hand']:.2f}BB/hand)")
    print(f"Player2: {results['p2_total']:.1f}BB ({results['p2_bb_per_hand']:.2f}BB/hand)")
    print(f"胜负: P1={results['p1_wins']}, P2={results['p2_wins']}, Tie={results['ties']}")
