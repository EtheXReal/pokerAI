"""
Strategy Engine - 动态策略引擎 (Phase 2.3)

整合三层架构，提供职业级决策建议：
- Range Engine (Phase 2.1): 范围推断和equity计算
- Opponent Modeling (Phase 2.2): 对手分类和统计
- Strategy Engine (Phase 2.3): GTO基线 + Exploit调整

核心功能：
1. GTO基线策略（翻前查找表 + 翻后公式）
2. 范围推断引擎（翻前 + 翻后动态更新）
3. 定量化Exploit策略（9种玩家类型 × 60个参数）
4. ProLevelAdvisor（端到端决策引擎）
5. DecisionOutput（分层输出格式）

性能目标：
- 决策延迟 < 100ms
- GTO公式准确性 > 95%
- Exploit有效性验证

设计原则：
- 简化GTO近似（不使用CFR求解器）
- 动态权重系统（按street/SPR调整）
- GTO+Exploit混合（可调节权重）
"""

# 核心类
from .advisor import (
    ProLevelAdvisor,
    GameState,
    create_advisor,
    quick_advise,
)

from .decision import (
    DecisionOutput,
    create_simple_decision,
    merge_decisions,
)

from .gto_baseline import (
    GTOBaseline,
    GTOContext,
    Street,
    Position,
)

from .range_estimator import (
    RangeEstimator,
    Action,
    estimate_villain_range,
)

from .exploits import (
    QuantifiedExploitStrategy,
    get_exploit_strategy,
    EXPLOIT_STRATEGIES,
)

__all__ = [
    # 核心决策
    'ProLevelAdvisor',
    'GameState',
    'create_advisor',
    'quick_advise',

    # 决策输出
    'DecisionOutput',
    'create_simple_decision',
    'merge_decisions',

    # GTO基线
    'GTOBaseline',
    'GTOContext',
    'Street',
    'Position',

    # 范围推断
    'RangeEstimator',
    'Action',
    'estimate_villain_range',

    # Exploit策略
    'QuantifiedExploitStrategy',
    'get_exploit_strategy',
    'EXPLOIT_STRATEGIES',
]

__version__ = '0.1.0'
