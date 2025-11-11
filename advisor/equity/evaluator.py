#!/usr/bin/env python
"""
手牌评估器 (Hand Evaluator)

评估5张牌的牌型强度:
- High Card (高牌)
- One Pair (一对)
- Two Pair (两对)
- Three of a Kind (三条)
- Straight (顺子)
- Flush (同花)
- Full House (葫芦)
- Four of a Kind (四条)
- Straight Flush (同花顺)
- Royal Flush (皇家同花顺)
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import IntEnum
from typing import List, Tuple, Optional
from collections import Counter

from .cards import Card, Rank


class HandRank(IntEnum):
    """牌型等级 (数字越大越强)"""
    HIGH_CARD = 1
    ONE_PAIR = 2
    TWO_PAIR = 3
    THREE_OF_A_KIND = 4
    STRAIGHT = 5
    FLUSH = 6
    FULL_HOUSE = 7
    FOUR_OF_A_KIND = 8
    STRAIGHT_FLUSH = 9
    ROYAL_FLUSH = 10

    def __str__(self) -> str:
        names = {
            1: "High Card",
            2: "One Pair",
            3: "Two Pair",
            4: "Three of a Kind",
            5: "Straight",
            6: "Flush",
            7: "Full House",
            8: "Four of a Kind",
            9: "Straight Flush",
            10: "Royal Flush",
        }
        return names[self.value]


@dataclass(frozen=True)
class HandStrength:
    """
    手牌强度评估结果

    Attributes:
        rank: 牌型等级
        primary: 主要牌面值 (如对子的大小、三条的大小)
        secondary: 次要牌面值 (如两对的次大对、葫芦的对子)
        kickers: 踢脚牌 (从大到小排序)
    """
    rank: HandRank
    primary: List[int]     # 主要牌值
    secondary: List[int]   # 次要牌值
    kickers: List[int]     # 踢脚牌

    def __lt__(self, other: HandStrength) -> bool:
        """比较两个手牌强度"""
        if self.rank != other.rank:
            return self.rank < other.rank

        # 相同牌型，比较主要牌值
        if self.primary != other.primary:
            return self.primary < other.primary

        # 主要牌值相同，比较次要牌值
        if self.secondary != other.secondary:
            return self.secondary < other.secondary

        # 次要牌值相同，比较踢脚牌
        return self.kickers < other.kickers

    def __eq__(self, other) -> bool:
        if not isinstance(other, HandStrength):
            return False
        return (self.rank == other.rank and
                self.primary == other.primary and
                self.secondary == other.secondary and
                self.kickers == other.kickers)

    def __str__(self) -> str:
        return f"{self.rank}"

    def to_score(self) -> int:
        """
        转换为数值分数 (用于快速比较)

        分数构成:
        - 牌型: rank * 10^12
        - 主要牌值: primary[0] * 10^10 + primary[1] * 10^8 + ...
        - 次要牌值: secondary[0] * 10^6 + ...
        - 踢脚: kickers[0] * 10^4 + kickers[1] * 10^2 + ...
        """
        score = int(self.rank) * (10 ** 12)

        # 主要牌值
        for i, val in enumerate(self.primary):
            score += val * (10 ** (10 - i * 2))

        # 次要牌值
        for i, val in enumerate(self.secondary):
            score += val * (10 ** (6 - i * 2))

        # 踢脚牌
        for i, val in enumerate(self.kickers):
            score += val * (10 ** (4 - i * 2))

        return score


class HandEvaluator:
    """手牌评估器"""

    @staticmethod
    def evaluate(cards: List[Card]) -> HandStrength:
        """
        评估5张牌的强度

        Args:
            cards: 5张牌

        Returns:
            HandStrength对象

        Raises:
            ValueError: 如果不是5张牌
        """
        if len(cards) != 5:
            raise ValueError(f"Must evaluate exactly 5 cards, got {len(cards)}")

        # 按牌面从大到小排序
        sorted_cards = sorted(cards, key=lambda c: c.rank, reverse=True)

        # 检查同花顺 (包括皇家同花顺)
        if HandEvaluator._is_flush(sorted_cards):
            straight_high = HandEvaluator._is_straight(sorted_cards)
            if straight_high is not None:
                # 同花顺
                if straight_high == Rank.ACE:
                    # 皇家同花顺
                    return HandStrength(
                        rank=HandRank.ROYAL_FLUSH,
                        primary=[int(Rank.ACE)],
                        secondary=[],
                        kickers=[]
                    )
                else:
                    # 普通同花顺
                    return HandStrength(
                        rank=HandRank.STRAIGHT_FLUSH,
                        primary=[int(straight_high)],
                        secondary=[],
                        kickers=[]
                    )

        # 统计每个牌面出现的次数
        rank_counts = Counter(c.rank for c in sorted_cards)
        counts = sorted(rank_counts.items(), key=lambda x: (x[1], x[0]), reverse=True)

        # 四条
        if counts[0][1] == 4:
            quad_rank = counts[0][0]
            kicker = counts[1][0]
            return HandStrength(
                rank=HandRank.FOUR_OF_A_KIND,
                primary=[int(quad_rank)],
                secondary=[],
                kickers=[int(kicker)]
            )

        # 葫芦 (三条 + 一对)
        if counts[0][1] == 3 and counts[1][1] == 2:
            trips_rank = counts[0][0]
            pair_rank = counts[1][0]
            return HandStrength(
                rank=HandRank.FULL_HOUSE,
                primary=[int(trips_rank)],
                secondary=[int(pair_rank)],
                kickers=[]
            )

        # 同花
        if HandEvaluator._is_flush(sorted_cards):
            kickers = [int(c.rank) for c in sorted_cards]
            return HandStrength(
                rank=HandRank.FLUSH,
                primary=[kickers[0]],  # 最大牌作为primary
                secondary=[],
                kickers=kickers[1:]    # 其余作为kickers
            )

        # 顺子
        straight_high = HandEvaluator._is_straight(sorted_cards)
        if straight_high is not None:
            return HandStrength(
                rank=HandRank.STRAIGHT,
                primary=[int(straight_high)],
                secondary=[],
                kickers=[]
            )

        # 三条
        if counts[0][1] == 3:
            trips_rank = counts[0][0]
            kickers = sorted([int(counts[1][0]), int(counts[2][0])], reverse=True)
            return HandStrength(
                rank=HandRank.THREE_OF_A_KIND,
                primary=[int(trips_rank)],
                secondary=[],
                kickers=kickers
            )

        # 两对
        if counts[0][1] == 2 and counts[1][1] == 2:
            # 两对从大到小排序
            pair1 = max(int(counts[0][0]), int(counts[1][0]))
            pair2 = min(int(counts[0][0]), int(counts[1][0]))
            kicker = int(counts[2][0])
            return HandStrength(
                rank=HandRank.TWO_PAIR,
                primary=[pair1, pair2],
                secondary=[],
                kickers=[kicker]
            )

        # 一对
        if counts[0][1] == 2:
            pair_rank = counts[0][0]
            kickers = sorted([int(counts[i][0]) for i in range(1, 4)], reverse=True)
            return HandStrength(
                rank=HandRank.ONE_PAIR,
                primary=[int(pair_rank)],
                secondary=[],
                kickers=kickers
            )

        # 高牌
        kickers = [int(c.rank) for c in sorted_cards]
        return HandStrength(
            rank=HandRank.HIGH_CARD,
            primary=[kickers[0]],  # 最大牌作为primary
            secondary=[],
            kickers=kickers[1:]    # 其余作为kickers
        )

    @staticmethod
    def _is_flush(cards: List[Card]) -> bool:
        """检查是否同花"""
        return len(set(c.suit for c in cards)) == 1

    @staticmethod
    def _is_straight(cards: List[Card]) -> Optional[Rank]:
        """
        检查是否顺子

        Returns:
            如果是顺子，返回最大牌的Rank；否则返回None
        """
        # 按牌面从大到小排序
        ranks = sorted([c.rank for c in cards], reverse=True)

        # 检查普通顺子 (5张连续)
        if ranks[0] - ranks[4] == 4:
            return ranks[0]

        # 检查A-2-3-4-5 (轮子顺子)
        if ranks == [Rank.ACE, Rank.FIVE, Rank.FOUR, Rank.THREE, Rank.TWO]:
            return Rank.FIVE  # A-2-3-4-5的顺子，5是最大牌

        return None

    @staticmethod
    def evaluate_best_5(cards: List[Card]) -> HandStrength:
        """
        从7张牌中评估最佳5张牌

        Args:
            cards: 7张牌 (手牌2张 + 公共牌5张)

        Returns:
            最佳5张牌的强度
        """
        if len(cards) != 7:
            raise ValueError(f"Must evaluate exactly 7 cards, got {len(cards)}")

        # 枚举所有C(7,5)=21种组合
        from itertools import combinations

        best_strength = None
        for five_cards in combinations(cards, 5):
            strength = HandEvaluator.evaluate(list(five_cards))
            if best_strength is None or strength > best_strength:
                best_strength = strength

        return best_strength


def evaluate_hand(cards: List[Card]) -> HandStrength:
    """
    便捷函数: 评估手牌强度

    Args:
        cards: 5张或7张牌

    Returns:
        HandStrength对象
    """
    if len(cards) == 5:
        return HandEvaluator.evaluate(cards)
    elif len(cards) == 7:
        return HandEvaluator.evaluate_best_5(cards)
    else:
        raise ValueError(f"Must provide 5 or 7 cards, got {len(cards)}")
