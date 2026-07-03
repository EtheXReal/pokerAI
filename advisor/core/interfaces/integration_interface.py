"""
Integration接口定义

Integration层负责orchestrate所有模块，生成完整的决策流程。
"""

from abc import ABC, abstractmethod
from typing import Optional
from advisor.core.data_structures import DecisionTrace, Action


class IDecisionIntegrator(ABC):
    """
    决策集成器接口

    职责：
    1. Orchestrate所有Analysis和Strategy模块
    2. 生成完整的DecisionTrace（确保模块不被架空）
    3. 选择最终action
    4. 性能监控

    决策流程：
    - 翻前：RangeEngine → GTOStrategy
    - 翻后：RangeEngine → EquityEngine → BoardAnalyzer → GTOStrategy
    - Phase 2: + OpponentModel → ExploitEngine → HybridStrategy
    """

    @abstractmethod
    def decide(self, game_state: any) -> DecisionTrace:
        """
        完整决策流程

        Args:
            game_state: 游戏状态（包含street, position, hand, board, etc.）

        Returns:
            DecisionTrace（包含所有中间结果和最终决策）

        流程：
        1. 调用RangeEngine获取hero_range和villain_range
        2. 如果是翻后：
           - 调用EquityEngine计算equity
           - 调用BoardAnalyzer分析board
        3. 构建StrategyContext
        4. 调用Strategy.decide()获取决策
        5. 选择最终action（从分布中采样）
        6. 构建DecisionTrace
        7. 验证模块使用（确保不被架空）
        """
        pass

    @abstractmethod
    def select_action(self, decision: 'StrategyDecision') -> Action:
        """
        从决策分布中选择最终action

        Args:
            decision: StrategyDecision（包含action_distribution）

        Returns:
            Action（选择的action）

        实现：
        - 根据action_distribution随机采样
        - 如果action需要sizing，从sizing_distribution采样
        """
        pass
