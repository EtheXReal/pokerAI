"""
HybridStrategy - GTO基准 + Exploit调整（重构版本）

核心改进：
- 使用exploits.py的类型安全handler系统
- 消除关键词匹配，直接调用apply_exploit_adjustment()
- 更清晰的代码结构，更容易测试

核心思想：
- Low confidence (< 0.3): 纯GTO，避免误判风险
- Medium confidence (0.3-0.7): 平滑混合GTO + Exploit
- High confidence (>= 0.7): 高权重Exploit调整
"""

from typing import Dict, Optional

from advisor_v2.core.interfaces.strategy_interface import IStrategy
from advisor_v2.core.data_structures import (
    StrategyContext,
    StrategyDecision,
)
from advisor_v2.strategy.gto_strategy import GTOStrategy
from advisor_v2.modeling.exploits import (
    StrategyLibrary,
    ActionContext,
    apply_exploit_adjustment,
)
from advisor_v2.modeling.models import PlayerType


class HybridStrategy(IStrategy):
    """
    混合策略：GTO基准 + Exploit调整（重构版本）

    决策流程：
    1. 获取GTO基准决策
    2. 检查对手建模数据（player_type, confidence）
    3. 计算exploit权重（alpha）
    4. 获取exploit建议
    5. 调用handler应用调整
    6. 返回混合决策
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        初始化HybridStrategy

        Args:
            config: 策略配置
                - confidence_threshold_low: 纯GTO阈值（默认0.3）
                - confidence_threshold_high: 高exploit阈值（默认0.7）
                - max_exploit_weight: 最大exploit权重（默认1.0）
                - enable_exploit: 是否启用exploit（默认True）
        """
        self.config = config or {}

        # Confidence阈值
        self.confidence_low = self.config.get('confidence_threshold_low', 0.3)
        self.confidence_high = self.config.get('confidence_threshold_high', 0.7)
        self.max_exploit_weight = self.config.get('max_exploit_weight', 1.0)
        self.enable_exploit = self.config.get('enable_exploit', True)

        # 初始化GTO策略和Exploit库
        self.gto_strategy = GTOStrategy(config)
        self.exploit_library = StrategyLibrary()

        # 追踪器（可选）
        self.tracer = None

    def set_tracer(self, tracer):
        """设置追踪器"""
        self.tracer = tracer
        # 同时设置GTO策略的tracer
        if hasattr(self.gto_strategy, 'set_tracer'):
            self.gto_strategy.set_tracer(tracer)

    def decide(self, ctx: StrategyContext) -> StrategyDecision:
        """
        基于上下文做出决策

        Args:
            ctx: StrategyContext（包含villain_tendencies）

        Returns:
            StrategyDecision（混合GTO + Exploit）
        """
        # 1. 获取GTO基准决策
        gto_decision = self.gto_strategy.decide(ctx)

        # 2. 如果未启用exploit，直接返回GTO
        if not self.enable_exploit:
            return gto_decision

        # 3. 获取对手建模数据
        villain_tendencies = ctx.villain_tendencies or {}
        player_type_str = villain_tendencies.get('player_type', 'UNKNOWN')
        confidence = villain_tendencies.get('confidence', 0.0)

        # DEBUG
        import os
        if os.environ.get('DEBUG_HYBRID') == '1':
            print(f"[HybridStrategy] player_type={player_type_str}, confidence={confidence:.2f}")

        # 4. 判断是否需要exploit调整
        if confidence < self.confidence_low:
            # Low confidence: 纯GTO
            if self.tracer and self.tracer.is_enabled():
                self.tracer.step_begin()
                self.tracer.step_end(
                    step_name="HybridStrategy决策",
                    module="advisor_v2/strategy/hybrid_strategy.py",
                    function="decide",
                    inputs={
                        "player_type": player_type_str,
                        "confidence": confidence,
                        "blend_mode": "pure_gto"
                    },
                    outputs={"action_dist": gto_decision.action_distribution},
                    reasoning=f"Confidence {confidence:.2f} < {self.confidence_low} → 纯GTO策略"
                )
            return gto_decision

        # 5. 解析player_type
        try:
            player_type = PlayerType[player_type_str.upper()] if player_type_str != 'UNKNOWN' else PlayerType.UNKNOWN
        except (KeyError, AttributeError):
            player_type = PlayerType.UNKNOWN
            if os.environ.get('DEBUG_HYBRID') == '1':
                print(f"[HybridStrategy] Failed to parse player_type: {player_type_str}")

        # 如果player_type是UNKNOWN，用纯GTO
        if player_type == PlayerType.UNKNOWN:
            if os.environ.get('DEBUG_HYBRID') == '1':
                print(f"[HybridStrategy] player_type is UNKNOWN, using pure GTO")
            return gto_decision

        # 6. 计算exploit权重
        alpha = self._calculate_blend_factor(confidence)

        # 7. 获取情境类型
        context_type = self._get_context_type(ctx)

        # 8. 获取exploit建议
        exploit_advice = self.exploit_library.get_advice(player_type, context_type)

        if os.environ.get('DEBUG_HYBRID') == '1':
            print(f"[HybridStrategy] alpha={alpha:.2f}, context={context_type}, advice={exploit_advice.action_type if exploit_advice else None}")

        # 9. 应用exploit调整
        if exploit_advice:
            blended_decision = self._blend_decisions(
                gto_decision,
                exploit_advice,
                alpha,
                ctx
            )

            # Trace
            if self.tracer and self.tracer.is_enabled():
                self.tracer.step_begin()
                self.tracer.step_end(
                    step_name="HybridStrategy决策",
                    module="advisor_v2/strategy/hybrid_strategy.py",
                    function="decide",
                    inputs={
                        "player_type": player_type_str,
                        "confidence": confidence,
                        "blend_mode": "hybrid",
                        "alpha": alpha,
                        "context": context_type.value,
                        "exploit_action_type": exploit_advice.action_type.name,
                    },
                    outputs={"action_dist": blended_decision.action_distribution},
                    reasoning=f"Confidence {confidence:.2f} → α={alpha:.2f} blending (vs {player_type_str}, {exploit_advice.action_type.name})"
                )

            return blended_decision
        else:
            # 没有匹配的exploit建议，返回GTO
            return gto_decision

    def _calculate_blend_factor(self, confidence: float) -> float:
        """
        计算exploit权重（alpha）

        线性插值：
        - confidence < 0.3: alpha = 0.0 (纯GTO)
        - confidence = 0.5: alpha = 0.35
        - confidence >= 0.7: alpha = max_exploit_weight

        Args:
            confidence: 对手建模置信度 (0-1)

        Returns:
            Exploit权重 (0-1)
        """
        if confidence < self.confidence_low:
            return 0.0
        elif confidence >= self.confidence_high:
            return self.max_exploit_weight
        else:
            # 线性插值: [0.3, 0.7] → [0.0, max_exploit_weight]
            normalized = (confidence - self.confidence_low) / (self.confidence_high - self.confidence_low)
            return normalized * self.max_exploit_weight

    def _get_context_type(self, ctx: StrategyContext) -> ActionContext:
        """
        识别当前情境类型

        Args:
            ctx: StrategyContext

        Returns:
            ActionContext枚举
        """
        street = ctx.street
        facing_bet = ctx.facing_bet

        # 翻前
        if street == 'preflop':
            if not facing_bet:
                # Open/steal机会
                if ctx.position.value in ['BTN', 'CO', 'SB']:
                    return ActionContext.STEAL_ATTEMPT
                else:
                    return ActionContext.STEAL_ATTEMPT  # 默认用steal
            else:
                # Facing raise（简化：有人raise时就算3-bet决策）
                return ActionContext.THREE_BET

        # 翻后
        else:
            if not facing_bet:
                # 主动决策
                # 判断是否C-bet机会（简化：翻牌圈第一次行动）
                if street == 'flop' and len(ctx.action_history) < 3:  # 粗略判断
                    return ActionContext.CBET
                else:
                    return ActionContext.VALUE_BET  # 或bluff，具体由equity判断
            else:
                # 防守决策
                return ActionContext.DEFENSE

    def _blend_decisions(
        self,
        gto_decision: StrategyDecision,
        exploit_advice: any,
        alpha: float,
        ctx: StrategyContext
    ) -> StrategyDecision:
        """
        混合GTO决策和Exploit建议（重构版本）

        核心改进：直接调用apply_exploit_adjustment()，无需关键词匹配

        Args:
            gto_decision: GTO基准决策
            exploit_advice: Exploit建议（StrategyAdvice）
            alpha: Exploit权重 (0-1)
            ctx: StrategyContext

        Returns:
            混合后的StrategyDecision
        """
        # 获取GTO的action分布
        gto_actions = gto_decision.action_distribution.copy()

        # 调用exploits.py的handler系统
        adjusted_actions = apply_exploit_adjustment(
            gto_actions=gto_actions,
            advice=exploit_advice,
            alpha=alpha,
            ctx=ctx
        )

        # 应用exploit sizing（如果有）
        adjusted_sizing = self._apply_exploit_sizing(
            gto_decision.sizing_distribution,
            exploit_advice,
            alpha,
            ctx
        )

        # 构建新的决策
        blended_decision = StrategyDecision(
            action_distribution=adjusted_actions,
            sizing_distribution=adjusted_sizing,
            reasoning=f"Hybrid: {gto_decision.reasoning} + Exploit (α={alpha:.2f}): {exploit_advice.reason}",
            confidence=gto_decision.confidence * (1 - alpha * 0.3),  # Exploit增加不确定性
            key_factors={
                **gto_decision.key_factors,
                'strategy': 'HybridStrategy',
                'exploit_alpha': alpha,
                'exploit_action_type': exploit_advice.action_type.name,
                'exploit_reason': exploit_advice.reason,
                'gto_actions': gto_actions,
                'adjusted_actions': adjusted_actions,
            }
        )

        return blended_decision

    def _apply_exploit_sizing(
        self,
        gto_sizing: Dict[float, float],
        exploit_advice: any,
        alpha: float,
        ctx: StrategyContext
    ) -> Dict[float, float]:
        """
        应用exploit sizing建议

        Args:
            gto_sizing: GTO sizing分布
            exploit_advice: Exploit建议
            alpha: Exploit权重
            ctx: StrategyContext

        Returns:
            调整后的sizing分布
        """
        if not exploit_advice.sizing_range or alpha < 0.1:
            return gto_sizing

        # 解析sizing_range
        sizing_min, sizing_max = exploit_advice.sizing_range
        target_sizing_avg = (sizing_min + sizing_max) / 2

        # 如果alpha很高，完全使用exploit sizing
        if alpha >= 0.8:
            return {target_sizing_avg: 1.0}

        # 否则混合 (简单混合：将exploit sizing加入分布)
        mixed_sizing = gto_sizing.copy()

        # 归一化GTO
        total_gto = sum(mixed_sizing.values())
        if total_gto > 0:
            mixed_sizing = {k: v * (1 - alpha) for k, v in mixed_sizing.items()}

        # 加入Exploit
        mixed_sizing[target_sizing_avg] = mixed_sizing.get(target_sizing_avg, 0.0) + alpha

        # 重新归一化
        total = sum(mixed_sizing.values())
        if total > 0:
            return {k: v/total for k, v in mixed_sizing.items()}

        return {target_sizing_avg: 1.0}

    def get_name(self) -> str:
        """返回策略名称"""
        return "HybridStrategy"

    def reset(self):
        """重置策略"""
        self.gto_strategy.reset()
