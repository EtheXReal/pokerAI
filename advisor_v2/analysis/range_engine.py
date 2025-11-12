"""
RangeEngine - Range管理和分析

这是range-based决策的核心模块，负责：
1. 管理GTO range库
2. 计算hand在range中的位置（相对强度）
3. 分析range vs range交互
4. 估计对手range
"""

import json
import os
from typing import List, Optional, Dict, Tuple
from collections import defaultdict

from advisor_v2.core.interfaces.analysis_interface import IRangeEngine
from advisor_v2.core.data_structures import RangeAdvantage
from advisor.game_state import Position, Hand, Action
from advisor.range import Range


class RangeEngine(IRangeEngine):
    """
    Range引擎实现

    核心改进：
    - 翻前决策基于hand在range中的相对位置（非绝对hand_strength）
    - 深度range分析（nut advantage + equity分布）
    - 基于对手类型动态调整range估计
    """

    def __init__(self, range_data_path: Optional[str] = None):
        """
        初始化RangeEngine

        Args:
            range_data_path: range数据文件路径，如果为None则使用默认路径
        """
        # 加载range数据
        if range_data_path is None:
            # 默认路径：advisor_v2/data/preflop_ranges.json
            current_dir = os.path.dirname(os.path.abspath(__file__))
            range_data_path = os.path.join(current_dir, '..', 'data', 'preflop_ranges.json')

        with open(range_data_path, 'r') as f:
            self.range_data = json.load(f)

        # 预解析所有range（性能优化：避免重复解析）
        self.range_cache = {}
        self._preload_ranges()

        # Preflop hand strength cache（用于hand percentile计算）
        self.preflop_hand_strength_cache = {}
        self._build_preflop_strength_cache()

    def _preload_ranges(self):
        """预加载所有range到缓存"""
        # Open ranges
        for pos, data in self.range_data['open_ranges'].items():
            range_str = data['range']
            if range_str:  # BB的range是空的
                self.range_cache[f'open_{pos}'] = Range.from_string(range_str)

        # 3-bet ranges
        for key, data in self.range_data['vs_open_3bet_ranges'].items():
            self.range_cache[f'3bet_{key}'] = Range.from_string(data['range'])

        # Call ranges
        for key, data in self.range_data['vs_open_call_ranges'].items():
            self.range_cache[f'call_{key}'] = Range.from_string(data['range'])

        # 4-bet ranges
        for key, data in self.range_data.get('vs_3bet_4bet_ranges', {}).items():
            self.range_cache[f'4bet_{key}'] = Range.from_string(data['range'])

        # Call vs 3-bet ranges
        for key, data in self.range_data.get('vs_3bet_call_ranges', {}).items():
            self.range_cache[f'call_vs_3bet_{key}'] = Range.from_string(data['range'])

    def _build_preflop_strength_cache(self):
        """
        构建翻前hand strength缓存

        这个cache用于快速计算hand在range中的位置。
        基于Sklansky-Malmuth手牌组排名 + 实际equity调整。
        """
        # 简化版：使用标准的hand strength评分
        # 完整版可以从solver数据导入

        # AA=1.0, KK=0.95, QQ=0.90, ...
        pair_strength = {
            'AA': 1.00, 'KK': 0.95, 'QQ': 0.90, 'JJ': 0.85, 'TT': 0.80,
            '99': 0.75, '88': 0.70, '77': 0.65, '66': 0.60, '55': 0.55,
            '44': 0.50, '33': 0.45, '22': 0.40
        }

        # Suited connectors and broadways
        suited_strength = {
            'AKs': 0.92, 'AQs': 0.88, 'AJs': 0.84, 'ATs': 0.80,
            'A9s': 0.70, 'A8s': 0.65, 'A7s': 0.60, 'A6s': 0.58, 'A5s': 0.62,  # A5s有flush+straight潜力
            'A4s': 0.56, 'A3s': 0.54, 'A2s': 0.52,
            'KQs': 0.82, 'KJs': 0.78, 'KTs': 0.74, 'K9s': 0.66, 'K8s': 0.62,
            'K7s': 0.58, 'K6s': 0.54, 'K5s': 0.52, 'K4s': 0.48, 'K3s': 0.46, 'K2s': 0.44,
            'QJs': 0.76, 'QTs': 0.72, 'Q9s': 0.68, 'Q8s': 0.64, 'Q7s': 0.58,
            'Q6s': 0.54, 'Q5s': 0.50, 'Q4s': 0.46, 'Q3s': 0.44, 'Q2s': 0.42,
            'JTs': 0.74, 'J9s': 0.70, 'J8s': 0.66, 'J7s': 0.60, 'J6s': 0.54,
            'J5s': 0.50, 'J4s': 0.48, 'J3s': 0.44, 'J2s': 0.42,
            'T9s': 0.72, 'T8s': 0.68, 'T7s': 0.62, 'T6s': 0.58, 'T5s': 0.54,
            'T4s': 0.50, 'T3s': 0.46, 'T2s': 0.44,
            '98s': 0.70, '97s': 0.64, '96s': 0.60, '95s': 0.56, '94s': 0.52,
            '87s': 0.68, '86s': 0.62, '85s': 0.58, '84s': 0.54,
            '76s': 0.66, '75s': 0.60, '74s': 0.56, '73s': 0.52,
            '65s': 0.64, '64s': 0.58, '63s': 0.54,
            '54s': 0.62, '53s': 0.56, '52s': 0.52,
            '43s': 0.54, '42s': 0.50,
            '32s': 0.52
        }

        # Offsuit hands
        offsuit_strength = {
            'AKo': 0.87, 'AQo': 0.83, 'AJo': 0.79, 'ATo': 0.75,
            'A9o': 0.65, 'A8o': 0.60, 'A7o': 0.55, 'A6o': 0.52, 'A5o': 0.54,
            'A4o': 0.50, 'A3o': 0.48, 'A2o': 0.46,
            'KQo': 0.77, 'KJo': 0.73, 'KTo': 0.69, 'K9o': 0.61, 'K8o': 0.57,
            'K7o': 0.53, 'K6o': 0.49, 'K5o': 0.47, 'K4o': 0.43, 'K3o': 0.41, 'K2o': 0.39,
            'QJo': 0.71, 'QTo': 0.67, 'Q9o': 0.63, 'Q8o': 0.59, 'Q7o': 0.53,
            'Q6o': 0.49, 'Q5o': 0.45, 'Q4o': 0.41, 'Q3o': 0.39, 'Q2o': 0.37,
            'JTo': 0.69, 'J9o': 0.65, 'J8o': 0.61, 'J7o': 0.55, 'J6o': 0.49,
            'J5o': 0.45, 'J4o': 0.43, 'J3o': 0.39, 'J2o': 0.37,
            'T9o': 0.67, 'T8o': 0.63, 'T7o': 0.57, 'T6o': 0.53, 'T5o': 0.49,
            'T4o': 0.45, 'T3o': 0.41, 'T2o': 0.39,
            '98o': 0.65, '97o': 0.59, '96o': 0.55, '95o': 0.51, '94o': 0.47,
            '87o': 0.63, '86o': 0.57, '85o': 0.53, '84o': 0.49,
            '76o': 0.61, '75o': 0.55, '74o': 0.51, '73o': 0.47,
            '65o': 0.59, '64o': 0.53, '63o': 0.49,
            '54o': 0.57, '53o': 0.51, '52o': 0.47,
            '43o': 0.49, '42o': 0.45,
            '32o': 0.47
        }

        self.preflop_hand_strength_cache = {**pair_strength, **suited_strength, **offsuit_strength}

    def get_ideal_range(self, position: Position, action_history: list,
                       stack_depth: Optional[float] = None) -> Range:
        """
        获取GTO理论范围

        Args:
            position: 位置
            action_history: 行动历史
            stack_depth: 有效筹码深度（BB数），暂不使用，预留给未来

        Returns:
            GTO理论range
        """
        if not action_history:
            # 开池range
            cache_key = f'open_{position.name}'
            if cache_key in self.range_cache:
                return self.range_cache[cache_key]
            else:
                # BB不能开池
                return Range.from_string("")

        # 分析行动历史
        last_action = action_history[-1]

        if len(action_history) == 1 and last_action.action == 'raise':
            # 面对open：3-bet或call
            opener_position = self._infer_opener_position(action_history, position)

            # 3-bet range
            three_bet_key = f'3bet_{position.name}_vs_{opener_position.name}'
            if three_bet_key in self.range_cache:
                three_bet_range = self.range_cache[three_bet_key]
            else:
                # 如果没有精确匹配，使用通用3-bet range
                three_bet_range = Range.from_string("99+,ATs+,KQs,AQo+")

            # Call range
            call_key = f'call_{position.name}_vs_{opener_position.name}'
            if call_key in self.range_cache:
                call_range = self.range_cache[call_key]
            else:
                # 通用call range
                call_range = Range.from_string("22-88,A2s+,K5s+,Q8s+,J8s+,T8s+,A5o+,K9o+")

            # 合并3-bet和call range
            combined_range_str = f"{three_bet_range.to_string()},{call_range.to_string()}"
            return Range.from_string(combined_range_str)

        elif len(action_history) == 2:
            # 可能是面对3-bet
            if action_history[0].action == 'raise' and action_history[1].action == 'raise':
                # open → 3-bet，现在我们要4-bet或call

                # 4-bet range
                four_bet_key = f'4bet_{position.name}_vs_BB_3bet'  # 简化，假设是vs BB
                if four_bet_key in self.range_cache:
                    four_bet_range = self.range_cache[four_bet_key]
                else:
                    four_bet_range = Range.from_string("JJ+,AQs+,AKo")

                # Call vs 3-bet range
                call_vs_3bet_key = f'call_vs_3bet_{position.name}_vs_BB_3bet'
                if call_vs_3bet_key in self.range_cache:
                    call_vs_3bet_range = self.range_cache[call_vs_3bet_key]
                else:
                    call_vs_3bet_range = Range.from_string("88-TT,AJs,KQs,AQo")

                # 合并
                combined_range_str = f"{four_bet_range.to_string()},{call_vs_3bet_range.to_string()}"
                return Range.from_string(combined_range_str)

        # 默认：返回较宽的range
        return Range.from_string("22+,A2s+,K5s+,Q8s+,J8s+,T8s+,A5o+,K9o+")

    def get_hand_percentile(self, hand: Hand, range_obj: Range,
                           board: Optional[List] = None) -> float:
        """
        计算hand在range中的位置（0-1）

        这是range-based决策的核心：不看绝对强度，看相对位置。

        Args:
            hand: Hero的手牌
            range_obj: Hero应该持有的range
            board: Board（如果是翻后）

        Returns:
            0-1的百分位数（1.0 = range中最强，0.0 = range中最弱）
        """
        all_hands = range_obj.to_hands()

        if not all_hands:
            return 0.5  # Empty range，返回中间值

        # 检查hand是否在range中
        if hand not in all_hands:
            # Hand不在range中，返回0
            return 0.0

        if not board or len(board) == 0:
            # 翻前：基于preflop strength排序
            hand_strengths = {}
            for h in all_hands:
                strength = self._get_preflop_hand_strength(h)
                hand_strengths[h] = strength

            # 排序
            sorted_hands = sorted(hand_strengths.items(), key=lambda x: x[1], reverse=True)

            # 找到当前hand的排名
            for idx, (h, strength) in enumerate(sorted_hands):
                if h == hand:
                    # Percentile = 1 - (rank / total)
                    # rank=0 (最强) → percentile=1.0
                    # rank=total-1 (最弱) → percentile ≈ 0.0
                    percentile = 1.0 - (idx / len(sorted_hands))
                    return percentile

            return 0.5  # 不应该到这里

        else:
            # 翻后：基于当前equity排序
            # 注意：这里需要equity计算，会在get_hand_percentile被调用时
            # 由EquityEngine提供equity信息
            # 为了避免循环依赖，这里使用简化版：基于hand type

            hand_equities = {}
            for h in all_hands:
                equity = self._estimate_hand_equity_on_board(h, board)
                hand_equities[h] = equity

            # 排序
            sorted_hands = sorted(hand_equities.items(), key=lambda x: x[1], reverse=True)

            # 找到当前hand的排名
            for idx, (h, equity) in enumerate(sorted_hands):
                if h == hand:
                    percentile = 1.0 - (idx / len(sorted_hands))
                    return percentile

            return 0.5

    def _get_preflop_hand_strength(self, hand: Hand) -> float:
        """
        获取翻前hand strength

        Args:
            hand: 手牌

        Returns:
            0-1的strength评分
        """
        # 获取hand的字符串表示
        hand_str = self._hand_to_str(hand)

        # 从cache查找
        if hand_str in self.preflop_hand_strength_cache:
            return self.preflop_hand_strength_cache[hand_str]

        # 如果不在cache中，返回默认值
        return 0.5

    def _hand_to_str(self, hand: Hand) -> str:
        """
        将Hand对象转换为标准字符串表示

        Args:
            hand: Hand对象

        Returns:
            字符串表示，如"AKs", "AKo", "AA"
        """
        if not hand or not hand.cards or len(hand.cards) < 2:
            return ""

        card1, card2 = hand.cards[0], hand.cards[1]
        rank1, rank2 = card1.rank, card2.rank

        # 确保高牌在前
        if self._rank_value(rank1) < self._rank_value(rank2):
            rank1, rank2 = rank2, rank1

        # 判断是否同花
        if card1.suit == card2.suit:
            if rank1 == rank2:
                return f"{rank1}{rank2}"  # Pair
            else:
                return f"{rank1}{rank2}s"  # Suited
        else:
            if rank1 == rank2:
                return f"{rank1}{rank2}"  # Pair
            else:
                return f"{rank1}{rank2}o"  # Offsuit

    def _rank_value(self, rank: str) -> int:
        """将rank转换为数值（用于排序）"""
        rank_order = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8,
                     '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
        return rank_order.get(rank, 0)

    def _estimate_hand_equity_on_board(self, hand: Hand, board: List) -> float:
        """
        简化的翻后equity估计（用于hand percentile计算）

        这是一个快速估计，不进行完整的Monte Carlo模拟。
        真正的equity计算由EquityEngine完成。

        Args:
            hand: 手牌
            board: Board

        Returns:
            估计的equity (0-1)
        """
        # 简化实现：基于hand type
        # 完整实现会调用EquityEngine，但那会导致循环依赖
        # 这里只用于range内部排序，不需要绝对准确

        from advisor.evaluator import Evaluator
        evaluator = Evaluator()

        try:
            # 评估当前hand strength
            hand_rank = evaluator.evaluate(board, hand.cards)

            # 将rank转换为大致的equity估计
            # hand_rank范围：1 (Royal Flush) - 7462 (High Card)
            # equity估计：rank越小（牌越强），equity越高
            estimated_equity = 1.0 - (hand_rank / 7462.0)

            # 调整：将equity缩放到合理范围 (0.15-0.95)
            estimated_equity = 0.15 + estimated_equity * 0.80

            return estimated_equity

        except:
            # 如果评估失败，返回中间值
            return 0.50

    def analyze_range_interaction(self, hero_range: Range, villain_range: Range,
                                  board: List) -> RangeAdvantage:
        """
        分析range vs range交互

        Args:
            hero_range: Hero的range
            villain_range: Villain的range
            board: Board

        Returns:
            RangeAdvantage对象
        """
        # 1. Range size比较
        hero_size = len(hero_range.to_hands())
        villain_size = len(villain_range.to_hands())
        size_ratio = hero_size / villain_size if villain_size > 0 else 1.0

        # 2. Nut advantage（如果有board）
        nut_adv = 0.0
        if board and len(board) >= 3:
            nut_adv = self._calculate_nut_advantage(hero_range, villain_range, board)

        # 3. Equity分布（简化版）
        hero_equity_dist = self._estimate_equity_distribution(hero_range, villain_range, board)
        villain_equity_dist = self._estimate_equity_distribution(villain_range, hero_range, board)

        # 4. 计算advantage_score
        # 综合考虑：nut advantage (40%), range size (30%), equity分布 (30%)
        nut_component = nut_adv * 0.4
        size_component = (size_ratio - 1.0) * 0.2  # size_ratio > 1 → 正分
        equity_component = (hero_equity_dist.get('strong', 0) - villain_equity_dist.get('strong', 0)) * 0.4

        advantage_score = nut_component + size_component + equity_component
        advantage_score = max(-1.0, min(1.0, advantage_score))  # Clamp to [-1, 1]

        # 5. 判断advantage类型
        if abs(nut_adv) > 0.3:
            advantage_type = 'nut'
        elif abs(size_ratio - 1.0) > 0.3:
            advantage_type = 'range'
        else:
            advantage_type = 'none'

        # 6. Board favors
        if advantage_score > 0.15:
            board_favors = 'hero'
        elif advantage_score < -0.15:
            board_favors = 'villain'
        else:
            board_favors = 'neutral'

        return RangeAdvantage(
            advantage_score=advantage_score,
            advantage_type=advantage_type,
            hero_nut_advantage=nut_adv,
            hero_range_size_ratio=size_ratio,
            hero_equity_distribution=hero_equity_dist,
            villain_equity_distribution=villain_equity_dist,
            board_favors=board_favors,
            board_texture_impact=0.0,  # 由BoardAnalyzer提供
            hero_polarization=0.5,  # 简化，默认0.5
            villain_polarization=0.5
        )

    def _calculate_nut_advantage(self, hero_range: Range, villain_range: Range,
                                 board: List) -> float:
        """
        计算nut advantage

        Args:
            hero_range: Hero的range
            villain_range: Villain的range
            board: Board

        Returns:
            -1到1的nut advantage评分
        """
        from advisor.evaluator import Evaluator
        evaluator = Evaluator()

        hero_hands = hero_range.to_hands()
        villain_hands = villain_range.to_hands()

        # 找出所有可能的hands在当前board上的rank
        hero_ranks = []
        villain_ranks = []

        for hand in hero_hands:
            try:
                rank = evaluator.evaluate(board, hand.cards)
                hero_ranks.append(rank)
            except:
                pass

        for hand in villain_hands:
            try:
                rank = evaluator.evaluate(board, hand.cards)
                villain_ranks.append(rank)
            except:
                pass

        if not hero_ranks or not villain_ranks:
            return 0.0

        # 找到最强的牌（rank最小）
        hero_best = min(hero_ranks)
        villain_best = min(villain_ranks)

        # 计算top 10%的平均rank
        hero_top_10 = sorted(hero_ranks)[:max(1, len(hero_ranks) // 10)]
        villain_top_10 = sorted(villain_ranks)[:max(1, len(villain_ranks) // 10)]

        hero_top_avg = sum(hero_top_10) / len(hero_top_10)
        villain_top_avg = sum(villain_top_10) / len(villain_top_10)

        # Nut advantage：比较top hands的质量
        # rank越小越强，所以villain_top_avg - hero_top_avg > 0 表示hero更强
        nut_diff = (villain_top_avg - hero_top_avg) / 7462.0  # 归一化

        # Clamp to [-1, 1]
        nut_advantage = max(-1.0, min(1.0, nut_diff * 5.0))  # 放大差异

        return nut_advantage

    def _estimate_equity_distribution(self, hero_range: Range, villain_range: Range,
                                     board: Optional[List]) -> Dict[str, float]:
        """
        估计equity分布

        Args:
            hero_range: Hero的range
            villain_range: Villain的range
            board: Board

        Returns:
            Equity分布字典
        """
        # 简化实现：基于range质量估计
        # 完整实现需要对每个hero hand计算vs villain range的equity

        hero_hands = hero_range.to_hands()
        if not hero_hands:
            return {'strong': 0, 'medium': 0, 'weak': 1.0}

        # 简化：基于hand count估计
        # 假设强牌占20%，中等牌占50%，弱牌占30%
        return {
            'strong': 0.25,
            'medium': 0.50,
            'weak': 0.25
        }

    def estimate_villain_range(self, villain_position: Position, action_history: list,
                               villain_tendencies: Optional[dict] = None) -> Range:
        """
        估计对手range

        Args:
            villain_position: 对手位置
            action_history: 行动历史
            villain_tendencies: 对手统计（Phase 2实现）

        Returns:
            估计的villain range
        """
        # Phase 1：使用GTO baseline
        # Phase 2：会根据villain_tendencies调整

        # 获取GTO baseline range
        gto_range = self.get_ideal_range(villain_position, action_history)

        # Phase 2会根据player_type调整：
        # - LAG: 扩大range (+30-50%)
        # - TAG: 缩小range (-10-20%)
        # - TIGHT_PASSIVE: 缩小并线性化
        # - LOOSE_PASSIVE: 扩大并线性化

        # 暂时直接返回GTO range
        return gto_range

    def _infer_opener_position(self, action_history: list, hero_position: Position) -> Position:
        """
        根据行动历史推断开池者位置

        这是一个简化实现，实际应该从GameState获取。
        """
        # 简化：假设opener是BTN或CO
        if hero_position == Position.BB:
            # BB面对open，可能是BTN, CO, MP, SB
            # 简化：假设是BTN
            return Position.BTN
        elif hero_position == Position.BTN:
            # BTN面对open，可能是CO, MP
            return Position.CO
        elif hero_position == Position.CO:
            # CO面对open，可能是MP
            return Position.MP
        else:
            # 默认BTN
            return Position.BTN
