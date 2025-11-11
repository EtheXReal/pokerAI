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
from typing import List, Dict
from collections import Counter
from .cards import Card, Board


class BoardTexture:
    """公共牌结构分析"""

    def __init__(self, board: Board):
        """
        初始化

        Args:
            board: Board对象
        """
        self.board = board
        self.cards = board.cards

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
        rank_counts = Counter(card.rank.value for card in self.cards)
        return any(count >= 2 for count in rank_counts.values())

    def _check_trips(self) -> bool:
        """检查是否有三条"""
        rank_counts = Counter(card.rank.value for card in self.cards)
        return any(count >= 3 for count in rank_counts.values())

    def _check_quads(self) -> bool:
        """检查是否有四条"""
        rank_counts = Counter(card.rank.value for card in self.cards)
        return any(count >= 4 for count in rank_counts.values())

    def _check_flush_draw(self) -> bool:
        """检查是否有同花面 (2+张同花)"""
        suit_counts = Counter(card.suit for card in self.cards)
        max_suit = max(suit_counts.values()) if suit_counts else 0
        return max_suit >= 2

    def _check_straight_draw(self) -> bool:
        """
        检查是否有顺子面

        简化判断: 如果有2张以上的牌间隔<=4，则认为有顺子可能
        """
        if len(self.cards) < 2:
            return False

        # 获取所有rank值
        ranks = sorted([card.rank.value for card in self.cards])

        # 特殊处理: A可以作为1
        if 14 in ranks:  # A = 14
            ranks_with_ace_low = ranks + [1]
            ranks = sorted(set(ranks_with_ace_low))

        # 检查是否有连续性 (间隔 <= 4)
        for i in range(len(ranks) - 1):
            if ranks[i+1] - ranks[i] <= 4:
                return True

        return False

    def _count_high_cards(self) -> int:
        """计算高牌数量 (T+)"""
        return sum(1 for card in self.cards if card.rank.value >= 10)

    def _count_mid_cards(self) -> int:
        """计算中牌数量 (6-9)"""
        return sum(1 for card in self.cards if 6 <= card.rank.value <= 9)

    def _count_low_cards(self) -> int:
        """计算低牌数量 (2-5)"""
        return sum(1 for card in self.cards if 2 <= card.rank.value <= 5)

    def _compute_connectivity(self) -> float:
        """
        计算连接性 (0.0-1.0)

        连接性越高，越容易形成顺子
        """
        if len(self.cards) < 2:
            return 0.0

        ranks = sorted([card.rank.value for card in self.cards])

        # 计算相邻牌的间隔
        gaps = []
        for i in range(len(ranks) - 1):
            gap = ranks[i+1] - ranks[i]
            gaps.append(gap)

        # 平均间隔越小，连接性越高
        avg_gap = sum(gaps) / len(gaps)

        # 映射到 0-1: gap=1(完美连接)→1.0, gap=4(分散)→0.0
        connectivity = max(0.0, 1.0 - (avg_gap - 1) / 3.0)

        return connectivity

    def _compute_wetness(self) -> str:
        """
        计算牌面湿度 (dry/medium/wet)

        考虑因素:
        - 同花面
        - 顺子面
        - 连接性
        - 高牌数量
        """
        score = 0

        # 同花面 (+2)
        if self.flush_draw_possible:
            suit_counts = Counter(card.suit for card in self.cards)
            max_suit = max(suit_counts.values())
            if max_suit >= 3:
                score += 3  # 3张同花很湿
            elif max_suit == 2:
                score += 2

        # 顺子面 (+2)
        if self.straight_draw_possible:
            score += 2

        # 连接性 (+1)
        if self.connectivity > 0.6:
            score += 1

        # 高牌多 (+1)
        if self.high_card_count >= 2:
            score += 1

        # 对子面 (-1，减少湿度)
        if self.has_pair:
            score -= 1

        # 分类
        if score <= 2:
            return 'dry'
        elif score <= 4:
            return 'medium'
        else:
            return 'wet'

    # ===== 决策辅助方法 =====

    def favors_caller_or_raiser(self) -> str:
        """
        判断牌面更有利于 caller 还是 raiser

        Returns:
            'raiser': 干燥高牌面，raiser范围优势
            'caller': 湿润连牌面，caller有更多听牌
        """
        # 干燥高牌面 → raiser
        if self.wetness == 'dry' and self.high_card_count >= 2:
            return 'raiser'

        # 湿润低牌/连牌面 → caller
        if self.wetness == 'wet' or self.connectivity > 0.7:
            return 'caller'

        # 中等 → 平衡
        return 'balanced'

    def suggested_cbet_size(self, pot: float) -> float:
        """
        建议的c-bet尺寸 (作为pot的百分比)

        Args:
            pot: 底池大小

        Returns:
            下注尺寸占pot的百分比 (0.33, 0.50, 0.66, 0.75, 1.0)
        """
        # 干燥面 → 小注 (33%-50%)
        if self.wetness == 'dry':
            if self.high_card_count >= 2:
                return 0.50  # 高牌干燥面，标准尺寸
            else:
                return 0.33  # 低牌干燥面，小注

        # 湿润面 → 大注保护 (66%-100%)
        elif self.wetness == 'wet':
            if self.flush_draw_possible:
                suit_counts = Counter(card.suit for card in self.cards)
                max_suit = max(suit_counts.values())
                if max_suit >= 3:
                    return 1.0  # 3张同花，pot bet
                else:
                    return 0.75  # 2张同花，75%
            else:
                return 0.66  # 其他湿润面，2/3 pot

        # 中等 → 标准尺寸 (50%-66%)
        else:
            return 0.50

    def to_dict(self) -> Dict:
        """
        转换为字典表示

        Returns:
            包含所有特征的字典
        """
        return {
            'has_pair': self.has_pair,
            'has_trips': self.has_trips,
            'has_quads': self.has_quads,
            'flush_draw_possible': self.flush_draw_possible,
            'straight_draw_possible': self.straight_draw_possible,
            'high_card_count': self.high_card_count,
            'mid_card_count': self.mid_card_count,
            'low_card_count': self.low_card_count,
            'connectivity': self.connectivity,
            'wetness': self.wetness,
            'favors': self.favors_caller_or_raiser(),
        }

    def __str__(self) -> str:
        """字符串表示"""
        features = []

        if self.has_quads:
            features.append("4条")
        elif self.has_trips:
            features.append("3条")
        elif self.has_pair:
            features.append("对子")

        if self.flush_draw_possible:
            suit_counts = Counter(card.suit for card in self.cards)
            max_suit = max(suit_counts.values())
            if max_suit >= 3:
                features.append("3同花")
            else:
                features.append("2同花")

        if self.straight_draw_possible:
            features.append("顺子面")

        features.append(f"湿度:{self.wetness}")
        features.append(f"有利:{self.favors_caller_or_raiser()}")

        return f"BoardTexture({', '.join(features)})"

    def __repr__(self) -> str:
        return self.__str__()
