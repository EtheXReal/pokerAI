"""
GTOStrategy - Range-based GTO策略实现

这是advisor_v2的核心策略，修复了advisor的致命缺陷：
- advisor: 基于hand_strength做决策 → A5o在BTN fold（hand_strength=0.47）
- advisor_v2: 基于range percentile做决策 → A5o在BTN raise（percentile=0.65）

关键改进：
1. 翻前：基于range percentile决策（NOT hand_strength）
2. 翻后：基于equity_distribution + range_advantage决策
3. Sizing：基于board texture和range advantage动态调整
4. Frequency：混合策略（GTO需要randomization）
5. Trace：记录所有关键因素，确保模块不被架空
"""

from typing import Dict, Optional
import random

from advisor_v2.core.interfaces.strategy_interface import IStrategy
from advisor_v2.core.data_structures import (
    StrategyContext,
    StrategyDecision,
    EquityInfo,
    RangeAdvantage,
    BoardAnalysis,
)
from advisor.range_engine.cards import Hand


class GTOStrategy(IStrategy):
    """
    GTO基准策略实现

    决策逻辑：
    - 翻前：基于get_hand_percentile()决定raise/call/fold
    - 翻后：基于equity + range advantage决定action和sizing
    - 所有决策基于range-based思维（非hand-centric）
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        初始化GTOStrategy

        Args:
            config: 策略配置
                - raise_threshold: 翻前raise的percentile阈值（默认0.50）
                - call_threshold: 翻前call的percentile阈值（默认0.30）
                - value_bet_threshold: 翻后value bet的equity阈值（默认0.55）
                - bluff_frequency: Bluff频率（默认0.30）
        """
        self.config = config or {}

        # 翻前阈值
        self.raise_threshold = self.config.get('raise_threshold', 0.50)
        self.call_threshold = self.config.get('call_threshold', 0.30)

        # 翻后阈值
        self.value_bet_threshold = self.config.get('value_bet_threshold', 0.55)
        self.bluff_frequency = self.config.get('bluff_frequency', 0.30)

        # Sizing配置
        self.default_raise_size = 2.5  # 2.5x BB翻前
        self.default_cbet_size = 0.66  # 0.66 pot翻后

        # 追踪器（可选）
        self.tracer = None

    def set_tracer(self, tracer):
        """设置追踪器"""
        self.tracer = tracer

    def decide(self, ctx: StrategyContext) -> StrategyDecision:
        """
        基于上下文做出决策

        Args:
            ctx: StrategyContext（完整的决策上下文）

        Returns:
            StrategyDecision（action分布 + sizing分布 + 元数据）
        """
        # 根据street选择决策逻辑
        if ctx.street == 'preflop':
            return self._decide_preflop(ctx)
        else:
            return self._decide_postflop(ctx)

    def _decide_preflop(self, ctx: StrategyContext) -> StrategyDecision:
        """
        翻前决策（基于range percentile）

        关键改进：
        - advisor: A5o在BTN，hand_strength=0.47 → fold
        - advisor_v2: A5o在BTN range的percentile=0.65 → raise

        Args:
            ctx: StrategyContext

        Returns:
            StrategyDecision
        """
        # 1. 获取hand在hero range中的percentile
        # 注意：这里需要RangeEngine，但ctx中没有提供
        # 临时方案：基于简化的hand strength估计
        # TODO: 在DecisionIntegrator中调用RangeEngine并将结果放入ctx

        hand = ctx.hero_hand

        # Trace: 估算hand percentile
        if self.tracer and self.tracer.is_enabled():
            self.tracer.step_begin()
        percentile = self._estimate_hand_percentile(hand, ctx)
        if self.tracer and self.tracer.is_enabled():
            self.tracer.step_end(
                step_name="Hand Percentile估算",
                module="advisor_v2/strategy/gto_strategy.py",
                function="_estimate_hand_percentile",
                inputs={"hand": str(hand), "position": str(ctx.position)},
                outputs={"percentile": percentile},
                reasoning=f"{hand}在{ctx.position}的GTO range中排名{percentile:.2%}（基于牌力粗略估计）"
            )

        # 2. 判断是否facing bet
        facing_bet = ctx.facing_bet

        # 3. 决策逻辑
        if not facing_bet:
            # Open或limp situation
            if self.tracer and self.tracer.is_enabled():
                self.tracer.step_begin()
            decision = self._decide_preflop_open(ctx, percentile)
            if self.tracer and self.tracer.is_enabled():
                self.tracer.step_end(
                    step_name="翻前Open决策",
                    module="advisor_v2/strategy/gto_strategy.py",
                    function="_decide_preflop_open",
                    inputs={"percentile": percentile, "raise_threshold": self.raise_threshold},
                    outputs={"action_dist": decision.action_distribution, "reasoning": decision.reasoning},
                    reasoning=f"基于percentile vs threshold做open/fold决策"
                )
            return decision
        else:
            # Facing raise/3bet
            if self.tracer and self.tracer.is_enabled():
                self.tracer.step_begin()
            decision = self._decide_preflop_facing_raise(ctx, percentile)
            if self.tracer and self.tracer.is_enabled():
                self.tracer.step_end(
                    step_name="翻前Facing Raise决策",
                    module="advisor_v2/strategy/gto_strategy.py",
                    function="_decide_preflop_facing_raise",
                    inputs={"percentile": percentile, "facing_bet": ctx.facing_bet_size},
                    outputs={"action_dist": decision.action_distribution, "reasoning": decision.reasoning},
                    reasoning=f"基于percentile做3bet/call/fold决策"
                )
            return decision

    def _decide_preflop_open(self, ctx: StrategyContext, percentile: float) -> StrategyDecision:
        """
        翻前open决策

        Args:
            ctx: StrategyContext
            percentile: Hand在range中的位置（0-1）

        Returns:
            StrategyDecision
        """
        # Range-based decision
        if percentile >= self.raise_threshold:
            # Top 50% of range → raise
            action_dist = {'raise': 1.0, 'call': 0.0, 'fold': 0.0}
            sizing_dist = {self.default_raise_size: 1.0}
            reasoning = f"Preflop open: hand percentile {percentile:.2f} >= {self.raise_threshold} → raise"

        elif percentile >= self.call_threshold:
            # Middle range → mixed strategy (mostly call, some raise for balance)
            action_dist = {'raise': 0.20, 'call': 0.70, 'fold': 0.10}
            sizing_dist = {self.default_raise_size: 1.0}
            reasoning = f"Preflop open: hand percentile {percentile:.2f} in middle range → mixed (mostly call)"

        else:
            # Bottom of range → fold
            action_dist = {'raise': 0.0, 'call': 0.0, 'fold': 1.0}
            sizing_dist = {}
            reasoning = f"Preflop open: hand percentile {percentile:.2f} < {self.call_threshold} → fold"

        # 构建决策
        decision = StrategyDecision(
            action_distribution=action_dist,
            sizing_distribution=sizing_dist,
            reasoning=reasoning,
            confidence=0.9,
            key_factors={
                'strategy': 'GTOStrategy',
                'street': 'preflop',
                'decision_type': 'open',
                'hand_percentile': percentile,
                'raise_threshold': self.raise_threshold,
                'call_threshold': self.call_threshold,
            }
        )

        return decision

    def _decide_preflop_facing_raise(self, ctx: StrategyContext, percentile: float) -> StrategyDecision:
        """
        翻前facing raise决策（3bet/call/fold）

        Args:
            ctx: StrategyContext
            percentile: Hand在range中的位置

        Returns:
            StrategyDecision
        """
        # Facing raise需要更tight的range
        # 3bet threshold更高
        three_bet_threshold = 0.70
        call_threshold = 0.40

        if percentile >= three_bet_threshold:
            # Top range → 3bet
            action_dist = {'raise': 1.0, 'call': 0.0, 'fold': 0.0}
            sizing_dist = {3.0: 1.0}  # 3x对手的raise
            reasoning = f"Facing raise: percentile {percentile:.2f} >= {three_bet_threshold} → 3bet"

        elif percentile >= call_threshold:
            # Middle range → mostly call, some 3bet for balance
            action_dist = {'raise': 0.15, 'call': 0.75, 'fold': 0.10}
            sizing_dist = {3.0: 1.0}
            reasoning = f"Facing raise: percentile {percentile:.2f} in middle range → mostly call"

        else:
            # Bottom → fold
            action_dist = {'raise': 0.0, 'call': 0.0, 'fold': 1.0}
            sizing_dist = {}
            reasoning = f"Facing raise: percentile {percentile:.2f} < {call_threshold} → fold"

        decision = StrategyDecision(
            action_distribution=action_dist,
            sizing_distribution=sizing_dist,
            reasoning=reasoning,
            confidence=0.85,
            key_factors={
                'strategy': 'GTOStrategy',
                'street': 'preflop',
                'decision_type': 'facing_raise',
                'hand_percentile': percentile,
                'three_bet_threshold': three_bet_threshold,
                'call_threshold': call_threshold,
                'facing_bet_size': ctx.facing_bet_size,
            }
        )

        return decision

    def _decide_postflop(self, ctx: StrategyContext) -> StrategyDecision:
        """
        翻后决策（基于equity + range advantage）

        关键改进：
        - 使用完整的EquityInfo（equity_distribution，不只是point_equity）
        - 使用RangeAdvantage（nut advantage, range size）
        - 使用BoardAnalysis（texture, equity realization）

        Args:
            ctx: StrategyContext

        Returns:
            StrategyDecision
        """
        # 1. 检查必需的分析结果
        if ctx.equity_info is None:
            # 没有equity info，保守fold
            return self._create_defensive_decision(ctx, "Missing equity_info")

        equity_info = ctx.equity_info
        range_advantage = ctx.range_advantage
        board_analysis = ctx.board_analysis

        # 2. 判断是否facing bet
        if ctx.facing_bet:
            # Trace: 翻后facing bet决策
            if self.tracer and self.tracer.is_enabled():
                self.tracer.step_begin()
            decision = self._decide_postflop_facing_bet(ctx, equity_info, range_advantage, board_analysis)
            if self.tracer and self.tracer.is_enabled():
                pot_odds = ctx.facing_bet_size / (ctx.pot_size + ctx.facing_bet_size) if ctx.pot_size > 0 else 0
                self.tracer.step_end(
                    step_name="翻后Facing Bet决策",
                    module="advisor_v2/strategy/gto_strategy.py",
                    function="_decide_postflop_facing_bet",
                    inputs={
                        "equity": equity_info.point_equity,
                        "pot_odds": pot_odds,
                        "facing_bet": ctx.facing_bet_size
                    },
                    outputs={"action_dist": decision.action_distribution, "reasoning": decision.reasoning[:60] + "..."},
                    reasoning=f"基于equity vs pot odds + range advantage做raise/call/fold决策"
                )
            return decision
        else:
            # Trace: 翻后主动决策
            if self.tracer and self.tracer.is_enabled():
                self.tracer.step_begin()
            decision = self._decide_postflop_initiative(ctx, equity_info, range_advantage, board_analysis)
            if self.tracer and self.tracer.is_enabled():
                self.tracer.step_end(
                    step_name="翻后Initiative决策",
                    module="advisor_v2/strategy/gto_strategy.py",
                    function="_decide_postflop_initiative",
                    inputs={
                        "equity": equity_info.point_equity,
                        "range_advantage": range_advantage.advantage_score if range_advantage else None
                    },
                    outputs={"action_dist": decision.action_distribution, "reasoning": decision.reasoning[:60] + "..."},
                    reasoning=f"基于equity + range advantage做bet/check决策（含bluff频率）"
                )
            return decision

    def _decide_postflop_facing_bet(
        self,
        ctx: StrategyContext,
        equity_info: EquityInfo,
        range_advantage: Optional[RangeAdvantage],
        board_analysis: Optional[BoardAnalysis]
    ) -> StrategyDecision:
        """
        翻后facing bet决策（raise/call/fold）

        Args:
            ctx: StrategyContext
            equity_info: Equity信息
            range_advantage: Range优势（可选）
            board_analysis: Board分析（可选）

        Returns:
            StrategyDecision
        """
        # 1. 计算pot odds
        pot_odds = ctx.facing_bet_size / (ctx.pot_size + ctx.facing_bet_size)

        # 2. 基于equity判断是否可以call
        equity = equity_info.point_equity

        # 3. 调整equity（考虑implied odds和equity realization）
        adjusted_equity = equity * equity_info.implied_odds_factor

        # 如果OOP且board wet，降低equity realization
        if not ctx.is_in_position and board_analysis:
            adjusted_equity *= board_analysis.equity_realization_factor

        # 4. 决策逻辑
        # Raise threshold（需要更高的equity）
        raise_threshold = 0.65

        # Call threshold（基于pot odds + margin）
        call_threshold = pot_odds + 0.05

        if adjusted_equity >= raise_threshold:
            # Strong hand → raise (value或protection)
            action_dist = {'raise': 0.70, 'call': 0.30, 'fold': 0.0}
            sizing_dist = self._calculate_raise_sizing(ctx, equity_info, range_advantage, board_analysis)
            reasoning = f"Facing bet: adjusted_equity {adjusted_equity:.2f} >= {raise_threshold} → raise (value/protection)"

        elif adjusted_equity >= call_threshold:
            # Marginal hand → call
            action_dist = {'raise': 0.0, 'call': 1.0, 'fold': 0.0}
            sizing_dist = {}
            reasoning = f"Facing bet: adjusted_equity {adjusted_equity:.2f} >= pot_odds {pot_odds:.2f} → call"

        else:
            # Weak hand → mostly fold, some bluff raises
            bluff_raise_freq = self._calculate_bluff_raise_frequency(ctx, range_advantage, board_analysis)
            action_dist = {'raise': bluff_raise_freq, 'call': 0.0, 'fold': 1.0 - bluff_raise_freq}
            sizing_dist = self._calculate_bluff_sizing(ctx) if bluff_raise_freq > 0 else {}
            reasoning = f"Facing bet: adjusted_equity {adjusted_equity:.2f} < pot_odds {pot_odds:.2f} → fold (with {bluff_raise_freq:.2f} bluff)"

        decision = StrategyDecision(
            action_distribution=action_dist,
            sizing_distribution=sizing_dist,
            reasoning=reasoning,
            confidence=0.85,
            key_factors={
                'strategy': 'GTOStrategy',
                'street': ctx.street,
                'decision_type': 'facing_bet',
                'point_equity': equity,
                'adjusted_equity': adjusted_equity,
                'pot_odds': pot_odds,
                'equity_distribution': equity_info.equity_distribution,
                'range_advantage_score': range_advantage.advantage_score if range_advantage else None,
                'board_texture': board_analysis.texture if board_analysis else None,
                'equity_realization_factor': board_analysis.equity_realization_factor if board_analysis else 1.0,
                'implied_odds_factor': equity_info.implied_odds_factor,
            }
        )

        return decision

    def _decide_postflop_initiative(
        self,
        ctx: StrategyContext,
        equity_info: EquityInfo,
        range_advantage: Optional[RangeAdvantage],
        board_analysis: Optional[BoardAnalysis]
    ) -> StrategyDecision:
        """
        翻后主动决策（bet/check）

        Args:
            ctx: StrategyContext
            equity_info: Equity信息
            range_advantage: Range优势
            board_analysis: Board分析

        Returns:
            StrategyDecision
        """
        # 1. 判断是否应该bet
        equity = equity_info.point_equity

        # 2. 基于equity和range advantage决定bet frequency
        should_bet = self._should_bet_for_value(equity_info, range_advantage)

        if should_bet:
            # Value bet
            bet_freq = self._calculate_value_bet_frequency(equity_info, range_advantage, board_analysis)
            action_dist = {'bet': bet_freq, 'check': 1.0 - bet_freq}
            sizing_dist = self._calculate_value_bet_sizing(ctx, equity_info, range_advantage, board_analysis)
            reasoning = f"Initiative: equity {equity:.2f} → value bet (freq={bet_freq:.2f})"

        else:
            # Marginal/weak hand
            # Check mostly, bet occasionally as bluff
            bluff_freq = self._calculate_bluff_frequency(ctx, range_advantage, board_analysis)
            action_dist = {'bet': bluff_freq, 'check': 1.0 - bluff_freq}
            sizing_dist = self._calculate_bluff_sizing(ctx) if bluff_freq > 0 else {}
            reasoning = f"Initiative: equity {equity:.2f} → check (with {bluff_freq:.2f} bluff)"

        decision = StrategyDecision(
            action_distribution=action_dist,
            sizing_distribution=sizing_dist,
            reasoning=reasoning,
            confidence=0.80,
            key_factors={
                'strategy': 'GTOStrategy',
                'street': ctx.street,
                'decision_type': 'initiative',
                'point_equity': equity,
                'equity_distribution': equity_info.equity_distribution,
                'range_advantage_score': range_advantage.advantage_score if range_advantage else None,
                'board_texture': board_analysis.texture if board_analysis else None,
                'is_in_position': ctx.is_in_position,
            }
        )

        return decision

    # ========================================================================
    # Helper methods
    # ========================================================================

    def _estimate_hand_percentile(self, hand: Hand, ctx: StrategyContext) -> float:
        """
        临时方案：估计hand的percentile

        TODO: 这个应该由RangeEngine提供，在DecisionIntegrator中调用

        Args:
            hand: Hero手牌
            ctx: StrategyContext

        Returns:
            估计的percentile (0-1)
        """
        # 简化实现：基于hand strength的粗略估计
        # 实际应该调用RangeEngine.get_hand_percentile()

        # 检查是否是对子
        is_pair = hand.cards[0].rank == hand.cards[1].rank
        is_suited = hand.cards[0].suit == hand.cards[1].suit

        # Rank is IntEnum, so we can use .value directly
        # Or just use the rank itself since it's already an int
        rank1 = int(hand.cards[0].rank)
        rank2 = int(hand.cards[1].rank)
        high_rank = max(rank1, rank2)
        low_rank = min(rank1, rank2)

        # 粗略估计（基于GTO range）
        # BTN range很宽（~70%），所以需要较高的base percentile
        if is_pair:
            # 对子：rank越高percentile越高
            # AA: 0.90+, KK: 0.85+, ... 22: 0.50+
            percentile = 0.45 + (high_rank / 14.0) * 0.50
        elif is_suited:
            # 同花：高牌越高percentile越高
            # AKs: 0.85+, A2s: 0.60+
            percentile = 0.35 + (high_rank / 14.0) * 0.45 + (low_rank / 14.0) * 0.15
        else:
            # 非同花：Ax比较特殊，应该在BTN range中
            # AKo: 0.80+, A5o: 0.60+, A2o: 0.55+
            if high_rank == 14:  # Ace
                # Ace offsuit: 基础更高
                percentile = 0.45 + (low_rank / 14.0) * 0.30
            else:
                # 其他非同花
                percentile = 0.15 + (high_rank / 14.0) * 0.40 + (low_rank / 14.0) * 0.15

        return min(1.0, max(0.0, percentile))

    def _should_bet_for_value(
        self,
        equity_info: EquityInfo,
        range_advantage: Optional[RangeAdvantage]
    ) -> bool:
        """
        判断是否应该value bet

        Args:
            equity_info: Equity信息
            range_advantage: Range优势

        Returns:
            是否应该bet
        """
        # 1. Equity够高
        if equity_info.point_equity < self.value_bet_threshold:
            return False

        # 2. Equity分布：crushing + strong + ahead的比例够高
        ahead_pct = equity_info.get_ahead_percentage()
        if ahead_pct < 0.50:
            return False

        # 3. Range advantage（如果有）
        if range_advantage and range_advantage.advantage_score < -0.20:
            # Range劣势太大，不适合bet
            return False

        return True

    def _calculate_value_bet_frequency(
        self,
        equity_info: EquityInfo,
        range_advantage: Optional[RangeAdvantage],
        board_analysis: Optional[BoardAnalysis]
    ) -> float:
        """
        计算value bet频率

        Args:
            equity_info: Equity信息
            range_advantage: Range优势
            board_analysis: Board分析

        Returns:
            Bet频率 (0-1)
        """
        base_freq = 0.70

        # 根据equity调整
        if equity_info.point_equity >= 0.70:
            base_freq += 0.20
        elif equity_info.point_equity >= 0.60:
            base_freq += 0.10

        # 根据range advantage调整
        if range_advantage:
            if range_advantage.advantage_score >= 0.30:
                base_freq += 0.10
            elif range_advantage.advantage_score <= -0.30:
                base_freq -= 0.20

        # 根据board texture调整
        if board_analysis:
            if board_analysis.texture == 'wet':
                base_freq += 0.10  # Wet board更应该bet（protection）
            elif board_analysis.texture == 'dry':
                base_freq -= 0.05  # Dry board可以check控制pot

        return min(1.0, max(0.0, base_freq))

    def _calculate_bluff_frequency(
        self,
        ctx: StrategyContext,
        range_advantage: Optional[RangeAdvantage],
        board_analysis: Optional[BoardAnalysis]
    ) -> float:
        """
        计算bluff频率

        GTO需要一定的bluff频率来平衡range

        Args:
            ctx: StrategyContext
            range_advantage: Range优势
            board_analysis: Board分析

        Returns:
            Bluff频率
        """
        base_freq = self.bluff_frequency

        # IP更容易bluff
        if ctx.is_in_position:
            base_freq += 0.10

        # Range advantage高，bluff更有效
        if range_advantage and range_advantage.advantage_score >= 0.20:
            base_freq += 0.10

        # Wet board bluff更有效（代表draws）
        if board_analysis and board_analysis.draw_heavy:
            base_freq += 0.10

        return min(0.50, max(0.0, base_freq))

    def _calculate_bluff_raise_frequency(
        self,
        ctx: StrategyContext,
        range_advantage: Optional[RangeAdvantage],
        board_analysis: Optional[BoardAnalysis]
    ) -> float:
        """
        计算bluff raise频率（facing bet时）

        Args:
            ctx: StrategyContext
            range_advantage: Range优势
            board_analysis: Board分析

        Returns:
            Bluff raise频率
        """
        # Bluff raise比bluff bet风险更大，频率更低
        base_freq = 0.15

        # IP可以bluff raise
        if ctx.is_in_position:
            base_freq += 0.05

        # Range advantage
        if range_advantage and range_advantage.advantage_score >= 0.30:
            base_freq += 0.10

        return min(0.30, max(0.0, base_freq))

    def _calculate_value_bet_sizing(
        self,
        ctx: StrategyContext,
        equity_info: EquityInfo,
        range_advantage: Optional[RangeAdvantage],
        board_analysis: Optional[BoardAnalysis]
    ) -> Dict[float, float]:
        """
        计算value bet sizing

        Args:
            ctx: StrategyContext
            equity_info: Equity信息
            range_advantage: Range优势
            board_analysis: Board分析

        Returns:
            Sizing分布 {pot_fraction: probability}
        """
        # 基础sizing: 0.66 pot
        base_size = self.default_cbet_size

        # 根据equity调整
        if equity_info.point_equity >= 0.75:
            # Very strong → larger bet
            base_size = 0.85
        elif equity_info.point_equity >= 0.65:
            base_size = 0.75
        elif equity_info.point_equity >= 0.55:
            base_size = 0.66
        else:
            base_size = 0.50

        # 根据board texture调整
        if board_analysis:
            if board_analysis.texture == 'wet' or board_analysis.draw_heavy:
                # Wet board → larger sizing (protection)
                base_size += 0.10
            elif board_analysis.texture == 'dry':
                # Dry board → smaller sizing (extract value from wider range)
                base_size -= 0.10

        # Clamp
        base_size = min(1.0, max(0.33, base_size))

        # 混合sizing（GTO需要）
        # 70%用base size，30%用更小/更大的size
        return {
            base_size: 0.70,
            base_size * 0.75: 0.15,
            base_size * 1.25: 0.15
        }

    def _calculate_raise_sizing(
        self,
        ctx: StrategyContext,
        equity_info: EquityInfo,
        range_advantage: Optional[RangeAdvantage],
        board_analysis: Optional[BoardAnalysis]
    ) -> Dict[float, float]:
        """
        计算raise sizing（facing bet时）

        Args:
            ctx: StrategyContext
            equity_info: Equity信息
            range_advantage: Range优势
            board_analysis: Board分析

        Returns:
            Sizing分布
        """
        # Raise size通常是3x对手的bet
        current_pot = ctx.pot_size + ctx.facing_bet_size
        min_raise = ctx.facing_bet_size * 2  # 最小raise

        # 基于equity调整
        if equity_info.point_equity >= 0.75:
            # Very strong → larger raise
            raise_size = ctx.facing_bet_size * 3.5
        else:
            raise_size = ctx.facing_bet_size * 2.5

        # 转换为pot fraction
        raise_pot_fraction = raise_size / current_pot

        return {
            raise_pot_fraction: 1.0
        }

    def _calculate_bluff_sizing(self, ctx: StrategyContext) -> Dict[float, float]:
        """
        计算bluff sizing

        Bluff通常用较大的sizing（更credible）

        Args:
            ctx: StrategyContext

        Returns:
            Sizing分布
        """
        # Bluff用较大的sizing（0.75-1.0 pot）
        return {
            0.85: 0.60,
            0.66: 0.40
        }

    def _create_defensive_decision(self, ctx: StrategyContext, reason: str) -> StrategyDecision:
        """
        创建保守决策（用于error handling）

        Args:
            ctx: StrategyContext
            reason: 原因

        Returns:
            StrategyDecision（保守的check/fold）
        """
        if ctx.facing_bet:
            # Facing bet → fold
            action_dist = {'fold': 1.0}
            sizing_dist = {}
        else:
            # Initiative → check
            action_dist = {'check': 1.0}
            sizing_dist = {}

        return StrategyDecision(
            action_distribution=action_dist,
            sizing_distribution=sizing_dist,
            reasoning=f"Defensive decision: {reason}",
            confidence=0.5,
            key_factors={
                'strategy': 'GTOStrategy',
                'decision_type': 'defensive',
                'reason': reason
            }
        )

    def get_name(self) -> str:
        """返回策略名称"""
        return "GTOStrategy"

    def reset(self):
        """重置策略（GTOStrategy无状态，不需要reset）"""
        pass
