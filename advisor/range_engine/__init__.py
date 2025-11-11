"""
Range引擎模块 (Range Engine Module)

Phase 2.1 - 范围思维核心

核心功能:
1. 扑克牌基础类 (cards.py) - Card, Hand, Board
2. 手牌评估器 (evaluator.py) - 判断牌型强度
3. Range类 (range.py) - 范围解析和集合操作
4. Equity计算器 (calculator.py) - 蒙特卡洛模拟
5. 翻前范围表 (preflop_ranges.py) - 5人桌GTO范围
6. 公共牌分析 (board_texture.py) - 牌面结构分析

设计目标:
- 支持 Hand vs Hand / Range vs Range equity计算
- 支持 Multiway equity (3+人底池)
- 完整的翻前范围数据库
- 准确的公共牌结构分析
- 纯Python实现，零依赖
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

from .board_texture import BoardTexture

from .preflop_ranges import (
    get_open_range,
    get_bb_call_range,
    get_3bet_range,
    get_4bet_range,
    parse_range_dict,
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

    # Board Texture
    'BoardTexture',

    # Preflop Ranges
    'get_open_range',
    'get_bb_call_range',
    'get_3bet_range',
    'get_4bet_range',
    'parse_range_dict',
]

__version__ = '0.1.0'
