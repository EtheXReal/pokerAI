"""
Range Engine - 范围引擎

核心模块:
- preflop_ranges: 5人桌翻前范围表
- range: Range类和范围操作
- equity: 范围equity计算
- board_texture: 公共牌结构分析
"""
from .range import Range, parse_range_dict, merge_range_dicts
from .equity import EquityCalculator
from .board_texture import BoardTexture
from .preflop_ranges import (
    get_open_range,
    get_bb_call_range,
    get_3bet_range,
    get_4bet_range,
)

__all__ = [
    'Range',
    'parse_range_dict',
    'merge_range_dicts',
    'EquityCalculator',
    'BoardTexture',
    'get_open_range',
    'get_bb_call_range',
    'get_3bet_range',
    'get_4bet_range',
]
