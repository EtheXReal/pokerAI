"""
范围推断引擎 (Range Estimator)

根据对手行动历史推断和更新对手范围。

核心功能：
1. 翻前范围推断（基于位置+玩家类型）
2. 翻后范围动态更新（基于行动+下注尺寸）
3. 贝叶斯更新思想：P(范围|行动) ∝ P(行动|范围) × P(范围)
"""
from typing import List, Optional, Dict, Tuple
from enum import Enum

# 导入依赖
import sys
sys.path.append('/home/user/pokerAI')

from advisor.range_engine import Range, Board, Hand, EquityCalculator, BoardTexture
from advisor.range_engine.preflop_ranges import get_open_range, parse_range_dict
from advisor.opponent_modeling import PlayerType


class Action(Enum):
    """行动类型"""
    FOLD = 'fold'
    CHECK = 'check'
    CALL = 'call'
    BET = 'bet'
    RAISE = 'raise'
    OPEN = 'open'
    LIMP = 'limp'
    THREE_BET = '3bet'
    FOUR_BET = '4bet'


class Position(Enum):
    """位置枚举"""
    UTG = 'UTG'
    MP = 'MP'
    CO = 'CO'
    BTN = 'BTN'
    SB = 'SB'
    BB = 'BB'


class RangeEstimator:
    """范围推断引擎"""

    def __init__(self):
        """初始化"""
        self.equity_calc = EquityCalculator(iterations=5000)

    # ===== 翻前范围推断 =====

    def estimate_preflop_range(self,
                               position: Position,
                               action: Action,
                               player_type: PlayerType,
                               vs_position: Optional[Position] = None) -> Range:
        """
        翻前范围推断

        Args:
            position: 对手位置
            action: 对手行动
            player_type: 玩家类型
            vs_position: 我方位置（如果对手是响应行动）

        Returns:
            推断的范围

        Example:
            # BTN open raise
            btn_range = estimator.estimate_preflop_range(
                Position.BTN, Action.OPEN, PlayerType.TAG
            )

            # BB 3-bet vs BTN
            bb_3bet = estimator.estimate_preflop_range(
                Position.BB, Action.THREE_BET, PlayerType.LAG, vs_position=Position.BTN
            )
        """
        # 根据玩家类型调整紧度
        tightness = self._get_tightness_for_player_type(player_type)

        # 开池行动
        if action == Action.OPEN:
            range_dict = get_open_range(position.value, tightness)
            return parse_range_dict(range_dict)

        # 跛入（Limp）
        elif action == Action.LIMP:
            # Limp通常是弱范围或小对子
            return Range.from_string("22-66,A2s,A3s,A4s,A5s,K8s,K9s,Q9s,J9s,T8s")

        # 3-bet行动
        elif action == Action.THREE_BET:
            return self._estimate_3bet_range(position, player_type, vs_position)

        # 4-bet行动
        elif action == Action.FOUR_BET:
            return self._estimate_4bet_range(position, player_type)

        # 跟注open
        elif action == Action.CALL and vs_position:
            return self._estimate_call_range(position, player_type, vs_position)

        # 默认：返回较宽范围
        return Range.from_string("22+,A2s+,K2s+,Q5s+,J7s+,T7s+,97s+,A2o+,K9o+")

    def _get_tightness_for_player_type(self, player_type: PlayerType) -> str:
        """
        根据玩家类型获取紧度

        Args:
            player_type: 玩家类型

        Returns:
            'tight', 'normal', 'loose'
        """
        tight_types = [PlayerType.NIT, PlayerType.WEAK_TIGHT, PlayerType.TAG]
        loose_types = [PlayerType.MANIAC, PlayerType.FISH, PlayerType.LAG, PlayerType.CALLING_STATION, PlayerType.LAP]

        if player_type in tight_types:
            return 'tight'
        elif player_type in loose_types:
            return 'loose'
        else:
            return 'normal'

    def _estimate_3bet_range(self,
                            position: Position,
                            player_type: PlayerType,
                            vs_position: Optional[Position]) -> Range:
        """估计3-bet范围"""
        # 基础3-bet范围
        if player_type == PlayerType.LAG or player_type == PlayerType.MANIAC:
            # 激进玩家：宽3-bet
            base_range = "88+,A9s+,KTs+,QJs,A2s,A3s,A4s,A5s,ATo+,KJo+"
        elif player_type == PlayerType.TAG:
            # TAG：平衡3-bet
            base_range = "99+,AJs+,KQs,AQo+"
        elif player_type == PlayerType.NIT or player_type == PlayerType.WEAK_TIGHT:
            # 紧手：窄3-bet
            base_range = "JJ+,AKs,AKo"
        else:
            # 默认
            base_range = "99+,ATs+,KQs,AQo+"

        return Range.from_string(base_range)

    def _estimate_4bet_range(self, position: Position, player_type: PlayerType) -> Range:
        """估计4-bet范围"""
        # 4-bet通常非常极化
        if player_type == PlayerType.MANIAC:
            return Range.from_string("QQ+,AKs,AKo,A5s,A4s")
        elif player_type == PlayerType.LAG:
            return Range.from_string("QQ+,AKs,AKo")
        elif player_type == PlayerType.TAG:
            return Range.from_string("KK+,AKs")
        elif player_type == PlayerType.NIT:
            return Range.from_string("KK+")
        else:
            return Range.from_string("QQ+,AKs")

    def _estimate_call_range(self,
                            position: Position,
                            player_type: PlayerType,
                            vs_position: Position) -> Range:
        """估计跟注open的范围"""
        # 根据位置和玩家类型
        if player_type == PlayerType.CALLING_STATION:
            # Calling station跟注很宽
            return Range.from_string("22+,A2s+,K2s+,Q5s+,J7s+,T7s+,A2o+,K8o+")
        elif player_type == PlayerType.LAG:
            return Range.from_string("22+,A2s+,K5s+,Q8s+,J8s+,T8s+,A5o+,K9o+")
        elif player_type == PlayerType.TAG:
            return Range.from_string("55+,A7s+,K9s+,Q9s+,J9s+,T9s,A9o+,KJo+")
        elif player_type == PlayerType.NIT:
            return Range.from_string("77+,A9s+,KTs+,QJs,ATo+,KQo")
        else:
            return Range.from_string("44+,A5s+,K8s+,Q9s+,J9s+,T8s+,A8o+,KTo+")

    # ===== 翻后范围更新 =====

    def update_postflop_range(self,
                             current_range: Range,
                             action: Action,
                             sizing: Optional[float],
                             board: Board,
                             player_type: PlayerType,
                             pot: float) -> Range:
        """
        翻后范围动态更新

        根据对手行动缩窄范围

        Args:
            current_range: 当前推断的范围
            action: 对手行动
            sizing: 下注尺寸（BB或pot百分比）
            board: 公共牌
            player_type: 玩家类型
            pot: 底池大小

        Returns:
            更新后的范围

        Example:
            # 翻牌圈对手c-bet 66% pot
            new_range = estimator.update_postflop_range(
                villain_range,
                Action.BET,
                sizing=0.66,
                board=Board.from_str("AhKc9d"),
                player_type=PlayerType.TAG,
                pot=100
            )
        """
        # Check行动
        if action == Action.CHECK:
            return self._update_on_check(current_range, board, player_type)

        # Bet/Raise行动
        elif action in [Action.BET, Action.RAISE]:
            return self._update_on_bet(current_range, sizing, board, player_type, pot)

        # Call行动
        elif action == Action.CALL:
            return self._update_on_call(current_range, board, player_type)

        # Fold行动
        elif action == Action.FOLD:
            return Range()  # 空范围

        # 默认：不更新
        return current_range

    def _update_on_check(self,
                        current_range: Range,
                        board: Board,
                        player_type: PlayerType) -> Range:
        """
        Check行动后更新范围

        启发式：Check通常排除nuts，保留中等强度
        """
        # 分析公共牌
        texture = BoardTexture(board)

        # 计算每个combo的equity（采样）
        hands = current_range.to_hands()
        if len(hands) > 100:
            # 太多手牌，随机采样
            import random
            hands = random.sample(hands, 100)

        # 保留equity在0.3-0.85之间的牌
        # Check通常不会是nuts（>85%）或pure air（<30%）
        filtered_combos = set()

        for hand in hands:
            try:
                # 简单估算：如果在范围内，假设合理
                # 实际实现可以计算equity，但会很慢
                # 这里用启发式：保留大部分牌，移除顶端
                filtered_combos.add(hand.to_combo())
            except:
                continue

        # 如果是TAG/Nit，check更可能是弱牌
        if player_type in [PlayerType.TAG, PlayerType.NIT]:
            # 移除最强的20%
            top_20_percent = int(len(filtered_combos) * 0.2)
            # 简化：保留全部（实际应该按equity排序）
            pass

        # 如果filtered_combos为空，返回原范围的70%（保守估计）
        if not filtered_combos:
            filtered_combos = current_range.combos

        return Range(filtered_combos)

    def _update_on_bet(self,
                      current_range: Range,
                      sizing: Optional[float],
                      board: Board,
                      player_type: PlayerType,
                      pot: float) -> Range:
        """
        Bet/Raise行动后更新范围

        启发式：
        - 大注（>75% pot）→ 极化范围（strong + bluff）
        - 中注（50-75%）→ 合并范围（all value）
        - 小注（<50%）→ 宽范围（value + draws）
        """
        if sizing is None:
            sizing = 0.66  # 默认2/3 pot

        texture = BoardTexture(board)
        hands = current_range.to_hands()

        # 简化实现：基于sizing和玩家类型过滤
        if sizing >= 0.75:
            # 大注：保留强牌和部分弱牌（bluff）
            # 移除中等强度的牌
            if player_type == PlayerType.MANIAC:
                # Maniac可能bluff很多
                keep_ratio = 0.9
            elif player_type == PlayerType.TAG:
                # TAG比较平衡
                keep_ratio = 0.6
            elif player_type == PlayerType.NIT:
                # Nit很少bluff
                keep_ratio = 0.4
            else:
                keep_ratio = 0.7

        elif sizing >= 0.50:
            # 中注：保留大部分
            keep_ratio = 0.8

        else:
            # 小注：保留几乎全部
            keep_ratio = 0.95

        # 简化：随机保留一定比例（实际应该按equity过滤）
        import random
        filtered_hands = random.sample(hands, max(1, int(len(hands) * keep_ratio)))

        filtered_combos = {hand.to_combo() for hand in filtered_hands}

        return Range(filtered_combos) if filtered_combos else current_range

    def _update_on_call(self,
                       current_range: Range,
                       board: Board,
                       player_type: PlayerType) -> Range:
        """
        Call行动后更新范围

        启发式：Call通常是中等强度或听牌
        """
        # Call移除最弱和最强的牌
        # 保留中间60-80%

        hands = current_range.to_hands()

        # 简化：保留大部分
        if player_type == PlayerType.CALLING_STATION:
            keep_ratio = 0.95  # Calling station什么都call
        elif player_type in [PlayerType.TAG, PlayerType.LAG]:
            keep_ratio = 0.75
        else:
            keep_ratio = 0.80

        import random
        filtered_hands = random.sample(hands, max(1, int(len(hands) * keep_ratio)))
        filtered_combos = {hand.to_combo() for hand in filtered_hands}

        return Range(filtered_combos) if filtered_combos else current_range

    # ===== 辅助方法 =====

    def estimate_range_strength(self,
                               range_obj: Range,
                               board: Board) -> Dict[str, float]:
        """
        估算范围整体强度

        Args:
            range_obj: 范围对象
            board: 公共牌

        Returns:
            强度指标字典
        """
        hands = range_obj.to_hands()

        if not hands:
            return {
                'avg_equity': 0.0,
                'top_10_percent': 0.0,
                'polarization': 0.0,
            }

        # 采样计算（避免太慢）
        import random
        sample_size = min(50, len(hands))
        sampled_hands = random.sample(hands, sample_size)

        # 简单估算equity（这里简化，实际需要vs对手范围）
        # 暂时返回固定值
        return {
            'avg_equity': 0.5,
            'top_10_percent': 0.8,
            'polarization': 0.3,
        }

    def categorize_range_advantage(self,
                                   hero_range: Range,
                                   villain_range: Range,
                                   board: Board) -> str:
        """
        判断范围优势

        Args:
            hero_range: 我方范围
            villain_range: 对手范围
            board: 公共牌

        Returns:
            'strong', 'medium', 'weak'
        """
        # 简化实现：比较范围大小和强度
        hero_size = len(hero_range)
        villain_size = len(villain_range)

        if hero_size > villain_size * 1.3:
            return 'strong'
        elif hero_size > villain_size * 0.8:
            return 'medium'
        else:
            return 'weak'


# ===== 便捷函数 =====

def estimate_villain_range(position: str,
                          action: str,
                          player_type: PlayerType,
                          vs_position: Optional[str] = None) -> Range:
    """
    便捷函数：估计对手翻前范围

    Args:
        position: 位置字符串（'BTN', 'BB', etc.）
        action: 行动字符串（'open', '3bet', etc.）
        player_type: 玩家类型
        vs_position: 对手位置（可选）

    Returns:
        Range对象
    """
    estimator = RangeEstimator()

    pos = Position[position.upper()]

    # 处理数字前缀的行动（3bet -> THREE_BET, 4bet -> FOUR_BET）
    action_map = {
        '3BET': 'THREE_BET',
        '4BET': 'FOUR_BET',
    }
    action_key = action.upper().replace('-', '_')
    action_key = action_map.get(action_key, action_key)
    act = Action[action_key]

    vs_pos = Position[vs_position.upper()] if vs_position else None

    return estimator.estimate_preflop_range(pos, act, player_type, vs_pos)
