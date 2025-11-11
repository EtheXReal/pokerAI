"""
Equity计算器模块 (Equity Calculator Module)

Phase 2.3 Week 1 - 决策引擎基础

核心功能:
1. 扑克牌基础类 (cards.py) - Card, Hand, Board
2. 手牌评估器 (evaluator.py) - 判断牌型强度
3. Equity计算器 (calculator.py) - 蒙特卡洛模拟

设计目标:
- 支持 Hand vs Hand equity计算
- 支持 Hand vs Range equity计算
- 准确的手牌评估 (9种牌型)
- 高效的蒙特卡洛模拟
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

from .calculator import (
    EquityResult,
    EquityCalculator,
    quick_equity,
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

__all__ = [
    # Cards
    'Rank',
    'Suit',
    'Card',
    'Hand',
    'Board',
    'create_deck',
    'validate_no_duplicates',
    'cards_to_str',

    # Evaluator
    'HandRank',
    'HandStrength',
    'HandEvaluator',
    'evaluate_hand',

    # Calculator
    'EquityResult',
    'EquityCalculator',
    'quick_equity',

    # Range
    'HandCombo',
    'Range',
    'RangeGenerator',
    'RangeParser',
    'create_premium_range',
    'create_broadw_range',
    'create_any_pair_range',
]

__version__ = '0.1.0'
