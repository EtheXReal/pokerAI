"""
核心接口定义

所有模块都通过接口交互，实现：
1. 接口隔离：单一职责
2. 依赖注入：松耦合
3. 易于测试：Mock任意模块
4. 易于扩展：新实现只需实现接口
"""

from advisor_v2.core.interfaces.strategy_interface import IStrategy
from advisor_v2.core.interfaces.analysis_interface import (
    IRangeEngine,
    IEquityEngine,
    IBoardAnalyzer
)
from advisor_v2.core.interfaces.model_interface import IOpponentModel
from advisor_v2.core.interfaces.exploit_interface import IExploitEngine
from advisor_v2.core.interfaces.integration_interface import IDecisionIntegrator

__all__ = [
    "IStrategy",
    "IRangeEngine",
    "IEquityEngine",
    "IBoardAnalyzer",
    "IOpponentModel",
    "IExploitEngine",
    "IDecisionIntegrator",
]
