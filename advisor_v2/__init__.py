"""
Advisor V2 - 职业级Poker AI建议系统

这是advisor模块的重构版本，采用可插拔架构设计：
- Range-based决策（非hand-centric）
- 完整的Equity信息（分布而非单点）
- 激活的对手建模和Exploit调整
- 全链路Trace和性能监控
- 接口隔离，易于测试和调试

Phase 1目标：
- 实现GTO基准策略（Range-based）
- vs Random: +420 BB/100
- 决策延迟: 翻前<5ms, 翻后<10ms
"""

__version__ = "2.0.0-alpha"

# TODO: PokerAdvisor还未实现
# from advisor_v2.core.poker_advisor import PokerAdvisor
from advisor_v2.core.data_structures import (
    StrategyContext,
    StrategyDecision,
    EquityInfo,
    RangeAdvantage,
    BoardAnalysis,
    DecisionTrace,
)

__all__ = [
    # "PokerAdvisor",
    "StrategyContext",
    "StrategyDecision",
    "EquityInfo",
    "RangeAdvantage",
    "BoardAnalysis",
    "DecisionTrace",
]
