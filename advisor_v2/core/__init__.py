"""
Core模块

包含advisor_v2的核心组件：
- data_structures: 核心数据结构
- interfaces: 所有接口定义
- poker_advisor: 主入口（PokerAdvisor类）
- decision_integrator: 决策整合器
"""

from advisor_v2.core.data_structures import (
    StrategyContext,
    StrategyDecision,
    EquityInfo,
    RangeAdvantage,
    BoardAnalysis,
    DecisionTrace,
    PlayerProfile,
    PlayerType,
    ExploitAdjustment,
)

__all__ = [
    "StrategyContext",
    "StrategyDecision",
    "EquityInfo",
    "RangeAdvantage",
    "BoardAnalysis",
    "DecisionTrace",
    "PlayerProfile",
    "PlayerType",
    "ExploitAdjustment",
]
