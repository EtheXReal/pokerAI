"""
Analysis接口定义

Analysis Layer负责：
1. Range管理和分析（IRangeEngine）
2. Equity计算（IEquityEngine）
3. Board分析（IBoardAnalyzer）
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from advisor_v2.core.data_structures import (
    EquityInfo,
    RangeAdvantage,
    BoardAnalysis
)
from advisor.strategy_engine.gto_baseline import Position
from advisor.range_engine.cards import Hand
from advisor.range_engine.range import Range


# ============================================================================
# Range Engine接口
# ============================================================================

class IRangeEngine(ABC):
    """
    Range引擎接口

    Range-based思维的核心模块，负责：
    1. 管理GTO range库
    2. 计算hand在range中的位置（相对强度）
    3. 分析range vs range交互
    4. 估计对手range
    """

    @abstractmethod
    def get_ideal_range(self, position: Position, action_history: list,
                       stack_depth: Optional[float] = None) -> Range:
        """
        获取GTO理论范围

        Args:
            position: 位置
            action_history: 行动历史
            stack_depth: 有效筹码深度（BB数）

        Returns:
            GTO理论range

        Example:
            # BTN开池range
            range_engine.get_ideal_range(Position.BTN, [])
            # 返回：22+,A2s+,K2s+,Q4s+,J7s+,T7s+,...

            # BB vs BTN open的call range
            range_engine.get_ideal_range(Position.BB, [Action('raise', 3.0)])
            # 返回：22-99,A2s+,K5s+,Q8s+,...
        """
        pass

    @abstractmethod
    def get_hand_percentile(self, hand: Hand, range_obj: Range,
                           board: Optional[List] = None) -> float:
        """
        计算hand在range中的位置（0-1）

        这是range-based决策的核心：
        - 不是看hand的绝对强度（hand_strength）
        - 而是看hand在当前range中的相对位置

        Args:
            hand: Hero的手牌
            range_obj: Hero应该持有的range
            board: Board（如果是翻后）

        Returns:
            0-1的百分位数
            - 1.0表示range中最强的牌
            - 0.5表示range中中等的牌
            - 0.0表示range中最弱的牌

        Example:
            # 翻前：AA在BTN open range中
            get_hand_percentile(Hand('AsAh'), btn_open_range, board=None)
            # 返回：~0.99（range中最强）

            # 翻前：A5o在BTN open range中
            get_hand_percentile(Hand('AsA5h'), btn_open_range, board=None)
            # 返回：~0.65（range中上中等）

            # 翻后：Flop Ks 7h 2c，Hero持有KQs
            get_hand_percentile(Hand('KcQc'), btn_cbet_range, board=[Ks,7h,2c])
            # 返回：~0.85（top pair good kicker在cbet range中很强）
        """
        pass

    @abstractmethod
    def analyze_range_interaction(self, hero_range: Range, villain_range: Range,
                                  board: List) -> RangeAdvantage:
        """
        分析range vs range交互

        这是现代扑克的核心：不只看自己的牌，而是看两个range的交互。

        分析维度：
        1. Range size（谁的range更宽）
        2. Nut advantage（谁拥有最强的牌）
        3. Equity分布（两个range的equity分布对比）
        4. Board interaction（board如何影响两个range）

        Args:
            hero_range: Hero的range
            villain_range: Villain的range
            board: Board

        Returns:
            RangeAdvantage对象，包含：
            - advantage_score: -1到1
            - advantage_type: 'nut', 'range', 'none'
            - hero_nut_advantage: hero拥有nuts的比例
            - board_favors: 'hero', 'villain', 'neutral'

        Example:
            # Flop Ks 7h 2c
            # BTN cbet range vs BB defense range
            analyze_range_interaction(btn_cbet_range, bb_defense_range, [Ks,7h,2c])
            # 返回：RangeAdvantage(
            #   advantage_score=0.35,
            #   advantage_type='nut',  # BTN有KK, 77, 22的set
            #   hero_nut_advantage=0.8,
            #   board_favors='hero'
            # )
        """
        pass

    @abstractmethod
    def estimate_villain_range(self, villain_position: Position, action_history: list,
                               villain_tendencies: Optional[dict] = None) -> Range:
        """
        估计对手range

        基于：
        1. 位置和行动历史（GTO baseline）
        2. 对手tendencies（如果有）

        Args:
            villain_position: 对手位置
            action_history: 行动历史
            villain_tendencies: 对手统计（VPIP, PFR等）

        Returns:
            估计的villain range

        Example:
            # BTN open后，BB不知道对手类型
            estimate_villain_range(Position.BTN, [Action('raise', 3.0)])
            # 返回：标准的BTN open range

            # BTN open后，已知对手是LAG (VPIP=35%, PFR=28%)
            estimate_villain_range(Position.BTN, [Action('raise', 3.0)],
                                  {'vpip': 0.35, 'pfr': 0.28})
            # 返回：扩大40%的range
        """
        pass


# ============================================================================
# Equity Engine接口
# ============================================================================

class IEquityEngine(ABC):
    """
    Equity引擎接口

    负责equity计算，关键改进：
    1. 返回完整EquityInfo（不只是单点equity）
    2. 支持缓存（避免重复计算）
    3. 可配置迭代次数（性能优化）
    """

    @abstractmethod
    def calculate_equity(self, hand: Hand, villain_range: Range, board: List,
                        iterations: int = 200) -> EquityInfo:
        """
        计算完整的equity信息

        Args:
            hand: Hero的手牌
            villain_range: Villain的range
            board: Board
            iterations: Monte Carlo迭代次数（默认200，vs Random足够）

        Returns:
            EquityInfo对象，包含：
            - point_equity: 单点equity
            - equity_distribution: equity分布（关键！）
            - outs: 听牌数
            - implied_odds_factor: implied odds因子

        Example:
            # Flop: Ks 7h 2c，Hero: Kc Qc
            equity_info = calculate_equity(Hand('KcQc'), villain_range, [Ks,7h,2c])
            # 返回：EquityInfo(
            #   point_equity=0.68,
            #   equity_distribution={
            #     'crushing': 0.20,  # vs 20%的villain hands，我们equity > 0.80
            #     'strong': 0.35,    # vs 35%，我们equity 0.65-0.80
            #     'ahead': 0.25,
            #     'flip': 0.15,
            #     'behind': 0.05
            #   },
            #   outs=5,  # 3个Q + 2个K
            #   implied_odds_factor=1.2
            # )
        """
        pass

    @abstractmethod
    def calculate_range_equity(self, hero_range: Range, villain_range: Range,
                              board: List) -> float:
        """
        计算range vs range的平均equity

        用于range advantage分析。

        Args:
            hero_range: Hero的range
            villain_range: Villain的range
            board: Board

        Returns:
            平均equity

        Example:
            # BTN cbet range vs BB call range on Ks 7h 2c
            calculate_range_equity(btn_cbet_range, bb_call_range, [Ks,7h,2c])
            # 返回：0.58
        """
        pass

    @abstractmethod
    def clear_cache(self):
        """清空equity缓存"""
        pass

    @abstractmethod
    def get_cache_stats(self) -> dict:
        """
        获取缓存统计

        Returns:
            {'size': 1500, 'hit_rate': 0.75, 'miss_rate': 0.25}
        """
        pass


# ============================================================================
# Board Analyzer接口
# ============================================================================

class IBoardAnalyzer(ABC):
    """
    Board分析器接口

    分析board texture及其对range的影响。
    """

    @abstractmethod
    def analyze(self, board: List) -> BoardAnalysis:
        """
        分析board texture

        Args:
            board: Board（3/4/5张牌）

        Returns:
            BoardAnalysis对象，包含：
            - texture: 'dry', 'wet', 'dynamic'
            - is_paired, is_monotone, is_connected等特征
            - draw_heavy: 是否听牌多
            - equity_realization_factor: IP vs OOP的实现率差异

        Example:
            # Dry board
            analyze([Ks, 7h, 2c])
            # 返回：BoardAnalysis(
            #   texture='dry',
            #   is_paired=False,
            #   is_rainbow=True,
            #   draw_heavy=False,
            #   equity_realization_factor=0.95
            # )

            # Wet board
            analyze([Qh, Jh, 9c])
            # 返回：BoardAnalysis(
            #   texture='wet',
            #   is_connected=True,
            #   is_two_tone=True,
            #   draw_heavy=True,
            #   flush_draw_possible=True,
            #   straight_draw_possible=True,
            #   equity_realization_factor=0.85
            # )
        """
        pass

    @abstractmethod
    def get_texture_score(self, board: List) -> float:
        """
        获取texture评分

        Args:
            board: Board

        Returns:
            0-1的评分
            - 0.0 = 非常dry (Ks 7h 2c)
            - 1.0 = 非常wet (Qh Jh Th)

        用于动态调整bet sizing和频率。
        """
        pass

    @abstractmethod
    def estimate_equity_realization(self, position: str, board: List) -> float:
        """
        估计equity realization factor

        IP通常有更高的equity realization（能看到更多街道，有位置优势）。
        OOP的equity realization通常是0.80-0.90。

        Args:
            position: 'IP' or 'OOP'
            board: Board

        Returns:
            Equity realization factor (0.7-1.0)

        Example:
            # Dry board，OOP
            estimate_equity_realization('OOP', [Ks,7h,2c])
            # 返回：0.90（dry board上OOP的equity还算能实现）

            # Wet board，OOP
            estimate_equity_realization('OOP', [Qh,Jh,9c])
            # 返回：0.75（wet board上OOP很难实现equity）
        """
        pass
