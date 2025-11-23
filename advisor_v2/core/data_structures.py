"""
核心数据结构定义

这些数据结构是advisor_v2的基础，定义了模块间传递的所有信息。
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any
from enum import Enum

# 复用poker_core的基础类型
from poker_core.cards import Hand, Card
from poker_core.range import Range

# ============================================================================
# 基础枚举和数据类
# ============================================================================

class Position(Enum):
    """
    玩家位置枚举

    支持2-10人游戏的所有位置：
    - 2人: BTN, BB
    - 3-4人: BTN, SB, BB
    - 5-6人: BTN, SB, BB, UTG, CO
    - 7+人: BTN, SB, BB, UTG, MP, CO
    """
    UTG = 'UTG'  # Under the Gun (第一个行动)
    MP = 'MP'    # Middle Position
    CO = 'CO'    # Cut Off
    BTN = 'BTN'  # Button (庄家)
    SB = 'SB'    # Small Blind
    BB = 'BB'    # Big Blind

# Action需要定义（advisor中没有统一的Action类）
@dataclass
class Action:
    """行动类"""
    action: str  # 'fold', 'call', 'raise', 'bet', 'check'
    amount: float = 0.0


# ============================================================================
# Strategy Layer数据结构
# ============================================================================

@dataclass
class StrategyContext:
    """
    策略决策所需的完整上下文

    这个数据结构包含了策略层做决策所需的所有信息，
    由Analysis Layer和Model Layer提供。
    """
    # Game state基础信息
    street: str  # 'preflop', 'flop', 'turn', 'river'
    position: Position
    action_history: List[Action]
    pot_size: float
    effective_stack: float

    # Hero信息
    hero_hand: Hand
    hero_range: Range  # Hero的GTO理论range

    # Villain信息
    villain_range: Range  # 基于对手模型估计的range
    villain_position: Position
    villain_tendencies: Dict[str, float]  # VPIP, PFR, AF等统计

    # Analysis结果
    equity_info: Optional['EquityInfo'] = None  # 完整的equity信息
    range_advantage: Optional['RangeAdvantage'] = None  # Range优势分析
    board_analysis: Optional['BoardAnalysis'] = None  # Board分析

    # Multi-street规划（Phase 2实现）
    future_streets_plan: Optional[Dict[str, Any]] = None

    # 额外上下文
    is_in_position: bool = True
    facing_bet: bool = False
    facing_bet_size: float = 0.0

    def __post_init__(self):
        """计算衍生属性"""
        # 判断是否IP
        position_order = {
            Position.BTN: 5,
            Position.CO: 4,
            Position.MP: 3,
            Position.SB: 1,
            Position.BB: 0
        }
        self.is_in_position = position_order.get(self.position, 0) > position_order.get(self.villain_position, 0)

        # 判断是否facing bet
        # 仅在facing_bet和facing_bet_size都是默认值时，才从action_history推断
        # 否则，使用显式设置的值（由DecisionIntegrator提供）
        if not self.facing_bet and self.facing_bet_size == 0.0 and self.action_history:
            last_action = self.action_history[-1]
            self.facing_bet = last_action.action in ['bet', 'raise']
            self.facing_bet_size = last_action.amount if self.facing_bet else 0.0


@dataclass
class StrategyDecision:
    """
    策略决策结果（带元数据）

    策略不返回单一action，而是返回action分布+sizing分布+元数据。
    这样可以：
    1. 支持混合策略（GTO需要）
    2. 提供决策理由（用于调试）
    3. 记录关键因素（用于验证模块是否被使用）
    """
    # 核心决策
    action_distribution: Dict[str, float]  # {'raise': 0.6, 'call': 0.3, 'fold': 0.1}
    sizing_distribution: Dict[float, float] = field(default_factory=dict)  # {0.5: 0.4, 0.75: 0.6} (pot比例)

    # 元数据（用于调试和验证）
    reasoning: str = ""  # 决策理由
    confidence: float = 1.0  # 置信度 (0-1)
    key_factors: Dict[str, Any] = field(default_factory=dict)  # 关键因素

    # Multi-street规划（Phase 2）
    future_plan: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """验证数据有效性"""
        # 验证action_distribution总和为1
        total = sum(self.action_distribution.values())
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"action_distribution总和必须为1，当前为{total}")

        # 验证sizing_distribution总和为1（如果存在）
        if self.sizing_distribution:
            total_sizing = sum(self.sizing_distribution.values())
            if not (0.99 <= total_sizing <= 1.01):
                raise ValueError(f"sizing_distribution总和必须为1，当前为{total_sizing}")


# ============================================================================
# Analysis Layer数据结构
# ============================================================================

@dataclass
class EquityInfo:
    """
    完整的Equity信息（不只是单点equity）

    为什么需要完整信息？
    - 单点equity（如0.58）不够：需要知道vs哪些hands领先
    - Equity分布：对决策至关重要（value bet vs bluff）
    - Outs和implied odds：影响call决策
    """
    # 核心equity
    point_equity: float  # 单点equity (vs villain range)

    # Equity分布（关键！）
    equity_distribution: Dict[str, float] = field(default_factory=dict)
    # {
    #   'crushing': 0.15,  # vs 15%的villain hands，我们equity > 0.80
    #   'strong': 0.30,    # vs 30%，equity 0.65-0.80
    #   'ahead': 0.25,     # vs 25%，equity 0.55-0.65
    #   'flip': 0.20,      # vs 20%，equity 0.45-0.55
    #   'behind': 0.10     # vs 10%，equity < 0.45
    # }

    # 细分equity（如果需要）
    equity_vs_calling_range: Optional[float] = None
    equity_vs_raising_range: Optional[float] = None
    equity_vs_folding_range: Optional[float] = None

    # Draw信息
    outs: int = 0
    clean_outs: int = 0  # 干净的outs（不会给对手更强牌）

    # Implied odds
    implied_odds_factor: float = 1.0  # >1表示有implied odds
    reverse_implied_odds: float = 0.0  # >0表示有reverse implied odds

    def get_ahead_percentage(self) -> float:
        """获取领先的百分比（crushing + strong + ahead）"""
        return self.equity_distribution.get('crushing', 0) + \
               self.equity_distribution.get('strong', 0) + \
               self.equity_distribution.get('ahead', 0)

    def is_value_hand(self, threshold: float = 0.55) -> bool:
        """判断是否是value hand"""
        return self.point_equity >= threshold


@dataclass
class RangeAdvantage:
    """
    Range优势分析

    Range advantage是现代扑克的核心概念：
    - 不只是range大小，还要看range质量
    - Nut advantage：谁拥有最强的牌
    - Equity分布：两个range的equity分布对比
    - Board interaction：board如何影响两个range
    """
    # 核心评分
    advantage_score: float  # -1到1，正数表示hero有优势
    advantage_type: str = 'none'  # 'nut', 'range', 'none'

    # 详细分析
    hero_nut_advantage: float = 0.0  # -1到1，hero拥有nuts的比例
    hero_range_size_ratio: float = 1.0  # hero range size / villain range size

    # Equity分布对比
    hero_equity_distribution: Dict[str, float] = field(default_factory=dict)
    villain_equity_distribution: Dict[str, float] = field(default_factory=dict)

    # Board interaction
    board_favors: str = 'neutral'  # 'hero', 'villain', 'neutral'
    board_texture_impact: float = 0.0  # Board对range advantage的影响

    # 极化程度
    hero_polarization: float = 0.5  # 0=线性，1=极化
    villain_polarization: float = 0.5

    def has_significant_advantage(self, threshold: float = 0.15) -> bool:
        """判断是否有显著优势"""
        return abs(self.advantage_score) >= threshold

    def should_bet_frequently(self) -> bool:
        """基于range advantage判断是否应该高频bet"""
        # Nut advantage或range advantage都支持高频bet
        return self.advantage_type in ['nut', 'range'] and self.advantage_score > 0.15


@dataclass
class BoardAnalysis:
    """
    Board texture分析

    Board texture影响：
    - 哪个range受益更多
    - Equity realization（IP vs OOP的实现率差异）
    - Bet sizing和频率
    """
    # Board信息
    board: List  # List[Card]
    street: str  # 'flop', 'turn', 'river'

    # 基础texture
    texture: str = 'neutral'  # 'dry', 'wet', 'dynamic', 'static'
    texture_score: float = 0.5  # 0=dry, 1=wet

    # 具体特征
    is_paired: bool = False
    is_monotone: bool = False  # 同花
    is_two_tone: bool = False
    is_rainbow: bool = False
    is_connected: bool = False  # 连牌

    # 高级特征
    draw_heavy: bool = False  # 听牌多
    high_card_heavy: bool = False  # 高牌多
    broadway_heavy: bool = False  # 百老汇牌多（AKQJT）
    low_card_heavy: bool = False

    # 具体听牌
    flush_draw_possible: bool = False
    straight_draw_possible: bool = False
    oesd_possible: bool = False  # 开放式顺子听牌
    gutshot_possible: bool = False

    # Equity realization
    equity_realization_factor: float = 1.0  # IP vs OOP，1.0表示相同
    # IP通常有更高的equity realization（能看到更多street）
    # OOP的equity realization通常是0.8-0.9

    # 动态性
    dynamic_score: float = 0.5  # Board的动态性，影响后续街道
    # Flop Ks 7h 2c（dry）→ Turn 6d（变化小）→ dynamic_score = 0.2
    # Flop Qh Jh 9c（wet）→ Turn 8h（变化大）→ dynamic_score = 0.9

    def __post_init__(self):
        """计算衍生属性"""
        if not self.board:
            return

        # 自动判断street
        self.street = self._determine_street()

        # 自动计算texture
        self._analyze_texture()

    def _determine_street(self) -> str:
        board_size = len(self.board)
        if board_size == 3:
            return 'flop'
        elif board_size == 4:
            return 'turn'
        elif board_size == 5:
            return 'river'
        return 'unknown'

    def _analyze_texture(self):
        """分析board texture（简化版，完整实现在BoardAnalyzer中）"""
        # 这里只做基础判断，详细分析由BoardAnalyzer完成
        board_size = len(self.board)

        # 判断是否paired
        if board_size >= 3:
            ranks = [card.rank for card in self.board]
            self.is_paired = len(ranks) != len(set(ranks))

        # 判断花色
        if board_size >= 3:
            suits = [card.suit for card in self.board]
            suit_counts = {}
            for suit in suits:
                suit_counts[suit] = suit_counts.get(suit, 0) + 1
            max_suit_count = max(suit_counts.values())

            self.is_monotone = (max_suit_count >= 3)
            self.is_two_tone = (max_suit_count == 2 and len(suit_counts) == 2)
            self.is_rainbow = (len(suit_counts) == board_size)


# ============================================================================
# Decision Integration数据结构
# ============================================================================

@dataclass
class DecisionTrace:
    """
    完整的决策追踪（用于调试和验证）

    这是确保"代码不被架空"的关键：
    - 记录每个模块的输入输出
    - 记录性能指标
    - 支持可视化决策树

    使用场景：
    1. 调试：为什么AI做了这个决策？
    2. 验证：equity_info被计算了但在key_factors中吗？
    3. 性能优化：哪个模块最慢？
    4. A/B测试：对比不同策略的决策差异
    """
    # Trace标识
    trace_id: str
    timestamp: float

    # 输入
    game_state: Any  # GameState对象（为避免循环导入，用Any）

    # Analysis Layer输出
    hero_range: Optional[Range] = None
    villain_range: Optional[Range] = None
    equity_info: Optional[EquityInfo] = None
    range_advantage: Optional[RangeAdvantage] = None
    board_analysis: Optional[BoardAnalysis] = None

    # Strategy Layer输出
    gto_decision: Optional[StrategyDecision] = None  # GTO基准决策
    exploit_decision: Optional[StrategyDecision] = None  # Exploit调整后
    final_decision: StrategyDecision = None  # 最终决策

    # 最终选择的action
    selected_action: Optional[Action] = None

    # 性能指标
    analysis_time_ms: float = 0.0
    strategy_time_ms: float = 0.0
    total_time_ms: float = 0.0

    # 额外元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """转换为字典（用于序列化）"""
        return {
            'trace_id': self.trace_id,
            'timestamp': self.timestamp,
            'street': self.game_state.street if self.game_state else None,
            'position': str(self.game_state.position) if self.game_state else None,
            'final_decision': {
                'action_distribution': self.final_decision.action_distribution,
                'reasoning': self.final_decision.reasoning,
                'confidence': self.final_decision.confidence,
                'key_factors': self.final_decision.key_factors
            } if self.final_decision else None,
            'selected_action': {
                'action': self.selected_action.action,
                'amount': self.selected_action.amount
            } if self.selected_action else None,
            'performance': {
                'analysis_time_ms': self.analysis_time_ms,
                'strategy_time_ms': self.strategy_time_ms,
                'total_time_ms': self.total_time_ms
            }
        }

    def verify_module_usage(self) -> Dict[str, bool]:
        """
        验证每个模块是否被正确使用

        返回：{'range_engine': True, 'equity_engine': False, ...}
        如果某个模块被计算但未在key_factors中出现，返回False
        """
        key_factors = self.final_decision.key_factors if self.final_decision else {}

        return {
            'range_engine': (
                self.hero_range is not None and
                self.villain_range is not None and
                ('range_percentile' in key_factors or 'range_advantage' in key_factors)
            ),
            'equity_engine': (
                self.equity_info is not None and
                'equity' in key_factors
            ),
            'range_advantage_analyzer': (
                self.range_advantage is not None and
                'range_advantage' in key_factors
            ),
            'board_analyzer': (
                self.board_analysis is not None and
                ('board_texture' in key_factors or 'board_favors' in key_factors)
            )
        }


# ============================================================================
# Model Layer数据结构
# ============================================================================

class PlayerType(Enum):
    """玩家类型分类"""
    UNKNOWN = "unknown"
    LAG = "lag"  # Loose Aggressive
    TAG = "tag"  # Tight Aggressive
    LOOSE_PASSIVE = "loose_passive"
    TIGHT_PASSIVE = "tight_passive"
    NORMAL = "normal"
    MANIAC = "maniac"
    NIT = "nit"


@dataclass
class PlayerProfile:
    """
    玩家画像

    基于观察到的行动构建的对手模型。
    用于：
    1. Range估计（不同类型玩家的range不同）
    2. Exploit调整（针对性策略）
    3. GTO-Exploit平衡（根据可靠性决定exploit程度）
    """
    player_id: str
    player_type: PlayerType = PlayerType.UNKNOWN

    # 基础统计（最重要的3个）
    vpip: float = 0.25  # Voluntarily Put money In Pot
    pfr: float = 0.18   # PreFlop Raise
    af: float = 1.5     # Aggression Factor = (bet + raise) / call

    # 其他统计
    wtsd: float = 0.25  # Went To ShowDown
    w_sd: float = 0.50  # Won at ShowDown

    # 位置统计（Phase 2实现）
    stats_by_position: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # 翻后趋势
    cbet_freq_flop: float = 0.50
    cbet_freq_turn: float = 0.40
    cbet_freq_river: float = 0.35
    fold_to_cbet_flop: float = 0.50
    fold_to_cbet_turn: float = 0.55
    fold_to_cbet_river: float = 0.60

    # 翻前趋势
    three_bet_freq: float = 0.08
    fold_to_3bet: float = 0.60
    four_bet_freq: float = 0.02

    # 样本量（关键！影响可靠性）
    sample_size: int = 0
    hands_observed: int = 0
    actions_observed: int = 0

    # 可靠性（基于样本量计算）
    confidence: float = 0.0

    def __post_init__(self):
        """计算置信度"""
        self.confidence = self._calculate_confidence()

    def _calculate_confidence(self) -> float:
        """
        基于样本量计算置信度

        样本量越大，越可靠：
        - 0-10 hands: confidence = 0.0-0.2（不可靠）
        - 10-50 hands: confidence = 0.2-0.6（部分可靠）
        - 50-100 hands: confidence = 0.6-0.8（可靠）
        - 100+ hands: confidence = 0.8-0.95（非常可靠）
        """
        if self.hands_observed < 10:
            return self.hands_observed / 50.0  # 0-0.2
        elif self.hands_observed < 50:
            return 0.2 + (self.hands_observed - 10) / 100.0  # 0.2-0.6
        elif self.hands_observed < 100:
            return 0.6 + (self.hands_observed - 50) / 250.0  # 0.6-0.8
        else:
            return min(0.95, 0.8 + (self.hands_observed - 100) / 1000.0)  # 0.8-0.95

    def is_reliable(self) -> bool:
        """判断profile是否可靠（用于决定是否exploit）"""
        return self.confidence >= 0.6


# ============================================================================
# Exploit Layer数据结构
# ============================================================================

@dataclass
class ExploitAdjustment:
    """
    Exploit调整

    基于对手tendencies计算的GTO调整。
    例如：vs PASSIVE对手 → 增加value bet频率，减少bluff频率
    """
    # 调整项（相对于GTO的调整）
    adjustments: Dict[str, float] = field(default_factory=dict)
    # {
    #   'value_bet_freq': +0.15,  # 增加15%的value bet频率
    #   'bluff_freq': -0.10,       # 减少10%的bluff频率
    #   'thin_value': +0.10,       # 扩大10%的thin value range
    #   'defense_freq': -0.05      # 减少5%的防守频率
    # }

    # 元数据
    reasoning: str = ""
    confidence: float = 0.0  # 基于对手profile的可靠性
    exploit_weight: float = 0.0  # 应用exploit的权重（0-1）

    def apply_to_frequencies(self, base_freq: Dict[str, float]) -> Dict[str, float]:
        """将调整应用到action频率"""
        adjusted = base_freq.copy()

        for key, adjustment in self.adjustments.items():
            if key in adjusted:
                adjusted[key] = max(0.0, min(1.0, adjusted[key] + adjustment * self.exploit_weight))

        # 归一化
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}

        return adjusted
