"""
公共牌结构分析器 (Board Texture Analyzer)

分析牌面特征:
1. 基础特征: 对子/三条/四条
2. 同花面: 2/3/4张同花
3. 顺子面: 连接性
4. 高牌/中牌/低牌分布
5. 湿度 (wetness): dry/medium/wet

用于:
- 范围更新 (哪些牌在这个面更强)
- 下注尺寸调整 (湿面小注保护，干面大注)
- Bluff频率调整 (湿面多bluff outs)
"""
from typing import List, Tuple
from treys import Card
from collections import Counter


class BoardTexture:
    """公共牌结构分析"""

    RANK_ORDER = '23456789TJQKA'
    RANK_VALUES = {r: i for i, r in enumerate(RANK_ORDER)}

    def __init__(self, board: List[int]):
        """
        初始化

        Args:
            board: treys格式的公共牌 [Card, Card, Card] 或 更多
        """
        self.board = board
        self.ranks = [Card.get_rank_int(c) for c in board]
        self.suits = [Card.get_suit_int(c) for c in board]

        # 转换为字符表示
        self.rank_chars = [self._rank_int_to_char(r) for r in self.ranks]
        self.suit_chars = [self._suit_int_to_char(s) for s in self.suits]

        # 预计算特征
        self._compute_features()

    def _compute_features(self):
        """预计算所有特征"""
        self.has_pair = self._check_pair()
        self.has_trips = self._check_trips()
        self.has_quads = self._check_quads()

        self.flush_draw_possible = self._check_flush_draw()
        self.straight_draw_possible = self._check_straight_draw()

        self.high_card_count = self._count_high_cards()
        self.mid_card_count = self._count_mid_cards()
        self.low_card_count = self._count_low_cards()

        self.connectivity = self._compute_connectivity()
        self.wetness = self._compute_wetness()

    # ===== 基础特征检测 =====

    def _check_pair(self) -> bool:
        """检查是否有对子"""
        rank_counts = Counter(self.rank_chars)
        return any(count >= 2 for count in rank_counts.values())

    def _check_trips(self) -> bool:
        """检查是否有三条"""
        rank_counts = Counter(self.rank_chars)
        return any(count >= 3 for count in rank_counts.values())

    def _check_quads(self) -> bool:
        """检查是否有四条"""
        rank_counts = Counter(self.rank_chars)
        return any(count >= 4 for count in rank_counts.values())

    def _check_flush_draw(self) -> bool:
        """检查是否有同花面 (2+张同花)"""
        suit_counts = Counter(self.suit_chars)
        max_suit = max(suit_counts.values()) if suit_counts else 0
        return max_suit >= 2

    def _check_straight_draw(self) -> bool:
        """
        检查是否有顺子面

        简化判断: 如果有2张以上的牌间隔<=4，则认为有顺子可能
        """
        if len(self.board) < 2:
            return False

        values = sorted([self.RANK_VALUES[r] for r in self.rank_chars])

        # 特殊处理: A可以作为1
        if 'A' in self.rank_chars:
            values_with_ace_low = values + [self.RANK_VALUES['A'] - 13]
            values = sorted(set(values_with_ace_low))

        # 检查是否有连续性
        for i in range(len(values) - 1):
            if values[i+1] - values[i] <= 4:
                return True

        return False

    def _count_high_cards(self) -> int:
        """高牌数量 (T+)"""
        return sum(1 for r in self.rank_chars if r in 'TJQKA')

    def _count_mid_cards(self) -> int:
        """中牌数量 (6-9)"""
        return sum(1 for r in self.rank_chars if r in '6789')

    def _count_low_cards(self) -> int:
        """低牌数量 (2-5)"""
        return sum(1 for r in self.rank_chars if r in '2345')

    def _compute_connectivity(self) -> str:
        """
        连接性评估

        Returns:
            'high': 高度连接 (如 789, JQK)
            'medium': 中度连接 (如 68T, Q35)
            'low': 低连接/彩虹面 (如 A72r, K63r)
        """
        if len(self.board) < 3:
            return 'low'

        values = sorted([self.RANK_VALUES[r] for r in self.rank_chars])

        # 检查最大间隔
        max_gap = max(values[i+1] - values[i] for i in range(len(values) - 1))

        if max_gap <= 2:
            return 'high'  # 非常连接
        elif max_gap <= 4:
            return 'medium'
        else:
            return 'low'

    def _compute_wetness(self) -> str:
        """
        牌面湿度综合评估

        Returns:
            'dry': 干燥面 (如 Ar7r2r, KhQc3d)
            'medium': 中等 (如 Th9s5c, KhJs6d)
            'wet': 湿润面 (如 Ts9s8h, JhTh9c)
        """
        score = 0

        # 对子/三条降低湿度
        if self.has_trips:
            score -= 2
        elif self.has_pair:
            score -= 1

        # 同花面
        suit_counts = Counter(self.suit_chars)
        max_suit = max(suit_counts.values()) if suit_counts else 0
        if max_suit >= 3:
            score += 3
        elif max_suit >= 2:
            score += 1

        # 连接性
        if self.connectivity == 'high':
            score += 3
        elif self.connectivity == 'medium':
            score += 1

        # 高牌数量 (高牌多 -> 更dry，因为范围hit率低)
        if self.high_card_count >= 2:
            score -= 2  # 增加权重

        # 中低牌多 -> 更wet (更多顺子可能)
        if self.mid_card_count + self.low_card_count >= 2:
            score += 1

        # 评分映射
        if score <= 0:
            return 'dry'
        elif score <= 2:
            return 'medium'
        else:
            return 'wet'

    # ===== 范围优势分析 =====

    def favors_caller_or_raiser(self) -> str:
        """
        判断牌面更有利于caller还是raiser

        一般规律:
        - 低牌连接面 (如 876, 654) -> 有利于caller (可以有更多小对/同花听牌)
        - 高牌面 (如 AKx, KQx) -> 有利于raiser (更可能有大对/TPTK)
        - 干燥高牌 (如 Ar7r2r) -> 强烈有利于raiser
        - 湿润中低牌 (如 9s8s5h) -> 有利于caller

        Returns:
            'raiser': 有利于加注者
            'caller': 有利于跟注者
            'neutral': 中性
        """
        if self.wetness == 'dry' and self.high_card_count >= 2:
            return 'raiser'

        if self.wetness == 'wet' and self.high_card_count <= 1:
            return 'caller'

        if self.high_card_count >= 2:
            return 'raiser'

        if self.connectivity == 'high':
            return 'caller'

        return 'neutral'

    def suggested_cbet_size(self, pot: int) -> float:
        """
        建议的C-bet尺寸

        Args:
            pot: 当前底池大小

        Returns:
            建议下注量 (占底池比例)
        """
        if self.wetness == 'dry':
            return 0.33  # 小注 (对手没什么outs)

        if self.wetness == 'wet':
            return 0.75  # 大注 (保护，不给对手好价格)

        return 0.50  # 标准半池

    # ===== 辅助方法 =====

    def _rank_int_to_char(self, rank_int: int) -> str:
        """
        treys rank_int -> char

        treys rank: 0=Deuce, 1=Trey, ..., 12=Ace
        """
        return self.RANK_ORDER[rank_int]

    def _suit_int_to_char(self, suit_int: int) -> str:
        """
        treys suit_int -> char

        treys suit: 1=spade, 2=heart, 4=diamond, 8=club
        """
        suit_map = {1: 's', 2: 'h', 4: 'd', 8: 'c'}
        return suit_map.get(suit_int, '?')

    def __repr__(self):
        board_str = ' '.join([Card.int_to_str(c) for c in self.board])
        return (f"BoardTexture({board_str}): "
                f"wetness={self.wetness}, connectivity={self.connectivity}, "
                f"flush_draw={self.flush_draw_possible}, straight_draw={self.straight_draw_possible}")


