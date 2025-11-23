"""
数据模型定义

包含枚举类型、辅助数据结构等
"""
from enum import Enum
from typing import List, Dict, Optional
from dataclasses import dataclass, field


class PlayerType(Enum):
    """
    9种玩家类型分类

    基于VPIP和激进度的二维分类 + 特殊类型
    """
    # 主要类型 (基于 VPIP × Aggression 矩阵)
    NIT = "nit"                    # 紧弱型 (VPIP<18%, AF<2)
    TAG = "tag"                    # 紧激进型 (VPIP 18-25%, AF>2)
    WEAK_TIGHT = "weak_tight"      # 弱紧型 (VPIP<20%, AF 1-2)

    CALLING_STATION = "calling_station"  # 松被动型 (VPIP>35%, AF<1.5)
    LAP = "lap"                    # 松被动型 (VPIP 28-38%, AF<1.8)
    FISH = "fish"                  # 鱼型 (VPIP>40%, 各种错误)

    LAG = "lag"                    # 松激进型 (VPIP 25-35%, AF>2.5)
    MANIAC = "maniac"              # 疯狂型 (VPIP>38%, AF>3.5)

    SOLID_REG = "solid_reg"        # 扎实常客 (平衡型, VPIP 22-28%, AF 2-3)

    UNKNOWN = "unknown"            # 未知 (手数不足)

    def __str__(self):
        return self.value

    @property
    def display_name(self) -> str:
        """中文显示名称"""
        names = {
            PlayerType.NIT: "岩石型(Nit)",
            PlayerType.TAG: "紧激进(TAG)",
            PlayerType.WEAK_TIGHT: "弱紧型",
            PlayerType.CALLING_STATION: "跟注站",
            PlayerType.LAP: "松被动",
            PlayerType.FISH: "鱼(Fish)",
            PlayerType.LAG: "松激进(LAG)",
            PlayerType.MANIAC: "疯子(Maniac)",
            PlayerType.SOLID_REG: "扎实常客",
            PlayerType.UNKNOWN: "未知",
        }
        return names.get(self, self.value)


class ActionType(Enum):
    """行动类型"""
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALL_IN = "all_in"

    def is_aggressive(self) -> bool:
        """是否为激进动作"""
        return self in [ActionType.BET, ActionType.RAISE, ActionType.ALL_IN]

    def is_passive(self) -> bool:
        """是否为被动动作"""
        return self in [ActionType.CHECK, ActionType.CALL]


class StreetType(Enum):
    """街道类型"""
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"

    def __str__(self):
        return self.value

    @property
    def index(self) -> int:
        """街道索引 (0-3)"""
        return list(StreetType).index(self)


class PositionType(Enum):
    """位置类型"""
    SB = "SB"
    BB = "BB"
    UTG = "UTG"
    MP = "MP"
    CO = "CO"
    BTN = "BTN"
    UNKNOWN = "UNKNOWN"

    def __str__(self):
        return self.value

    @property
    def is_early(self) -> bool:
        """是否为早期位置"""
        return self in [PositionType.UTG, PositionType.MP]

    @property
    def is_late(self) -> bool:
        """是否为晚期位置"""
        return self in [PositionType.CO, PositionType.BTN]

    @property
    def is_blind(self) -> bool:
        """是否为盲注位置"""
        return self in [PositionType.SB, PositionType.BB]


@dataclass
class ActionRecord:
    """
    单次行动记录

    用于追踪玩家的每个动作，便于统计分析
    """
    street: StreetType
    position: PositionType
    action: ActionType
    amount: float = 0.0
    pot_size: float = 0.0
    facing_bet: float = 0.0

    # 上下文信息
    is_in_position: bool = False
    is_first_action: bool = False
    num_players: int = 2

    # 标记
    is_open_raise: bool = False
    is_3bet: bool = False
    is_4bet: bool = False
    is_cbet: bool = False
    is_check_raise: bool = False
    is_donk_bet: bool = False


@dataclass
class HandResult:
    """
    单手牌结果

    记录玩家在一手牌中的表现
    """
    hand_id: str
    position: PositionType
    vpip: bool  # 是否主动入池
    pfr: bool   # 是否翻前加注

    # 翻前行动
    saw_flop: bool = False
    faced_raise: bool = False  # 是否面对了raise（用于计算3-bet机会）
    three_bet: bool = False
    four_bet: bool = False
    fold_to_3bet: bool = False
    call_3bet: bool = False

    # 翻后行动
    cbet_flop: Optional[bool] = None
    cbet_turn: Optional[bool] = None
    cbet_river: Optional[bool] = None
    fold_to_cbet: Optional[bool] = None

    # 结果
    went_to_showdown: bool = False
    won_at_showdown: bool = False
    won_hand: bool = False
    amount_won: float = 0.0

    # 行动序列
    actions: List[ActionRecord] = field(default_factory=list)


# 辅助函数

def classify_action(action_str: str) -> ActionType:
    """
    将字符串动作转换为ActionType

    Args:
        action_str: 'fold', 'call', 'call 2.5BB', 'bet 3.0BB', 'raise to 5.0BB', 'allin', etc.

    Returns:
        ActionType枚举
    """
    action_lower = action_str.lower()

    if action_lower == 'fold' or action_lower.startswith('fold'):
        return ActionType.FOLD
    elif action_lower == 'check' or action_lower.startswith('check'):
        return ActionType.CHECK
    elif action_lower == 'call' or action_lower.startswith('call'):
        return ActionType.CALL
    elif action_lower.startswith('bet'):
        return ActionType.BET
    elif action_lower.startswith('raise') or action_lower.startswith('r'):
        return ActionType.RAISE
    elif 'all-in' in action_lower or 'allin' in action_lower:
        return ActionType.ALL_IN
    else:
        return ActionType.CHECK  # 默认


def parse_street(street_str: str) -> StreetType:
    """解析街道字符串"""
    street_map = {
        'preflop': StreetType.PREFLOP,
        'flop': StreetType.FLOP,
        'turn': StreetType.TURN,
        'river': StreetType.RIVER,
    }
    return street_map.get(street_str.lower(), StreetType.PREFLOP)


def parse_position(pos_str: str) -> PositionType:
    """解析位置字符串"""
    pos_upper = pos_str.upper()
    try:
        return PositionType[pos_upper]
    except KeyError:
        return PositionType.UNKNOWN
