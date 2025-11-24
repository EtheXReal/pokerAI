"""
范围感知Exploit系统 - 核心模块

取代基于频率的exploit调整，实现真正的范围感知策略。

核心概念：
- EquityBucket: 根据牌力将手牌分桶
- RangeAwareAdvice: 每个bucket不同的行动频率
- EquityBucketClassifier: 将当前手牌分类到bucket
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .models import PlayerType, StreetType
from poker_core.cards import Card


# ============================================================================
# Equity Buckets - 牌力分桶
# ============================================================================

class EquityBucket(Enum):
    """
    牌力分桶 - 根据equity和showdown value分类

    分桶原则：
    - Nutted: 80%+ equity (nuts, sets, overpairs on dry board)
    - Strong: 65-80% equity (TPTK, strong overpair)
    - Medium-Strong: 50-65% equity (top pair weak kicker, overpair on wet board)
    - Medium: 35-50% equity (middle pair, weak top pair)
    - Weak: 20-35% equity (bottom pair, weak draws)
    - Air: 0-20% equity (complete air, busted draws)
    """
    NUTTED = "nutted"
    STRONG = "strong"
    MEDIUM_STRONG = "medium_strong"
    MEDIUM = "medium"
    WEAK = "weak"
    AIR = "air"


# ============================================================================
# Action Frequencies - 行动频率分布
# ============================================================================

@dataclass
class ActionFrequencies:
    """
    行动频率分布

    确保所有频率之和为1.0
    """
    fold: float = 0.0
    call: float = 0.0
    raise_: float = 0.0  # 避免Python关键字冲突
    bet: float = 0.0
    check: float = 0.0

    def __post_init__(self):
        """验证频率之和为1.0"""
        total = self.fold + self.call + self.raise_ + self.bet + self.check
        if not (0.99 <= total <= 1.01):
            raise ValueError(
                f"ActionFrequencies must sum to 1.0, got {total:.3f}. "
                f"fold={self.fold}, call={self.call}, raise={self.raise_}, "
                f"bet={self.bet}, check={self.check}"
            )

    def to_dict(self) -> Dict[str, float]:
        """转换为字典格式（与现有系统兼容）"""
        result = {}
        if self.fold > 0:
            result['fold'] = self.fold
        if self.call > 0:
            result['call'] = self.call
        if self.raise_ > 0:
            result['raise'] = self.raise_
        if self.bet > 0:
            result['bet'] = self.bet
        if self.check > 0:
            result['check'] = self.check
        return result

    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> 'ActionFrequencies':
        """从字典创建"""
        return cls(
            fold=d.get('fold', 0.0),
            call=d.get('call', 0.0),
            raise_=d.get('raise', 0.0),
            bet=d.get('bet', 0.0),
            check=d.get('check', 0.0),
        )

    def __repr__(self) -> str:
        """可读的字符串表示"""
        parts = []
        if self.fold > 0:
            parts.append(f"fold={self.fold:.2f}")
        if self.call > 0:
            parts.append(f"call={self.call:.2f}")
        if self.raise_ > 0:
            parts.append(f"raise={self.raise_:.2f}")
        if self.bet > 0:
            parts.append(f"bet={self.bet:.2f}")
        if self.check > 0:
            parts.append(f"check={self.check:.2f}")
        return f"ActionFreqs({', '.join(parts)})"


# ============================================================================
# Range-Aware Advice - 范围感知建议
# ============================================================================

@dataclass
class RangeAwareAdvice:
    """
    范围感知的策略建议

    不再是"call 60%"，而是"用nutted hands call 90%, strong hands call 60%, medium hands fold"

    Example:
        advice = RangeAwareAdvice(
            action_type=ExploitActionType.RANGE_AWARE_DEFENSE,
            bucket_strategies={
                EquityBucket.NUTTED: ActionFrequencies(fold=0.0, call=0.7, raise_=0.3),
                EquityBucket.STRONG: ActionFrequencies(fold=0.1, call=0.6, raise_=0.3),
                EquityBucket.MEDIUM: ActionFrequencies(fold=0.85, call=0.15, raise_=0.0),
                EquityBucket.WEAK: ActionFrequencies(fold=0.95, call=0.05, raise_=0.0),
                EquityBucket.AIR: ActionFrequencies(fold=1.0, call=0.0, raise_=0.0),
            },
            reason="Against MANIAC: trap with nuts, fold most marginal hands",
        )
    """
    action_type: str  # e.g., "RANGE_AWARE_DEFENSE"
    bucket_strategies: Dict[EquityBucket, ActionFrequencies]
    reason: str
    warnings: List[str] = field(default_factory=list)
    sizing_range: Optional[Tuple[float, float]] = None

    def get_target_freqs(self, bucket: EquityBucket) -> Optional[ActionFrequencies]:
        """获取特定bucket的目标频率"""
        return self.bucket_strategies.get(bucket)

    def __repr__(self) -> str:
        return (
            f"RangeAwareAdvice(action_type={self.action_type}, "
            f"buckets={len(self.bucket_strategies)}, reason='{self.reason[:50]}...')"
        )


# ============================================================================
# Equity Bucket Classifier - 牌力分类器
# ============================================================================

class EquityBucketClassifier:
    """
    将当前手牌分类到equity bucket

    输入：手牌、公共牌、对手范围估计
    输出：EquityBucket
    """

    def classify(
        self,
        hole_cards: List[Card],
        board: List[Card],
        opponent_range: Optional[any] = None,
        street: Optional[StreetType] = None,
    ) -> EquityBucket:
        """
        分类当前手牌到bucket

        Args:
            hole_cards: Hero的两张手牌
            board: 公共牌
            opponent_range: 对手范围估计（可选）
            street: 当前street（preflop/flop/turn/river）

        Returns:
            EquityBucket

        逻辑：
        1. 如果preflop：基于手牌强度（AA > KK > ...）
        2. 如果postflop：计算equity vs opponent range
        3. 考虑board texture（dry vs wet）影响分桶边界
        """
        if not board:  # Preflop
            return self._classify_preflop(hole_cards)

        # Postflop: 计算equity
        equity = self._calculate_equity(hole_cards, board, opponent_range)

        # 根据equity分桶
        return self._equity_to_bucket(equity)

    def _classify_preflop(self, hole_cards: List[Card]) -> EquityBucket:
        """
        Preflop分类

        基于Sklansky-Chubukov排名和hand strength percentile
        """
        hand_strength = self._preflop_hand_strength(hole_cards)

        # Top 2% (AA, KK)
        if hand_strength >= 0.98:
            return EquityBucket.NUTTED
        # Top 5% (QQ, AKs)
        elif hand_strength >= 0.95:
            return EquityBucket.STRONG
        # Top 15% (JJ, TT, AKo, AQs, KQs)
        elif hand_strength >= 0.85:
            return EquityBucket.MEDIUM_STRONG
        # Top 30% (99-77, AQ, AJ, suited broadways)
        elif hand_strength >= 0.70:
            return EquityBucket.MEDIUM
        # Top 50% (small pairs, Ax, suited connectors)
        elif hand_strength >= 0.50:
            return EquityBucket.WEAK
        else:
            return EquityBucket.AIR

    def _preflop_hand_strength(self, hole_cards: List[Card]) -> float:
        """
        计算preflop手牌强度 percentile (0.0-1.0)

        返回：该手牌在所有1326种起手牌中的百分位
        例如：AA = 1.0 (top 0.45%), 72o = 0.0 (bottom)
        """
        if len(hole_cards) != 2:
            return 0.0

        card1, card2 = hole_cards
        rank1 = self._rank_value(card1.rank)
        rank2 = self._rank_value(card2.rank)

        # Ensure rank1 >= rank2
        if rank1 < rank2:
            rank1, rank2 = rank2, rank1

        is_pair = (rank1 == rank2)
        is_suited = (card1.suit == card2.suit)

        # Simplified Sklansky-Chubukov ranking
        # AA/KK: 1.0
        if is_pair and rank1 >= 13:  # AA, KK
            return 1.0
        # QQ: 0.98
        elif is_pair and rank1 == 12:
            return 0.98
        # JJ, AKs: 0.96
        elif (is_pair and rank1 == 11) or (rank1 == 14 and rank2 == 13 and is_suited):
            return 0.96
        # TT, AKo, AQs: 0.93
        elif (is_pair and rank1 == 10) or (rank1 == 14 and rank2 == 13) or \
             (rank1 == 14 and rank2 == 12 and is_suited):
            return 0.93
        # 99, AQo, AJs, KQs: 0.88
        elif (is_pair and rank1 == 9) or (rank1 == 14 and rank2 == 12) or \
             (rank1 == 14 and rank2 == 11 and is_suited) or \
             (rank1 == 13 and rank2 == 12 and is_suited):
            return 0.88
        # 88, AJo, ATs, KQo, KJs, QJs: 0.80
        elif (is_pair and rank1 == 8) or (rank1 == 14 and rank2 == 11) or \
             (rank1 == 14 and rank2 == 10 and is_suited) or \
             (rank1 == 13 and rank2 == 12) or \
             (rank1 == 13 and rank2 == 11 and is_suited) or \
             (rank1 == 12 and rank2 == 11 and is_suited):
            return 0.80
        # 77-22: pairs
        elif is_pair:
            return 0.50 + (rank1 - 2) * 0.03  # 0.50-0.68
        # Suited connectors/broadways
        elif is_suited and abs(rank1 - rank2) <= 2:
            return 0.60 + (rank1 + rank2 - 4) * 0.01  # ~0.60-0.75
        # Offsuit broadways
        elif rank1 >= 10 and rank2 >= 10:
            return 0.55 + (rank1 + rank2 - 20) * 0.02  # ~0.55-0.70
        # Ax suited
        elif rank1 == 14 and is_suited:
            return 0.50 + rank2 * 0.01  # ~0.52-0.63
        # Ax offsuit
        elif rank1 == 14:
            return 0.40 + rank2 * 0.01  # ~0.42-0.53
        # Suited cards
        elif is_suited:
            gap = rank1 - rank2
            if gap <= 3:
                return 0.45 + (rank1 + rank2) * 0.005  # ~0.45-0.58
            else:
                return 0.30 + (rank1 + rank2) * 0.003  # ~0.30-0.42
        # Offsuit trash
        else:
            return max(0.05, 0.20 + (rank1 + rank2 - 4) * 0.01)  # ~0.05-0.35

    def _rank_value(self, rank: str) -> int:
        """Convert rank to numerical value (2-14)"""
        rank_map = {
            '2': 2, '3': 3, '4': 4, '5': 5, '6': 6,
            '7': 7, '8': 8, '9': 9, 'T': 10, 'J': 11,
            'Q': 12, 'K': 13, 'A': 14
        }
        return rank_map.get(rank, 0)

    def _calculate_equity(
        self,
        hole_cards: List[Card],
        board: List[Card],
        opponent_range: Optional[any],
    ) -> float:
        """
        计算equity vs opponent range

        使用Monte Carlo simulation或equity lookup

        Note: 这里需要集成EquityEngine或使用simplified heuristic
        """
        # TODO: 集成真正的equity calculation
        # 暂时使用simplified heuristic

        # 简化版：基于hand rank和board texture
        hand_rank = self._evaluate_hand_rank(hole_cards, board)

        # 归一化到0-1
        # Nuts (straight flush, quads) = 1.0
        # High pair = 0.6-0.8
        # Middle pair = 0.4-0.6
        # Low pair/draw = 0.2-0.4
        # Air = 0.0-0.2

        if hand_rank >= 8:  # Straight flush, quads
            return 0.95
        elif hand_rank == 7:  # Full house
            return 0.90
        elif hand_rank == 6:  # Flush
            return 0.85
        elif hand_rank == 5:  # Straight
            return 0.80
        elif hand_rank == 4:  # Trips
            return 0.75
        elif hand_rank == 3:  # Two pair
            return 0.65
        elif hand_rank == 2:  # Pair
            # Distinguish between top/middle/bottom pair
            pair_strength = self._pair_strength(hole_cards, board)
            return 0.40 + pair_strength * 0.30  # 0.40-0.70
        else:  # High card
            return 0.20

    def _evaluate_hand_rank(self, hole_cards: List[Card], board: List[Card]) -> int:
        """
        评估手牌等级

        Returns: 0-9 (0=high card, 9=straight flush)

        Note: 这是simplified版本，实际应该使用完整的hand evaluator
        """
        # TODO: 使用完整的hand evaluator
        # 暂时返回简化评估
        all_cards = hole_cards + board
        ranks = [self._rank_value(c.rank) for c in all_cards]
        suits = [c.suit for c in all_cards]

        # Count rank frequencies
        from collections import Counter
        rank_counts = Counter(ranks)
        most_common = rank_counts.most_common(2)

        # Check for pairs, trips, quads
        if most_common[0][1] == 4:
            return 7  # Quads
        elif most_common[0][1] == 3:
            if len(most_common) > 1 and most_common[1][1] == 2:
                return 6  # Full house
            return 3  # Trips
        elif most_common[0][1] == 2:
            if len(most_common) > 1 and most_common[1][1] == 2:
                return 2  # Two pair
            return 1  # Pair

        # Check for flush (simplified)
        suit_counts = Counter(suits)
        if suit_counts.most_common(1)[0][1] >= 5:
            return 5  # Flush

        # Check for straight (simplified)
        unique_ranks = sorted(set(ranks))
        if len(unique_ranks) >= 5:
            for i in range(len(unique_ranks) - 4):
                if unique_ranks[i+4] - unique_ranks[i] == 4:
                    return 4  # Straight

        return 0  # High card

    def _pair_strength(self, hole_cards: List[Card], board: List[Card]) -> float:
        """
        评估pair的强度 (0.0-1.0)

        1.0 = top pair top kicker
        0.5 = middle pair
        0.0 = bottom pair
        """
        hole_ranks = [self._rank_value(c.rank) for c in hole_cards]
        board_ranks = [self._rank_value(c.rank) for c in board]

        # Find paired rank
        all_ranks = hole_ranks + board_ranks
        from collections import Counter
        rank_counts = Counter(all_ranks)

        paired_ranks = [r for r, count in rank_counts.items() if count == 2]
        if not paired_ranks:
            return 0.0

        paired_rank = max(paired_ranks)

        # Is it top pair?
        if paired_rank == max(board_ranks):
            # Top pair - check kicker
            kicker = max([r for r in hole_ranks if r != paired_rank])
            kicker_strength = (kicker - 2) / 12  # 0.0-1.0
            return 0.7 + kicker_strength * 0.3  # 0.7-1.0

        # Middle or bottom pair
        board_ranks_sorted = sorted(board_ranks, reverse=True)
        if paired_rank == board_ranks_sorted[1] if len(board_ranks_sorted) > 1 else False:
            return 0.4  # Middle pair
        else:
            return 0.1  # Bottom pair or underpair

    def _equity_to_bucket(self, equity: float) -> EquityBucket:
        """将equity值映射到bucket"""
        if equity >= 0.80:
            return EquityBucket.NUTTED
        elif equity >= 0.65:
            return EquityBucket.STRONG
        elif equity >= 0.50:
            return EquityBucket.MEDIUM_STRONG
        elif equity >= 0.35:
            return EquityBucket.MEDIUM
        elif equity >= 0.20:
            return EquityBucket.WEAK
        else:
            return EquityBucket.AIR


# ============================================================================
# Decision Context - 决策上下文
# ============================================================================

@dataclass
class DecisionContext:
    """
    决策上下文 - 传递给handler的完整信息

    包含：equity bucket, board texture, position等范围感知所需的信息
    """
    # 基础信息
    game_state: any  # GameState
    hole_cards: List[Card]
    board: List[Card]
    street: Optional[StreetType]

    # 范围感知信息
    equity_bucket: EquityBucket
    equity: float

    # 可选信息
    opponent_range_estimate: Optional[any] = None
    opponent_type: Optional[PlayerType] = None
    opponent_stats: Optional[any] = None

    def __repr__(self) -> str:
        return (
            f"DecisionContext(street={self.street}, "
            f"bucket={self.equity_bucket.value}, equity={self.equity:.2f})"
        )
