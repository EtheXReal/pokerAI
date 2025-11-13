"""
Poker Environment Utilities
"""
from enum import Enum
from typing import List


# ============================================================================
# 精度控制常量
# ============================================================================
# 德州扑克标准精度：0.01BB（小数点后2位）
# 这与线上扑克的筹码最小单位一致
PRECISION = 2  # 小数点位数
EPSILON = 0.01  # 最小单位（0.01BB）
ALLIN_THRESHOLD = 0.01  # All-in阈值


def round_amount(amount: float) -> float:
    """
    统一的金额精度控制

    Args:
        amount: 原始金额

    Returns:
        四舍五入到0.01BB精度的金额
    """
    return round(amount, PRECISION)


def is_close(a: float, b: float, epsilon: float = EPSILON) -> bool:
    """
    浮点数比较（考虑精度误差）

    Args:
        a: 第一个数
        b: 第二个数
        epsilon: 误差阈值

    Returns:
        是否在误差范围内相等
    """
    return abs(a - b) < epsilon


class Street(Enum):
    """街道枚举"""
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"


class Position(Enum):
    """位置枚举（用于6人及以上）"""
    BTN = "BTN"  # 庄家
    SB = "SB"    # 小盲
    BB = "BB"    # 大盲
    UTG = "UTG"  # Under the Gun (大盲左边第一个)
    MP = "MP"    # Middle Position
    CO = "CO"    # Cut Off (庄家右边第一个)

    # 2人游戏特殊情况
    # BTN = SB (庄家同时是小盲)
    # BB = BB (大盲)


def get_action_order(num_players: int, btn_seat: int, street: Street) -> List[int]:
    """
    获取行动顺序（座位索引列表）

    座位编号从0开始，按顺时针方向递增。
    BTN是庄家位置，后手位置。

    Args:
        num_players: 玩家数量
        btn_seat: 庄家座位索引 (0 到 num_players-1)
        street: 当前街道

    Returns:
        座位索引列表，表示行动顺序

    德州扑克规则：
    - Preflop: 从大盲左边第一个开始（UTG），到大盲结束
    - Flop/Turn/River: 从庄家左边第一个开始（SB），到庄家结束

    2人游戏特殊情况：
    - BTN = SB (庄家同时是小盲)
    - Preflop: SB先行动（需要补齐大盲）
    - Flop/Turn/River: SB先行动
    """
    if num_players < 2:
        raise ValueError("At least 2 players required")

    # 计算盲注位置
    sb_seat = btn_seat  # 2人游戏中，BTN=SB
    bb_seat = (btn_seat + 1) % num_players

    if num_players == 2:
        # 2人游戏：BTN=SB
        if street == Street.PREFLOP:
            # Preflop: SB先行动
            return [sb_seat, bb_seat]
        else:
            # Flop/Turn/River: SB先行动
            return [sb_seat, bb_seat]
    else:
        # 多人游戏
        if street == Street.PREFLOP:
            # Preflop: 从UTG（大盲左边第一个）开始
            utg_seat = (bb_seat + 1) % num_players
            order = []
            for i in range(num_players):
                seat = (utg_seat + i) % num_players
                order.append(seat)
            return order
        else:
            # Flop/Turn/River: 从SB开始
            order = []
            for i in range(num_players):
                seat = (sb_seat + i) % num_players
                order.append(seat)
            return order


def get_position_name(seat_idx: int, btn_seat: int, num_players: int) -> str:
    """
    获取座位的位置名称

    Args:
        seat_idx: 座位索引
        btn_seat: 庄家座位索引
        num_players: 玩家数量

    Returns:
        位置名称字符串
    """
    if num_players == 2:
        if seat_idx == btn_seat:
            return "BTN/SB"
        else:
            return "BB"
    elif num_players <= 6:
        # 6人及以下
        offset = (seat_idx - btn_seat) % num_players
        if offset == 0:
            return "BTN"
        elif offset == 1:
            return "SB"
        elif offset == 2:
            return "BB"
        elif offset == 3:
            return "UTG"
        elif offset == 4:
            return "MP"
        elif offset == 5:
            return "CO"
        else:
            return f"P{seat_idx}"
    else:
        # 7人及以上
        offset = (seat_idx - btn_seat) % num_players
        if offset == 0:
            return "BTN"
        elif offset == 1:
            return "SB"
        elif offset == 2:
            return "BB"
        elif offset == 3:
            return "UTG"
        elif offset == num_players - 1:
            return "CO"
        else:
            return f"MP{offset-3}"


def get_blind_amounts(num_players: int, sb: float = 0.5, bb: float = 1.0) -> dict:
    """
    获取盲注金额配置

    Args:
        num_players: 玩家数量
        sb: 小盲金额
        bb: 大盲金额

    Returns:
        字典，key是相对于BTN的偏移量，value是盲注金额
    """
    if num_players == 2:
        # 2人游戏：BTN=SB, BB=BB
        return {
            0: sb,  # BTN/SB
            1: bb,  # BB
        }
    else:
        # 多人游戏：BTN后第一个是SB，第二个是BB
        return {
            1: sb,  # SB
            2: bb,  # BB
        }


def format_action(player_name: str, action: str, amount: float = 0,
                  pot_after: float = 0) -> str:
    """
    格式化action字符串

    Args:
        player_name: 玩家名称
        action: 动作类型
        amount: 金额（可选）
        pot_after: 动作后的pot大小

    Returns:
        格式化的字符串
    """
    if amount > 0:
        return f"{player_name}: {action} {amount:.2f}BB (pot={pot_after:.2f}BB)"
    else:
        return f"{player_name}: {action} (pot={pot_after:.2f}BB)"
