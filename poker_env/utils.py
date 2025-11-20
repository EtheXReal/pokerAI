"""
Poker Environment Utilities
"""
from enum import Enum
from typing import List


# ============================================================================
# 精度控制常量
# ============================================================================
"""
德州扑克金额规则：
- 小盲注：0.5BB（强制盲注）
- 大盲注：1BB（强制盲注）
- Call：可以是任意金额（被动跟注）
- 主动下注/加注最小单位：1BB
- 所有金额保留2位小数
"""

# 浮点数比较容差（用于处理浮点精度误差）
FLOAT_TOLERANCE = 0.01

# 盲注金额
SMALL_BLIND = 0.5  # 小盲（0.5BB）
BIG_BLIND = 1.0    # 大盲（1BB）

# 主动下注最小单位（仅用于 bet/raise 验证）
MIN_BET_UNIT = BIG_BLIND  # 1BB

# All-in阈值（剩余筹码小于此值视为all-in）
ALLIN_THRESHOLD = SMALL_BLIND  # 0.5BB

# 小数精度（保留2位小数）
PRECISION = 2  # 小数点位数

# 判断金额是否"接近0"（用于各种 amount > 0 的判断）
ZERO_THRESHOLD = FLOAT_TOLERANCE  # 0.01BB


def round_amount(amount: float) -> float:
    """
    统一的金额精度控制

    Args:
        amount: 原始金额

    Returns:
        四舍五入到0.01BB精度的金额

    Note:
        虽然主动下注最小单位是1BB，但保留2位小数以支持：
        - 小盲注：0.5BB
        - 筹码计算中间值
    """
    return round(amount, PRECISION)


def round_bet_amount(amount: float) -> float:
    """
    将bet/raise金额规范化到整数BB

    主动bet/raise不允许有小数部分（包括0.5），只允许整数BB

    Args:
        amount: 原始金额

    Returns:
        四舍五入到最近的整数BB

    Examples:
        1.32BB -> 1.0BB
        1.87BB -> 2.0BB
        9.35BB -> 9.0BB
        23.50BB -> 24.0BB
        2.24BB -> 2.0BB
    """
    # 四舍五入到整数BB
    return round(amount)


def is_close(a: float, b: float, tolerance: float = FLOAT_TOLERANCE) -> bool:
    """
    浮点数比较（考虑精度误差）

    Args:
        a: 第一个数
        b: 第二个数
        tolerance: 误差阈值

    Returns:
        是否在误差范围内相等
    """
    return abs(a - b) < tolerance


# 向后兼容（标记为deprecated）
EPSILON = FLOAT_TOLERANCE  # DEPRECATED: 使用 FLOAT_TOLERANCE 或 ZERO_THRESHOLD


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

    使用统一的 next_player 抽象：
    - dealer_pos = btn_seat
    - sb_pos = next_player(dealer_pos)
    - bb_pos = next_player(sb_pos)
    - preflop_first = next_player(bb_pos)  # 大盲左边第一个
    - postflop_first = next_player(dealer_pos)  # 庄家左边第一个（SB）

    Args:
        num_players: 玩家数量
        btn_seat: 庄家座位索引 (0 到 num_players-1)
        street: 当前街道

    Returns:
        座位索引列表，表示行动顺序

    核心规则：
    - 翻前：从大盲左边第一个开始
    - 翻后：从庄家左边第一个开始

    特殊情况：
    - 2人游戏：BTN = SB，翻前和翻后都是 SB → BB
    - 3人游戏：翻前从SB开始（标准3人德州扑克规则）
    - 4人及以上：翻前从UTG（BB+1）开始
    """
    if num_players < 2:
        raise ValueError("At least 2 players required")

    dealer_pos = btn_seat

    if num_players == 2:
        # 2人游戏特殊情况：BTN = SB
        sb_pos = dealer_pos
        bb_pos = (dealer_pos + 1) % num_players

        # 翻前和翻后都是 SB → BB
        return [sb_pos, bb_pos]

    # 3人及以上游戏
    sb_pos = (dealer_pos + 1) % num_players
    bb_pos = (dealer_pos + 2) % num_players

    if street == Street.PREFLOP:
        # 翻前：从大盲左边第一个开始
        # preflop_first = next_player(bb_pos)
        first_to_act = (bb_pos + 1) % num_players
    else:
        # 翻后：从庄家左边第一个开始
        # postflop_first = next_player(dealer_pos) = sb_pos
        first_to_act = (dealer_pos + 1) % num_players

    # 生成完整的行动顺序
    order = []
    for i in range(num_players):
        seat = (first_to_act + i) % num_players
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