# ===== 示例用法 =====

if __name__ == '__main__':
    # 测试不同牌面
    print("=== Dry Board ===")
    board1 = [Card.new('As'), Card.new('7h'), Card.new('2d')]
    texture1 = BoardTexture(board1)
    print(texture1)
    print(f"Favors: {texture1.favors_caller_or_raiser()}")
    print(f"Suggested C-bet: {texture1.suggested_cbet_size(100):.2f} pot")

    print("\n=== Wet Board ===")
    board2 = [Card.new('Ts'), Card.new('9s'), Card.new('8h')]
    texture2 = BoardTexture(board2)
    print(texture2)
    print(f"Favors: {texture2.favors_caller_or_raiser()}")
    print(f"Suggested C-bet: {texture2.suggested_cbet_size(100):.2f} pot")

    print("\n=== Medium Board ===")
    board3 = [Card.new('Kh'), Card.new('Jc'), Card.new('6d')]
    texture3 = BoardTexture(board3)
    print(texture3)
    print(f"Favors: {texture3.favors_caller_or_raiser()}")
    print(f"Suggested C-bet: {texture3.suggested_cbet_size(100):.2f} pot")

    print("\n=== Paired Board ===")
    board4 = [Card.new('Qc'), Card.new('Qh'), Card.new('3s')]
    texture4 = BoardTexture(board4)
    print(texture4)
    print(f"Has pair: {texture4.has_pair}")
    print(f"Wetness: {texture4.wetness}")

    print("\n=== Flush Draw Board ===")
    board5 = [Card.new('Ah'), Card.new('Kh'), Card.new('Th')]
    texture5 = BoardTexture(board5)
    print(texture5)
    print(f"Flush draw possible: {texture5.flush_draw_possible}")
    print(f"Wetness: {texture5.wetness}")
