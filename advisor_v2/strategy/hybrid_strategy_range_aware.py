"""
HybridStrategy Range-Aware版本

扩展HybridStrategy，支持范围感知exploit系统。

关键改进：
1. 计算equity bucket（使用EquityBucketClassifier）
2. 构建DecisionContext（传递equity信息）
3. 使用range-aware handlers（而非频率调整）
4. 支持新旧系统并存（向后兼容）
"""
from typing import Dict, Optional
import os

from advisor_v2.strategy.hybrid_strategy import HybridStrategy
from advisor_v2.core.data_structures import (
    StrategyContext,
    StrategyDecision,
)
from advisor_v2.modeling.exploits_range_aware import get_range_aware_strategy_library
from advisor_v2.modeling.range_aware import (
    EquityBucket,
    EquityBucketClassifier,
    DecisionContext,
    RangeAwareAdvice,
)
from advisor_v2.modeling.range_aware_handlers import apply_range_aware_adjustment
from advisor_v2.modeling.models import PlayerType, StreetType


class HybridStrategyRangeAware(HybridStrategy):
    """
    范围感知混合策略

    继承自HybridStrategy，添加range-aware支持
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        初始化Range-Aware Hybrid Strategy

        Args:
            config: 策略配置
                - use_range_aware: 是否使用range-aware系统（默认True）
                - 其他参数同HybridStrategy
        """
        super().__init__(config)

        # Range-aware配置
        self.use_range_aware = self.config.get('use_range_aware', True)

        # 初始化range-aware组件
        if self.use_range_aware:
            self.equity_classifier = EquityBucketClassifier()
            self.range_aware_library = get_range_aware_strategy_library()

            if os.environ.get('DEBUG_HYBRID') == '1':
                print("[HybridStrategyRangeAware] Range-aware mode ENABLED")

    def _blend_decisions(
        self,
        gto_decision: StrategyDecision,
        exploit_advice: any,
        alpha: float,
        ctx: StrategyContext
    ) -> StrategyDecision:
        """
        混合GTO和Exploit决策（Range-Aware版本）

        逻辑：
        1. 检查exploit_advice类型
        2. 如果是RangeAwareAdvice：
           a. 计算equity bucket
           b. 构建DecisionContext
           c. 使用range-aware handler
        3. 否则fallback到旧的频率调整系统

        Args:
            gto_decision: GTO决策
            exploit_advice: Exploit建议（可能是RangeAwareAdvice或旧的StrategyAdvice）
            alpha: Exploit权重
            ctx: StrategyContext

        Returns:
            混合决策
        """
        # 获取GTO action分布
        gto_actions = gto_decision.action_distribution.copy()

        # 检查是否是RangeAwareAdvice
        if isinstance(exploit_advice, RangeAwareAdvice) and self.use_range_aware:
            # === Range-Aware路径 ===
            adjusted_actions = self._apply_range_aware_adjustment(
                gto_actions=gto_actions,
                advice=exploit_advice,
                alpha=alpha,
                ctx=ctx,
            )
        else:
            # === 旧系统路径（频率调整） ===
            from advisor_v2.modeling.exploits import apply_exploit_adjustment
            adjusted_actions = apply_exploit_adjustment(
                gto_actions=gto_actions,
                advice=exploit_advice,
                alpha=alpha,
                ctx=ctx
            )

        # 应用exploit sizing（同HybridStrategy）
        adjusted_sizing = self._apply_exploit_sizing(
            gto_decision.sizing_distribution,
            exploit_advice,
            alpha,
            ctx
        )

        # 返回混合决策
        return StrategyDecision(
            action_distribution=adjusted_actions,
            sizing_distribution=adjusted_sizing,
            reasoning=f"Hybrid (Range-Aware α={alpha:.2f}): " + gto_decision.reasoning
        )

    def _apply_range_aware_adjustment(
        self,
        gto_actions: Dict[str, float],
        advice: RangeAwareAdvice,
        alpha: float,
        ctx: StrategyContext,
    ) -> Dict[str, float]:
        """
        应用范围感知调整

        Steps:
        1. 从ctx中提取hole_cards和board
        2. 使用EquityBucketClassifier计算equity bucket
        3. 构建DecisionContext
        4. 调用range-aware handler

        Args:
            gto_actions: GTO action分布
            advice: RangeAwareAdvice
            alpha: exploit权重
            ctx: StrategyContext

        Returns:
            调整后的action分布
        """
        # 1. 提取hole_cards和board
        try:
            hole_cards = ctx.hand.cards if hasattr(ctx, 'hand') and hasattr(ctx.hand, 'cards') else []
            board = ctx.board if hasattr(ctx, 'board') else []
            street = self._get_street_from_context(ctx)

            # 2. 计算equity bucket
            equity_bucket = self.equity_classifier.classify(
                hole_cards=hole_cards,
                board=board,
                opponent_range=None,  # TODO: 集成range estimation
                street=street,
            )

            # 估算equity（暂时使用bucket的中位数）
            equity = self._bucket_to_equity(equity_bucket)

            if os.environ.get('DEBUG_HYBRID') == '1':
                print(f"[RangeAware] bucket={equity_bucket.value}, equity={equity:.2f}")

            # 3. 构建DecisionContext
            decision_ctx = DecisionContext(
                game_state=None,  # 不需要完整game_state
                hole_cards=hole_cards,
                board=board,
                street=street,
                equity_bucket=equity_bucket,
                equity=equity,
                opponent_type=self._get_opponent_type_from_ctx(ctx),
            )

            # 4. 应用range-aware调整
            adjusted = apply_range_aware_adjustment(
                gto_actions=gto_actions,
                advice=advice,
                alpha=alpha,
                ctx=decision_ctx,
            )

            return adjusted

        except Exception as e:
            # 出错时fallback到GTO（安全第一）
            print(f"[WARNING] Range-aware adjustment failed: {e}, using GTO")
            return gto_actions

    def _get_street_from_context(self, ctx: StrategyContext) -> Optional[StreetType]:
        """从StrategyContext中提取street"""
        if hasattr(ctx, 'street'):
            # 直接有street属性
            street_str = ctx.street
            if isinstance(street_str, str):
                try:
                    return StreetType[street_str.upper()]
                except (KeyError, AttributeError):
                    pass

        # 根据board长度推断
        if hasattr(ctx, 'board'):
            board_len = len(ctx.board) if ctx.board else 0
            if board_len == 0:
                return StreetType.PREFLOP
            elif board_len == 3:
                return StreetType.FLOP
            elif board_len == 4:
                return StreetType.TURN
            elif board_len == 5:
                return StreetType.RIVER

        return None

    def _bucket_to_equity(self, bucket: EquityBucket) -> float:
        """
        将equity bucket映射到估算的equity值

        使用bucket的中位数作为估算
        """
        bucket_ranges = {
            EquityBucket.NUTTED: (0.80, 1.00),
            EquityBucket.STRONG: (0.65, 0.80),
            EquityBucket.MEDIUM_STRONG: (0.50, 0.65),
            EquityBucket.MEDIUM: (0.35, 0.50),
            EquityBucket.WEAK: (0.20, 0.35),
            EquityBucket.AIR: (0.00, 0.20),
        }
        low, high = bucket_ranges.get(bucket, (0.0, 1.0))
        return (low + high) / 2

    def _get_opponent_type_from_ctx(self, ctx: StrategyContext) -> Optional[PlayerType]:
        """从context中提取opponent type"""
        if hasattr(ctx, 'villain_tendencies') and ctx.villain_tendencies:
            player_type_str = ctx.villain_tendencies.get('player_type', 'UNKNOWN')
            try:
                return PlayerType[player_type_str.upper()]
            except (KeyError, AttributeError):
                pass
        return None

    def decide(self, ctx: StrategyContext) -> StrategyDecision:
        """
        决策入口（Override）

        逻辑：
        1. 如果use_range_aware=True，使用range-aware策略库
        2. 否则使用旧策略库

        这样可以在测试时灵活切换新旧系统
        """
        # 如果use_range_aware，替换exploit_library
        original_library = None
        if self.use_range_aware:
            original_library = self.exploit_library
            self.exploit_library = self.range_aware_library

        # 调用父类的decide
        decision = super().decide(ctx)

        # 恢复原library
        if original_library:
            self.exploit_library = original_library

        return decision
