"""
Strategy接口定义

策略层负责核心决策逻辑，基于Analysis Layer和Model Layer的输出，
生成action distribution + sizing distribution。
"""

from abc import ABC, abstractmethod
from advisor.core.data_structures import StrategyContext, StrategyDecision


class IStrategy(ABC):
    """
    策略接口

    不同的策略实现：
    - GTOStrategy: GTO基准策略（Range-based）
    - ExploitStrategy: Exploit策略（基于对手模型调整GTO）
    - HybridStrategy: 混合策略（GTO + Exploit动态平衡）
    - SolverStrategy: Solver策略（Phase 3，集成预计算数据）
    """

    @abstractmethod
    def decide(self, ctx: StrategyContext) -> StrategyDecision:
        """
        基于上下文做出决策

        Args:
            ctx: StrategyContext，包含所有决策所需信息

        Returns:
            StrategyDecision，包含：
            - action_distribution: {'raise': 0.6, 'call': 0.3, 'fold': 0.1}
            - sizing_distribution: {0.5: 0.4, 0.75: 0.6}
            - reasoning: 决策理由
            - key_factors: 关键因素（用于验证模块使用）

        注意：
        1. 必须在key_factors中记录使用的关键信息（如equity, range_advantage）
        2. reasoning应该清晰说明决策逻辑
        3. action_distribution总和必须为1.0
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """
        返回策略名称

        用于：
        - Trace追踪
        - Metrics统计
        - A/B测试

        Returns:
            策略名称，如 "GTOStrategy", "ExploitStrategy"
        """
        pass

    def reset(self):
        """
        重置策略状态（可选实现）

        某些策略可能有内部状态（如学习型策略），
        在新的session开始时需要重置。
        """
        pass


class IStrategyConfig(ABC):
    """
    策略配置接口

    每个策略可以有自己的配置，支持：
    - 参数调整（如threshold, sizing）
    - 动态加载
    - 热更新
    """

    @abstractmethod
    def get_config(self, key: str) -> any:
        """获取配置项"""
        pass

    @abstractmethod
    def set_config(self, key: str, value: any):
        """设置配置项"""
        pass

    @abstractmethod
    def load_from_file(self, filepath: str):
        """从文件加载配置"""
        pass

    @abstractmethod
    def save_to_file(self, filepath: str):
        """保存配置到文件"""
        pass
