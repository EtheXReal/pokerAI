"""
HybridStrategy - GTO基准 + Exploit调整

这是advisor_v2的关键改进：根据对手建模数据动态调整GTO策略。

核心思想：
- Low confidence (< 0.3): 纯GTO，避免误判风险
- Medium confidence (0.3-0.7): 平滑混合GTO + Exploit
- High confidence (>= 0.7): 70% Exploit + 30% GTO基底

设计原则：
1. 单一职责：GTOStrategy保持纯粹，HybridStrategy负责混合
2. 风险可控：confidence低时退化为GTO
3. 充分利用：exploits.py的StrategyLibrary直接使用
4. 符合理论：对未知对手用GTO，对已知对手加入exploit
"""

from typing import Dict, Optional
import random

from advisor_v2.core.interfaces.strategy_interface import IStrategy
from advisor_v2.core.data_structures import (
    StrategyContext,
    StrategyDecision,
)
from advisor_v2.strategy.gto_strategy import GTOStrategy
from advisor_v2.modeling.exploits import StrategyLibrary, ActionContext
from advisor_v2.modeling.models import PlayerType


class HybridStrategy(IStrategy):
    """
    混合策略：GTO基准 + Exploit调整

    决策流程：
    1. 获取villain_tendencies (player_type, confidence)
    2. 计算GTO基准决策
    3. 根据confidence决定exploit权重
    4. 获取针对该玩家类型的exploit建议
    5. 混合GTO和Exploit生成最终决策
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        初始化HybridStrategy

        Args:
            config: 策略配置
                - confidence_threshold_low: 纯GTO阈值（默认0.3）
                - confidence_threshold_high: 高exploit阈值（默认0.7）
                - max_exploit_weight: 最大exploit权重（默认0.7）
                - enable_exploit: 是否启用exploit（默认True）
        """
        self.config = config or {}

        # Confidence阈值
        self.confidence_low = self.config.get('confidence_threshold_low', 0.3)
        self.confidence_high = self.config.get('confidence_threshold_high', 0.7)
        self.max_exploit_weight = self.config.get('max_exploit_weight', 0.7)
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

        # DEBUG: 打印对手建模数据
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
            import os
            if os.environ.get('DEBUG_HYBRID') == '1':
                print(f"[HybridStrategy] Failed to parse player_type: {player_type_str}")

        # 如果player_type是UNKNOWN，也用纯GTO
        if player_type == PlayerType.UNKNOWN:
            import os
            if os.environ.get('DEBUG_HYBRID') == '1':
                print(f"[HybridStrategy] player_type is UNKNOWN, using pure GTO")
            return gto_decision

        # 6. 计算exploit权重
        alpha = self._calculate_blend_factor(confidence)

        # 7. 获取exploit建议
        context_type = self._get_context_type(ctx)
        exploit_advice = self.exploit_library.get_advice(player_type, context_type)

        import os
        if os.environ.get('DEBUG_HYBRID') == '1':
            print(f"[HybridStrategy] alpha={alpha:.2f}, context={context_type}, advice={exploit_advice.action if exploit_advice else None}")

        # 8. 混合GTO + Exploit
        if exploit_advice:
            blended_decision = self._blend_decisions(
                gto_decision,
                exploit_advice,
                alpha,
                ctx,
                player_type
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
                        "context": context_type
                    },
                    outputs={"action_dist": blended_decision.action_distribution},
                    reasoning=f"Confidence {confidence:.2f} → α={alpha:.2f} blending (vs {player_type_str} in {context_type})"
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
        - confidence = 0.5: alpha = 0.35 (50% → 35% exploit)
        - confidence >= 0.7: alpha = 0.7 (最大exploit)

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
            # 线性插值: [0.3, 0.7] → [0.0, 0.7]
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
                # Facing raise
                # 判断是否3-bet情况（需要检查action history）
                # 简化：有人raise时就算3-bet决策
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
        exploit_advice: 'StrategyAdvice',
        alpha: float,
        ctx: StrategyContext,
        player_type: PlayerType
    ) -> StrategyDecision:
        """
        混合GTO决策和Exploit建议

        混合策略：
        1. 解析exploit建议（如"频繁偷盲 80%+"）
        2. 调整GTO的action distribution
        3. 保持sizing distribution（exploit主要影响频率）

        Args:
            gto_decision: GTO基准决策
            exploit_advice: Exploit建议
            alpha: Exploit权重 (0-1)
            ctx: StrategyContext
            player_type: 对手类型

        Returns:
            混合后的StrategyDecision
        """
        # 获取GTO的action分布
        gto_actions = gto_decision.action_distribution.copy()

        # 根据exploit建议调整action分布
        adjusted_actions = self._apply_exploit_advice(
            gto_actions,
            exploit_advice,
            alpha,
            ctx
        )

        # 归一化
        total = sum(adjusted_actions.values())
        if total > 0:
            adjusted_actions = {k: v/total for k, v in adjusted_actions.items()}

        # 构建新的决策
        blended_decision = StrategyDecision(
            action_distribution=adjusted_actions,
            sizing_distribution=gto_decision.sizing_distribution,  # 保持GTO sizing
            reasoning=f"Hybrid: {gto_decision.reasoning} + Exploit vs {player_type.value} (α={alpha:.2f}): {exploit_advice.action}",
            confidence=gto_decision.confidence * (1 - alpha * 0.3),  # Exploit增加不确定性
            key_factors={
                **gto_decision.key_factors,
                'strategy': 'HybridStrategy',
                'exploit_alpha': alpha,
                'player_type': player_type.value,
                'exploit_advice': exploit_advice.action,
                'gto_actions': gto_actions,
                'adjusted_actions': adjusted_actions,
            }
        )

        return blended_decision

    def _apply_exploit_advice(
        self,
        gto_actions: Dict[str, float],
        exploit_advice: 'StrategyAdvice',
        alpha: float,
        ctx: StrategyContext
    ) -> Dict[str, float]:
        """
        应用exploit建议调整action分布

        根据建议的action和frequency调整GTO频率：
        - "频繁偷盲" → 增加raise频率
        - "紧缩防守" → 增加fold频率
        - "激进3-bet" → 增加raise频率
        - "被动跟注" → 增加call频率

        Args:
            gto_actions: GTO action分布
            exploit_advice: Exploit建议
            alpha: Exploit权重
            ctx: StrategyContext

        Returns:
            调整后的action分布
        """
        adjusted = gto_actions.copy()

        # 解析建议的频率（如"80%+"）
        target_frequency = self._parse_frequency(exploit_advice.frequency)

        # 根据建议的action类型调整
        action_keyword = exploit_advice.action.lower()

        # 偷盲/激进raise
        if '偷盲' in action_keyword or '激进' in action_keyword or 'raise' in action_keyword or '加注' in action_keyword:
            # 增加raise/bet频率
            primary_action = 'raise' if 'raise' in adjusted else 'bet'
            if primary_action in adjusted:
                # 计算目标频率（GTO → Exploit的插值）
                gto_freq = adjusted.get(primary_action, 0.0)
                target_freq = max(target_frequency, 0.7)  # 激进至少70%
                new_freq = gto_freq + alpha * (target_freq - gto_freq)

                # 调整
                delta = new_freq - adjusted.get(primary_action, 0.0)
                adjusted[primary_action] = new_freq
                # 从fold中减去
                adjusted['fold'] = max(0.0, adjusted.get('fold', 0.0) - delta)

        # 紧缩防守/过度弃牌
        elif '弃牌' in action_keyword or 'fold' in action_keyword or '紧' in action_keyword:
            # 增加fold频率
            if 'fold' in adjusted:
                gto_freq = adjusted.get('fold', 0.0)
                target_freq = max(target_frequency, 0.6)
                new_freq = gto_freq + alpha * (target_freq - gto_freq)

                delta = new_freq - adjusted.get('fold', 0.0)
                adjusted['fold'] = new_freq
                # 从call/raise中减去
                if 'call' in adjusted:
                    adjusted['call'] = max(0.0, adjusted.get('call', 0.0) - delta * 0.7)
                if 'raise' in adjusted or 'bet' in adjusted:
                    action_key = 'raise' if 'raise' in adjusted else 'bet'
                    adjusted[action_key] = max(0.0, adjusted.get(action_key, 0.0) - delta * 0.3)

        # 被动跟注
        elif '跟注' in action_keyword or 'call' in action_keyword or '被动' in action_keyword:
            # 增加call频率
            if 'call' in adjusted:
                gto_freq = adjusted.get('call', 0.0)
                target_freq = max(target_frequency, 0.5)
                new_freq = gto_freq + alpha * (target_freq - gto_freq)

                delta = new_freq - adjusted.get('call', 0.0)
                adjusted['call'] = new_freq
                # 从fold中减去
                adjusted['fold'] = max(0.0, adjusted.get('fold', 0.0) - delta)

        # Value betting（针对calling station）
        elif 'value' in action_keyword or '价值' in action_keyword:
            # 增加bet/raise频率，减少check
            primary_action = 'bet' if 'bet' in adjusted else 'raise'
            if primary_action in adjusted:
                gto_freq = adjusted.get(primary_action, 0.0)
                new_freq = gto_freq + alpha * (0.8 - gto_freq)

                delta = new_freq - adjusted.get(primary_action, 0.0)
                adjusted[primary_action] = new_freq
                if 'check' in adjusted:
                    adjusted['check'] = max(0.0, adjusted.get('check', 0.0) - delta)

        # 确保所有值非负
        for key in adjusted:
            adjusted[key] = max(0.0, adjusted[key])

        return adjusted

    def _parse_frequency(self, frequency_str: str) -> float:
        """
        解析频率字符串

        Args:
            frequency_str: "80%+", "50-70%", "rarely"等

        Returns:
            频率值 (0-1)
        """
        if not frequency_str:
            return 0.5

        freq_lower = frequency_str.lower()

        # 解析百分比
        if '%' in freq_lower:
            # 提取数字
            import re
            numbers = re.findall(r'\d+', freq_lower)
            if numbers:
                num = int(numbers[0])
                return num / 100.0

        # 关键词
        if 'rarely' in freq_lower or '很少' in freq_lower:
            return 0.2
        elif 'sometimes' in freq_lower or '有时' in freq_lower:
            return 0.4
        elif 'often' in freq_lower or '经常' in freq_lower or '频繁' in freq_lower:
            return 0.7
        elif 'always' in freq_lower or '总是' in freq_lower:
            return 0.9

        # 默认
        return 0.5

    def get_name(self) -> str:
        """返回策略名称"""
        return "HybridStrategy"

    def reset(self):
        """重置策略"""
        self.gto_strategy.reset()
