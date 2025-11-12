"""
GTO基线策略 (GTO Baseline Strategy)

提供简化的GTO近似策略，包括：
1. 翻前GTO查找表
2. 翻后GTO公式（MDF、Bluff频率、Equity门槛）
3. 动态权重系统
4. 多人底池调整

基于GTO原则的启发式规则，不使用CFR求解器。
"""
from typing import Dict, Optional, Tuple, List
from enum import Enum
from dataclasses import dataclass


class Street(Enum):
    """街道枚举"""
    PREFLOP = 'preflop'
    FLOP = 'flop'
    TURN = 'turn'
    RIVER = 'river'


class Position(Enum):
    """位置枚举"""
    UTG = 'UTG'
    MP = 'MP'
    CO = 'CO'
    BTN = 'BTN'
    SB = 'SB'
    BB = 'BB'


@dataclass
class GTOContext:
    """GTO决策上下文"""
    street: Street
    position: Position
    is_in_position: bool

    # 范围信息
    equity: float
    range_advantage: str  # 'strong'/'medium'/'weak'

    # 底池信息
    pot_size: float
    effective_stack: float
    spr: float  # Stack-to-Pot Ratio

    # 对手信息
    num_opponents: int
    facing_bet: Optional[float] = None
    bet_to_call: Optional[float] = None

    # 公共牌信息
    board_texture: Optional[str] = None  # 'dry'/'medium'/'wet'


