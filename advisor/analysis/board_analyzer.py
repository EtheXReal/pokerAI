"""
BoardAnalyzer - Board texture分析

分析board的特征，包括：
1. Texture识别（dry/wet/dynamic）
2. 花色和连牌分析
3. Draw识别（flush draw, straight draw）
4. Equity realization估计（IP vs OOP）
"""

from typing import List, Dict, Set
from advisor.core.interfaces.analysis_interface import IBoardAnalyzer
from advisor.core.data_structures import BoardAnalysis
from poker_core.cards import Card, Rank


class BoardAnalyzer(IBoardAnalyzer):
    """
    Board分析器实现

    分析board texture及其对range的影响。
    """

    def __init__(self):
        """初始化BoardAnalyzer"""
        # 使用Rank枚举作为键（card.rank是Rank枚举）
        self.rank_values = {
            Rank.TWO: 2, Rank.THREE: 3, Rank.FOUR: 4, Rank.FIVE: 5,
            Rank.SIX: 6, Rank.SEVEN: 7, Rank.EIGHT: 8, Rank.NINE: 9,
            Rank.TEN: 10, Rank.JACK: 11, Rank.QUEEN: 12, Rank.KING: 13, Rank.ACE: 14
        }

    def analyze(self, board: List[Card]) -> BoardAnalysis:
        """
        分析board texture

        Args:
            board: Board（3/4/5张牌）

        Returns:
            BoardAnalysis对象
        """
        if not board or len(board) < 3:
            # Board不完整，返回默认值
            return BoardAnalysis(
                board=board,
                street='preflop',
                texture='neutral',
                texture_score=0.5
            )

        # 确定street
        street = self._determine_street(len(board))

        # 基础特征分析
        is_paired = self._is_paired(board)
        is_monotone = self._is_monotone(board)
        is_two_tone = self._is_two_tone(board)
        is_rainbow = self._is_rainbow(board)
        is_connected = self._is_connected(board)

        # 听牌分析
        draw_heavy = self._is_draw_heavy(board)
        flush_draw_possible = self._has_flush_draw(board)
        straight_draw_possible = self._has_straight_draw(board)
        oesd_possible = self._has_oesd(board)
        gutshot_possible = self._has_gutshot(board)

        # 高牌分析
        high_card_heavy = self._is_high_card_heavy(board)
        broadway_heavy = self._is_broadway_heavy(board)
        low_card_heavy = self._is_low_card_heavy(board)

        # Texture评分和分类
        texture_score = self._calculate_texture_score(
            is_connected, flush_draw_possible, straight_draw_possible, is_paired
        )
        texture = self._classify_texture(texture_score)

        # Dynamic score
        dynamic_score = self._calculate_dynamic_score(
            street, texture_score, draw_heavy
        )

        # Equity realization
        equity_realization_factor = self._estimate_equity_realization(
            texture, is_connected, draw_heavy
        )

        return BoardAnalysis(
            board=board,
            street=street,
            texture=texture,
            texture_score=texture_score,
            is_paired=is_paired,
            is_monotone=is_monotone,
            is_two_tone=is_two_tone,
            is_rainbow=is_rainbow,
            is_connected=is_connected,
            draw_heavy=draw_heavy,
            high_card_heavy=high_card_heavy,
            broadway_heavy=broadway_heavy,
            low_card_heavy=low_card_heavy,
            flush_draw_possible=flush_draw_possible,
            straight_draw_possible=straight_draw_possible,
            oesd_possible=oesd_possible,
            gutshot_possible=gutshot_possible,
            equity_realization_factor=equity_realization_factor,
            dynamic_score=dynamic_score
        )

    def _determine_street(self, board_size: int) -> str:
        """确定当前street"""
        if board_size == 3:
            return 'flop'
        elif board_size == 4:
            return 'turn'
        elif board_size == 5:
            return 'river'
        return 'unknown'

    def _is_paired(self, board: List[Card]) -> bool:
        """判断board是否paired"""
        ranks = [card.rank for card in board]
        return len(ranks) != len(set(ranks))

    def _is_monotone(self, board: List[Card]) -> bool:
        """判断是否单色（所有牌同花）"""
        if len(board) < 3:
            return False
        suits = [card.suit for card in board]
        return len(set(suits)) == 1

    def _is_two_tone(self, board: List[Card]) -> bool:
        """判断是否两色"""
        if len(board) < 3:
            return False
        suits = [card.suit for card in board]
        suit_counts = {}
        for suit in suits:
            suit_counts[suit] = suit_counts.get(suit, 0) + 1

        # 两色：一种花色有2张，另一种有1张（或更多）
        return len(suit_counts) == 2

    def _is_rainbow(self, board: List[Card]) -> bool:
        """判断是否彩虹（所有牌不同花）"""
        if len(board) < 3:
            return False
        suits = [card.suit for card in board]
        return len(set(suits)) == len(suits)

    def _is_connected(self, board: List[Card]) -> bool:
        """判断是否连牌"""
        if len(board) < 3:
            return False

        ranks = [self.rank_values[card.rank] for card in board]
        ranks_sorted = sorted(ranks)

        # 检查是否有连续的牌
        for i in range(len(ranks_sorted) - 1):
            if ranks_sorted[i+1] - ranks_sorted[i] <= 2:
                # 有gap ≤ 2的牌，认为是connected
                return True

        # 特殊情况：A-2-3, A-2-4, A-2-5（A可以作为1）
        if 14 in ranks and 2 in ranks:
            return True

        return False

    def _has_flush_draw(self, board: List[Card]) -> bool:
        """判断是否有flush draw可能"""
        if len(board) < 3:
            return False

        suits = [card.suit for card in board]
        suit_counts = {}
        for suit in suits:
            suit_counts[suit] = suit_counts.get(suit, 0) + 1

        # 有2张或3张同花
        max_suit_count = max(suit_counts.values())
        return max_suit_count >= 2

    def _has_straight_draw(self, board: List[Card]) -> bool:
        """判断是否有straight draw可能"""
        if len(board) < 3:
            return False

        ranks = [self.rank_values[card.rank] for card in board]
        ranks_sorted = sorted(set(ranks))

        # 检查是否有可能形成顺子
        # 如果有连续或接近连续的牌，就有straight draw
        for i in range(len(ranks_sorted) - 1):
            if ranks_sorted[i+1] - ranks_sorted[i] <= 3:
                return True

        # A-low straight
        if 14 in ranks and 2 in ranks:
            return True

        return False

    def _has_oesd(self, board: List[Card]) -> bool:
        """判断是否有开放式顺子听牌（OESD）"""
        if len(board) < 3:
            return False

        ranks = [self.rank_values[card.rank] for card in board]
        ranks_sorted = sorted(set(ranks))

        # OESD: 需要有连续的3张或4张
        for i in range(len(ranks_sorted) - 2):
            if i + 1 < len(ranks_sorted):
                diff1 = ranks_sorted[i+1] - ranks_sorted[i]
                if i + 2 < len(ranks_sorted):
                    diff2 = ranks_sorted[i+2] - ranks_sorted[i+1]
                    if diff1 == 1 and diff2 == 1:
                        # 有连续3张
                        return True
                    if diff1 <= 2 and diff2 <= 2:
                        # 有gap但接近连续
                        return True

        return False

    def _has_gutshot(self, board: List[Card]) -> bool:
        """判断是否有gutshot（内顺听牌）"""
        # 简化：如果有straight draw但不是OESD，可能是gutshot
        return self._has_straight_draw(board) and not self._has_oesd(board)

    def _is_draw_heavy(self, board: List[Card]) -> bool:
        """判断是否听牌多"""
        flush = self._has_flush_draw(board)
        straight = self._has_straight_draw(board)

        # 同时有flush和straight draw → draw heavy
        return flush and straight

    def _is_high_card_heavy(self, board: List[Card]) -> bool:
        """判断是否高牌多"""
        if len(board) < 3:
            return False

        high_cards = sum(1 for card in board if self.rank_values[card.rank] >= 10)
        return high_cards >= 2

    def _is_broadway_heavy(self, board: List[Card]) -> bool:
        """判断是否Broadway牌多（T, J, Q, K, A）"""
        if len(board) < 3:
            return False

        broadway_count = sum(1 for card in board if self.rank_values[card.rank] >= 10)
        return broadway_count >= 2

    def _is_low_card_heavy(self, board: List[Card]) -> bool:
        """判断是否低牌多"""
        if len(board) < 3:
            return False

        low_cards = sum(1 for card in board if self.rank_values[card.rank] <= 7)
        return low_cards >= 2

    def _calculate_texture_score(self, is_connected: bool, flush_draw: bool,
                                 straight_draw: bool, is_paired: bool) -> float:
        """
        计算texture评分

        Returns:
            0-1的评分，0=dry, 1=wet
        """
        score = 0.0

        # Connected增加wetness
        if is_connected:
            score += 0.3

        # Flush draw增加wetness
        if flush_draw:
            score += 0.25

        # Straight draw增加wetness
        if straight_draw:
            score += 0.25

        # Paired略微减少wetness（更静态）
        if is_paired:
            score -= 0.1

        # Clamp to [0, 1]
        return max(0.0, min(1.0, score))

    def _classify_texture(self, texture_score: float) -> str:
        """
        分类texture

        Args:
            texture_score: 0-1的评分

        Returns:
            'dry', 'wet', 'dynamic', 或 'static'
        """
        if texture_score >= 0.6:
            return 'wet'
        elif texture_score >= 0.35:
            return 'dynamic'
        elif texture_score >= 0.15:
            return 'neutral'
        else:
            return 'dry'

    def _calculate_dynamic_score(self, street: str, texture_score: float,
                                 draw_heavy: bool) -> float:
        """
        计算board的动态性

        动态性：board在未来街道变化的可能性

        Returns:
            0-1的评分
        """
        if street == 'river':
            return 0.0  # River没有未来街道

        dynamic = texture_score

        # Draw heavy的board更动态
        if draw_heavy:
            dynamic += 0.2

        # Turn比flop更静态（只剩1张）
        if street == 'turn':
            dynamic *= 0.7

        return max(0.0, min(1.0, dynamic))

    def _estimate_equity_realization(self, texture: str, is_connected: bool,
                                    draw_heavy: bool) -> float:
        """
        估计equity realization factor

        OOP在wet board上很难实现equity。
        IP在wet board上能更好地实现equity。

        这个factor用于调整OOP的equity。

        Returns:
            0.7-1.0的factor（OOP的equity实现率）
        """
        # 基础值：0.85（OOP通常实现85%的equity）
        factor = 0.85

        # Wet board → OOP更难实现
        if texture == 'wet':
            factor -= 0.10
        elif texture == 'dynamic':
            factor -= 0.05

        # Connected board → OOP更难实现
        if is_connected:
            factor -= 0.03

        # Draw heavy → OOP更难实现
        if draw_heavy:
            factor -= 0.05

        # Clamp
        return max(0.70, min(1.0, factor))

    def get_texture_score(self, board: List[Card]) -> float:
        """
        获取texture评分

        Args:
            board: Board

        Returns:
            0-1的评分
        """
        analysis = self.analyze(board)
        return analysis.texture_score

    def estimate_equity_realization(self, position: str, board: List[Card]) -> float:
        """
        估计equity realization factor

        Args:
            position: 'IP' or 'OOP'
            board: Board

        Returns:
            Equity realization factor
        """
        analysis = self.analyze(board)

        if position == 'IP':
            # IP的equity realization通常更好
            return min(1.0, analysis.equity_realization_factor + 0.10)
        else:
            # OOP
            return analysis.equity_realization_factor
