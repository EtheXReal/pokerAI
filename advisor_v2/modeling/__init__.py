"""
对手建模引擎 (Opponent Modeling Engine)

Phase 2.2 - 职业级AI决策系统的第二层

核心功能:
1. 统计追踪 (stats.py) - 20+对手指标实时追踪
2. 玩家分类 (classifier.py) - 9种玩家类型识别
3. Exploit策略 (exploits.py) - 针对性策略调整
4. 持久化存储 (storage.py) - SQLite跨session数据

设计目标:
- 50手后分类准确率 > 85%
- 支持多人同时追踪
- 置信度评分系统
- 动态重分类能力
"""

from .stats import OpponentStats, PositionStats, StreetsStats, create_opponent_stats
from .models import PlayerType, ActionType, StreetType, PositionType, HandResult, ActionRecord
from .tracker import StatsTracker, ActionParser, create_tracker
from .storage import StorageBackend, SQLiteStorage, create_storage
from .classifier import PlayerClassifier, ClassificationResult, classify_player, get_player_type_name
from .exploits import (
    ExploitStrategy, StrategyLibrary, StrategyAdvice,
    ActionContext, ExploitActionType, get_strategy, apply_exploit_adjustment
)

__all__ = [
    'OpponentStats',
    'PositionStats',
    'StreetsStats',
    'create_opponent_stats',
    'PlayerType',
    'ActionType',
    'StreetType',
    'PositionType',
    'HandResult',
    'ActionRecord',
    'StatsTracker',
    'ActionParser',
    'create_tracker',
    'StorageBackend',
    'SQLiteStorage',
    'create_storage',
    'PlayerClassifier',
    'ClassificationResult',
    'classify_player',
    'get_player_type_name',
    'ExploitStrategy',
    'StrategyLibrary',
    'StrategyAdvice',
    'ActionContext',
    'ExploitActionType',
    'get_strategy',
    'apply_exploit_adjustment',
]

__version__ = '0.1.0'