class GTOBaseline:
    """GTO基线策略引擎"""

    def __init__(self):
        """初始化GTO基线"""
        pass

    # ===== 翻前GTO =====

    def preflop_strategy(self,
                        position: Position,
                        hand_strength: float,
                        action_history: List[str],
                        effective_stack: float,
                        equity: float = None,
                        opponent_type: str = None) -> Dict[str, float]:
        """
        翻前GTO策略

        Args:
            position: 位置
            hand_strength: 手牌强度 (0.0-1.0)
            action_history: 行动历史 ['open', '3bet', ...]
            effective_stack: 有效筹码 (BB)
            equity: vs对手范围的equity (可选)
            opponent_type: 对手类型 (可选)

        Returns:
            动作概率分布
        """
        # 未面对下注：开池或弃牌
        if not action_history or action_history[-1] in ['fold', 'check']:
            return self._preflop_open_strategy(position, hand_strength)

        # 面对open raise
        if action_history[-1] == 'open':
            return self._preflop_vs_open(position, hand_strength, effective_stack)

        # 面对3-bet
        if action_history[-1] == '3bet':
            return self._preflop_vs_3bet(position, hand_strength, effective_stack,
                                         equity=equity, opponent_type=opponent_type)

        # 面对4-bet
        if action_history[-1] == '4bet':
            return self._preflop_vs_4bet(hand_strength, effective_stack)

        # 面对limp (call)
        if action_history[-1] == 'call':
            return self._preflop_vs_limp(position, hand_strength, effective_stack)

        # 默认：保守策略
        return {'fold': 0.8, 'call': 0.2}

    def _preflop_open_strategy(self, position: Position, strength: float) -> Dict[str, float]:
        """
        开池策略（包含limp逻辑）

        根据hand strength和位置决定：
        1. Raise (open) - 强牌
        2. Call (limp) - 中等牌，基于pot odds合理
        3. Fold - 弱牌
        """
        # Raise阈值 - 位置越好，开池范围越宽
        # Phase 1 Fix: 扩大BTN/CO开池范围，符合GTO标准
        raise_thresholds = {
            Position.UTG: 0.75,  # 只开最好的25%
            Position.MP: 0.70,   # 开30%
            Position.CO: 0.40,   # 开60% (修复：0.65→0.40)
            Position.BTN: 0.25,  # 开75% (修复：0.50→0.25) - GTO标准
            Position.SB: 0.50,   # 开50%
            Position.BB: 1.0,    # BB已经投入，不用开池
        }

        # Limp阈值 - 修复Bug #2: BTN/CO/UTG/MP取消limp，SB收紧
        # 现代GTO：BTN/CO要么raise要么fold，不limp
        # 设置limp_threshold = raise_threshold即可取消limp
        limp_thresholds = {
            Position.UTG: 0.75,  # = raise threshold，取消limp
            Position.MP: 0.70,   # = raise threshold，取消limp
            Position.CO: 0.40,   # = raise threshold，取消limp (修复：0.65→0.40)
            Position.BTN: 0.25,  # = raise threshold，取消limp (修复：0.50→0.25)
            Position.SB: 0.50,   # 收紧limp范围（修复：0.40→0.50）
            Position.BB: 0.30,   # BB保留（免费看flop）
        }

        raise_threshold = raise_thresholds.get(position, 0.70)
        limp_threshold = limp_thresholds.get(position, 0.50)

        if strength >= raise_threshold:
            # 强牌：raise (open)
            return {'fold': 0.0, 'call': 0.0, 'raise': 1.0}
        elif strength >= limp_threshold:
            # 中等牌：主要limp，少量raise作为bluff/balance
            # BTN和SB位置可以更多limp（因为有位置或pot odds优势）
            if position in [Position.BTN, Position.SB]:
                return {'fold': 0.0, 'call': 0.85, 'raise': 0.15}
            else:
                # EP/MP位置limp风险较高（容易被squeeze），所以部分fold
                return {'fold': 0.2, 'call': 0.70, 'raise': 0.10}
        else:
            # 弱牌：fold
            return {'fold': 1.0}

    def _preflop_vs_open(self, position: Position, strength: float, stack: float) -> Dict[str, float]:
        """面对open的策略"""
        # 3-bet门槛
        three_bet_threshold = 0.85

        # 跟注门槛（考虑位置）
        call_threshold = 0.65 if position in [Position.BTN, Position.BB] else 0.70

        if strength >= three_bet_threshold:
            # 强牌：3-bet
            return {'fold': 0.0, 'call': 0.2, '3bet': 0.8}
        elif strength >= call_threshold:
            # 中等牌：主要跟注，少量3-bet bluff
            return {'fold': 0.0, 'call': 0.85, '3bet': 0.15}
        elif strength >= 0.55:
            # 边缘牌：主要弃牌，少量跟注
            return {'fold': 0.7, 'call': 0.3}
        else:
            # 弱牌：弃牌
            return {'fold': 1.0}

    def _preflop_vs_3bet(self, position: Position, strength: float, stack: float,
                        equity: float = None, opponent_type: str = None) -> Dict[str, float]:
        """
        面对3-bet的策略

        优先使用equity，其次使用strength
        根据对手类型调整（LAG的3-bet范围宽，我们defend wider）
        """
        # ✅ 优先使用equity决策
        if equity is not None and equity > 0:
            # Equity-based决策（更准确）
            # 典型pot odds vs 3-bet约为42-45%

            if equity >= 0.65:  # 明显优势
                return {'fold': 0.0, 'call': 0.4, '4bet': 0.6}
            elif equity >= 0.55:  # 中等优势
                return {'fold': 0.0, 'call': 0.75, '4bet': 0.25}
            elif equity >= 0.48:  # 略有优势，超过pot odds
                return {'fold': 0.0, 'call': 0.90, '4bet': 0.10}
            elif equity >= 0.42:  # 接近pot odds (可以call)
                return {'fold': 0.15, 'call': 0.80, '4bet': 0.05}
            elif equity >= 0.35:  # 略低于pot odds
                return {'fold': 0.60, 'call': 0.35, '4bet': 0.05}
            else:  # 明显弱牌
                return {'fold': 0.95, 'call': 0.05}

        # ✅ 如果没有equity，使用strength（改进的阈值）
        # 根据对手类型调整
        if opponent_type == 'LAG' or opponent_type == 'MANIAC':
            # vs LAG：他们3-bet范围宽，我们defend wider
            four_bet_threshold = 0.88
            call_threshold = 0.70
        elif opponent_type == 'NIT' or opponent_type == 'WEAK_TIGHT':
            # vs Nit：他们3-bet范围紧，我们defend tighter
            four_bet_threshold = 0.94
            call_threshold = 0.80
        else:
            # 默认 vs TAG/UNKNOWN
            four_bet_threshold = 0.90
            call_threshold = 0.75

        if strength >= four_bet_threshold:
            # 超强牌：4-bet
            return {'fold': 0.0, 'call': 0.3, '4bet': 0.7}
        elif strength >= call_threshold:
            # 强牌：主要跟注
            return {'fold': 0.0, 'call': 0.90, '4bet': 0.10}
        elif strength >= 0.60:  # ✅ 降低阈值（之前是0.65）
            # 中等牌：少fold，多call
            return {'fold': 0.30, 'call': 0.65, '4bet': 0.05}
        else:
            # 弱牌：弃牌
            return {'fold': 1.0}

    def _preflop_vs_4bet(self, strength: float, stack: float) -> Dict[str, float]:
        """面对4-bet的策略"""
        # 极化策略：只用最强和最弱的牌
        if strength >= 0.95:
            # nuts：全压或跟注
            return {'fold': 0.0, 'call': 0.6, 'allin': 0.4}
        elif strength >= 0.85:
            # 强牌：主要跟注
            return {'fold': 0.2, 'call': 0.8}
        else:
            # 其他：弃牌
            return {'fold': 1.0}

    def _preflop_vs_limp(self, position: Position, strength: float, stack: float) -> Dict[str, float]:
        """
        面对limp (call)的策略

        特别重要：BB位置面对limp时，强牌应该raise进行isolation

        GTO原则：
        1. 强牌(88+, ATs+, AQo+): 100% raise for value + isolation
        2. 中等牌: Check back (免费看flop)
        3. 弱牌: Check back (已投入1BB，pot odds好)
        """
        # BB位置特殊处理
        if position == Position.BB:
            # BB vs limp的raise阈值
            # 88+ = 0.78+, ATs = 0.73, AQo = 0.72
            if strength >= 0.72:
                # 强牌：100% raise进行isolation
                # TT (0.78), KK (0.88), AA (0.95), AK (0.85+), AQ (0.72+)
                return {'fold': 0.0, 'call': 0.0, 'raise': 1.0}
            else:
                # 中等牌/弱牌：check (已投入1BB，pot odds优秀)
                # BB只投入1BB，看flop只需再投0BB（免费）
                # 所以几乎任何牌都应该check
                return {'fold': 0.0, 'call': 1.0, 'raise': 0.0}

        # SB位置面对limp
        elif position == Position.SB:
            # SB需要投0.5BB (pot=2.0BB)，pot odds = 25%
            if strength >= 0.80:
                # 强牌：raise进行isolation
                return {'fold': 0.0, 'call': 0.2, 'raise': 0.8}
            elif strength >= 0.35:
                # 中等牌：主要limp，少量raise
                return {'fold': 0.0, 'call': 0.85, 'raise': 0.15}
            else:
                # 弱牌：部分fold（虽然pot odds好，但位置差）
                return {'fold': 0.6, 'call': 0.4}

        # 其他位置（理论上不会有，因为只有BB/SB在limp后面行动）
        else:
            # 保守策略
            return {'fold': 0.5, 'call': 0.5}

    # ===== 翻后GTO公式 =====

    def postflop_strategy(self, ctx: GTOContext) -> Dict[str, float]:
        """
        翻后GTO策略

        Args:
            ctx: GTO决策上下文

        Returns:
            动作概率分布
        """
        # 面对下注：防守策略
        if ctx.facing_bet:
            return self._defense_strategy(ctx)

        # 未面对下注：主动策略
        else:
            return self._aggression_strategy(ctx)

    def _defense_strategy(self, ctx: GTOContext) -> Dict[str, float]:
        """
        防守策略（面对下注）

        基于MDF (Minimum Defense Frequency) 和 Equity
        """
        # 计算底池赔率和MDF
        pot_odds = self.calculate_pot_odds(ctx.pot_size, ctx.bet_to_call)
        mdf = self.calculate_mdf(ctx.pot_size, ctx.facing_bet)

        # Equity vs 底池赔率
        if ctx.equity >= pot_odds + 0.05:
            # Equity明显好于底池赔率：跟注为主
            fold_freq = max(0.0, 1.0 - mdf - 0.1)
            call_freq = min(0.9, mdf + 0.1)
            raise_freq = 0.1 if ctx.equity > 0.65 else 0.0

        elif ctx.equity >= pot_odds - 0.05:
            # Equity接近底池赔率：混合策略
            fold_freq = 1.0 - mdf
            call_freq = mdf * 0.8
            raise_freq = mdf * 0.2 if ctx.equity > 0.55 else 0.0

        else:
            # Equity差：主要弃牌
            fold_freq = min(1.0, 1.0 - mdf + 0.2)
            call_freq = max(0.0, mdf - 0.2)
            raise_freq = 0.0

        # 位置调整
        if ctx.is_in_position:
            # 有位置：少弃牌，多跟注/加注
            fold_freq *= 0.85
            call_freq += 0.10
            raise_freq += 0.05

        # 归一化
        total = fold_freq + call_freq + raise_freq
        return {
            'fold': fold_freq / total,
            'call': call_freq / total,
            'raise': raise_freq / total
        }

    def _aggression_strategy(self, ctx: GTOContext) -> Dict[str, float]:
        """
        主动策略（未面对下注）

        基于Equity、Range优势、位置

        Phase 1 Fix:
        1. 降低value_threshold: 0.65→0.50 (OOP), 0.55→0.45 (IP)
        2. 移除中等牌硬编码，改用bet_frequency计算
        """
        # 计算下注频率
        bet_frequency = self._calculate_bet_frequency(ctx)

        # 计算bluff频率
        if bet_frequency > 0:
            bluff_freq = self.calculate_optimal_bluff_frequency(ctx.pot_size, ctx.pot_size * 0.66)
        else:
            bluff_freq = 0.0

        # Equity门槛 - Phase 1 Fix: 降低threshold扩大value betting range
        value_threshold = 0.50 - (0.05 if ctx.is_in_position else 0.0)
        # OOP: 0.50 (修复：0.65→0.50), IP: 0.45 (修复：0.55→0.45)

        if ctx.equity >= value_threshold:
            # 强牌：价值下注（增强频率）
            check_freq = 1.0 - bet_frequency
            bet_freq = bet_frequency

        elif ctx.equity >= 0.35:
            # 中等牌：Phase 1 Fix - 移除硬编码，改用动态计算
            # 使用bet_frequency但降低系数（中等牌不如强牌aggressive）
            adjusted_bet_freq = bet_frequency * 0.6
            check_freq = 1.0 - adjusted_bet_freq
            bet_freq = adjusted_bet_freq

        else:
            # 弱牌：主要过牌，少量pure bluff
            check_freq = 1.0 - bluff_freq
            bet_freq = bluff_freq

        return {
            'check': check_freq,
            'bet': bet_freq
        }

    def _calculate_bet_frequency(self, ctx: GTOContext) -> float:
        """
        计算下注频率

        考虑：范围优势、位置、公共牌湿度
        """
        base_freq = 0.5

        # 范围优势调整
        if ctx.range_advantage == 'strong':
            base_freq += 0.2
        elif ctx.range_advantage == 'weak':
            base_freq -= 0.2

        # 位置调整
        if ctx.is_in_position:
            base_freq += 0.1
        else:
            base_freq -= 0.1

        # 公共牌调整
        if ctx.board_texture == 'dry':
            base_freq += 0.1  # 干燥面多下注
        elif ctx.board_texture == 'wet':
            base_freq -= 0.1  # 湿面少下注

        # SPR调整
        if ctx.spr < 3:
            base_freq += 0.15  # 浅筹码多下注
        elif ctx.spr > 10:
            base_freq -= 0.1  # 深筹码少下注

        return max(0.0, min(1.0, base_freq))

    # ===== GTO公式 =====

    @staticmethod
    def calculate_mdf(pot: float, bet: float) -> float:
        """
        计算最小防守频率 (Minimum Defense Frequency)

        MDF = pot / (pot + bet)

        Args:
            pot: 底池大小
            bet: 下注大小

        Returns:
            MDF (0.0-1.0)

        Example:
            >>> calculate_mdf(100, 50)
            0.6666...  # 需要防守67%
        """
        return pot / (pot + bet)

    @staticmethod
    def calculate_pot_odds(pot: float, call_amount: float) -> float:
        """
        计算底池赔率

        Pot Odds = call / (pot + call)

        Args:
            pot: 底池大小
            call_amount: 需要跟注的金额

        Returns:
            所需equity (0.0-1.0)
        """
        return call_amount / (pot + call_amount)

    @staticmethod
    def calculate_optimal_bluff_frequency(pot: float, bet: float) -> float:
        """
        计算最优bluff频率

        Optimal Bluff Freq = risk / (risk + reward)
                            = bet / (bet + pot)

        Args:
            pot: 底池大小
            bet: 下注大小

        Returns:
            Bluff频率 (0.0-1.0)

        Example:
            >>> calculate_optimal_bluff_frequency(100, 50)
            0.333...  # 1/3 bluff, 2/3 value
        """
        return bet / (bet + pot)

    @staticmethod
    def calculate_bet_sizing(ctx: GTOContext) -> float:
        """
        计算推荐下注尺寸（pot的百分比）

        考虑：范围优势、SPR、公共牌湿度

        Args:
            ctx: GTO决策上下文

        Returns:
            下注尺寸占pot的百分比 (0.33-2.0)
        """
        # 基础尺寸
        if ctx.range_advantage == 'strong':
            base_size = 0.75
        elif ctx.range_advantage == 'medium':
            base_size = 0.66
        else:
            base_size = 0.50

        # 公共牌调整
        if ctx.board_texture == 'dry':
            base_size -= 0.10  # 干燥面小注
        elif ctx.board_texture == 'wet':
            base_size += 0.15  # 湿面大注保护

        # SPR调整
        if ctx.spr < 3:
            base_size += 0.25  # 浅筹码大尺寸
        elif ctx.spr > 10:
            base_size -= 0.10  # 深筹码小尺寸

        # 位置调整
        if not ctx.is_in_position:
            base_size += 0.10  # OOP用大尺寸保护

        return max(0.33, min(2.0, base_size))

    # ===== 多人底池调整 =====

    @staticmethod
    def multiway_equity_discount(equity: float, num_opponents: int) -> float:
        """
        多人底池equity打折

        在多人底池中，需要击败所有对手，equity显著降低

        Args:
            equity: 原始equity
            num_opponents: 对手数量

        Returns:
            调整后的equity

        Example:
            >>> multiway_equity_discount(0.83, 1)  # heads-up
            0.83
            >>> multiway_equity_discount(0.83, 2)  # 3-way
            0.70  # 打折~15%
        """
        if num_opponents <= 1:
            return equity

        # 每增加一个对手，打折15%
        discount_per_opp = 0.15
        total_discount = discount_per_opp * (num_opponents - 1)

        return equity * (1.0 - total_discount)

    @staticmethod
    def multiway_bet_frequency_adjustment(base_freq: float, num_opponents: int) -> float:
        """
        多人底池下注频率调整

        多人底池应该减少bluff，增加value bet

        Args:
            base_freq: 基础下注频率
            num_opponents: 对手数量

        Returns:
            调整后的频率
        """
        if num_opponents <= 1:
            return base_freq

        # 减少bluff频率
        bluff_reduction = 0.1 * (num_opponents - 1)

        return max(0.0, base_freq - bluff_reduction)

    # ===== 动态权重系统 =====

    @staticmethod
    def get_decision_weights(ctx: GTOContext) -> Dict[str, float]:
        """
        获取决策因素的动态权重

        根据街道、SPR等情境调整各因素权重

        Args:
            ctx: GTO决策上下文

        Returns:
            权重字典
        """
        if ctx.street == Street.PREFLOP:
            return {
                'position': 0.30,
                'hand_strength': 0.25,
                'opponent_type': 0.20,
                'stack_depth': 0.15,
                'pot_odds': 0.10,
            }

        elif ctx.street == Street.RIVER:
            return {
                'range_advantage': 0.35,
                'pot_odds': 0.25,
                'opponent_type': 0.20,
                'position': 0.10,
                'blockers': 0.10,
            }

        elif ctx.spr < 3:  # 浅筹码
            return {
                'equity': 0.40,
                'pot_odds': 0.30,
                'opponent_type': 0.15,
                'position': 0.10,
                'board_texture': 0.05,
            }

        else:  # 标准情况（翻牌/转牌，中等SPR）
            return {
                'equity': 0.25,
                'range_advantage': 0.20,
                'position': 0.20,
                'opponent_type': 0.15,
                'board_texture': 0.10,
                'spr': 0.10,
            }
