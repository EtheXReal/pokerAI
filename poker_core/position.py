"""位置与街道枚举。

扑克领域的基础枚举，poker_env 和 advisor 共用。
（原位于 advisor/strategy_engine/gto_baseline.py）
"""
from enum import Enum


class Street(Enum):
    """街道枚举"""
    PREFLOP = 'preflop'
    FLOP = 'flop'
    TURN = 'turn'
    RIVER = 'river'


class Position(Enum):
    """位置枚举"""
    UTG = 'UTG'
    MP = 'MP'
    CO = 'CO'
    BTN = 'BTN'
    SB = 'SB'
    BB = 'BB'
