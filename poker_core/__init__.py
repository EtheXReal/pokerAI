"""
poker_core - 扑克基础原语包

项目中所有模块共用的基础类型，纯Python实现，零第三方依赖：
- cards.py:     Card, Hand, Board, Rank, Suit, create_deck
- evaluator.py: HandEvaluator (7张牌牌型评估)
- range.py:     Range, HandCombo (范围表示与集合操作)
- position.py:  Position, Street 枚举

依赖方向: poker_core ← poker_env / advisor
"""

from .cards import (
    Rank,
    Suit,
    Card,
    Hand,
    Board,
    create_deck,
    validate_no_duplicates,
    cards_to_str,
)

from .evaluator import (
    HandRank,
    HandStrength,
    HandEvaluator,
    evaluate_hand,
)

from .range import (
    HandCombo,
    Range,
    RangeGenerator,
    RangeParser,
    create_premium_range,
    create_broadw_range,
    create_any_pair_range,
)

from .position import Position, Street

__all__ = [
    # Cards
    'Rank', 'Suit', 'Card', 'Hand', 'Board',
    'create_deck', 'validate_no_duplicates', 'cards_to_str',
    # Evaluator
    'HandRank', 'HandStrength', 'HandEvaluator', 'evaluate_hand',
    # Range
    'HandCombo', 'Range', 'RangeGenerator', 'RangeParser',
    'create_premium_range', 'create_broadw_range', 'create_any_pair_range',
    # Position
    'Position', 'Street',
]

__version__ = '0.2.0'
