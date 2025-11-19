# 职业级Poker AI终极架构设计

## 🎯 设计目标

构建达到/超越职业选手水平的德州扑克AI建议系统，针对5人桌（2-5位玩家）现金局。

**核心要求**：
1. **完整性**：Range-based GTO + Exploit适应性策略
2. **可插拔性**：模块化设计，易于测试和调试
3. **可扩展性**：支持未来集成Solver、CFR、深度学习
4. **可观测性**：全链路trace，每个决策可追踪

---

## 📐 整体架构

### 五层架构 + 横向支撑

```
┌─────────────────────────────────────────────────────────────────┐
│                    Poker Advisor (Facade)                        │
│                  统一决策入口 + 决策追踪                           │
└─────────────────────────────────────────────────────────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        ▼                        ▼                        ▼
┌──────────────┐      ┌──────────────────┐      ┌──────────────┐
│ Strategy     │      │ Decision         │      │ Solver       │
│ Layer        │◄─────┤ Integration      │─────►│ Interface    │
│              │      │ Layer            │      │ (可插拔)      │
└──────┬───────┘      └──────────────────┘      └──────────────┘
       │                       ▲
       │              ┌────────┴────────┐
       ▼              ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Analysis     │  │ Model        │  │ Exploit      │
│ Layer        │  │ Layer        │  │ Layer        │
│              │  │              │  │              │
│ Range分析    │  │ 对手建模      │  │ Exploit调整  │
│ Equity计算   │  │ 趋势追踪      │  │ GTO-E平衡    │
│ Board分析    │  │ 分类预测      │  │              │
└──────┬───────┘  └──────┬───────┘  └──────────────┘
       │                 │
       └────────┬────────┘
                ▼
     ┌─────────────────────┐
     │ Data Layer          │
     │                     │
     │ Range库、缓存、统计   │
     └─────────────────────┘

═══════════════════════════════════════════════════════════════
                    横向支撑系统
═══════════════════════════════════════════════════════════════
┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐
│ Trace      │  │ Metrics    │  │ Testing    │  │ Config     │
│ System     │  │ System     │  │ Framework  │  │ Manager    │
│            │  │            │  │            │  │            │
│ 决策追踪    │  │ 性能监控    │  │ A/B测试    │  │ 策略配置    │
└────────────┘  └────────────┘  └────────────┘  └────────────┘
```

---

## 🎨 核心模块详细设计

### 1. Strategy Layer（策略层）

**职责**：核心决策逻辑

**接口定义**：
```python
class IStrategy(ABC):
    @abstractmethod
    def decide(self, ctx: StrategyContext) -> StrategyDecision:
        """基于上下文做出决策"""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """策略名称（用于追踪）"""
        pass
```

**实现类**：
- `GTOStrategy` - GTO基准策略（Range-based）
- `ExploitStrategy` - Exploit策略（基于对手模型调整）
- `HybridStrategy` - 混合策略（动态GTO-Exploit平衡）
- `SolverStrategy` - Solver策略（未来：集成PioSolver等）

**数据结构**：
```python
@dataclass
class StrategyContext:
    """策略决策所需的完整上下文"""
    street: str
    position: Position
    action_history: list[Action]
    pot_size: float
    effective_stack: float
    hero_hand: Hand
    hero_range: Range
    villain_range: Range
    villain_position: Position
    villain_tendencies: Dict[str, float]
    equity_info: EquityInfo
    range_advantage: RangeAdvantage
    board_analysis: BoardAnalysis
    future_streets: Optional[MultiStreetPlan]

@dataclass
class StrategyDecision:
    """策略决策结果（带元数据）"""
    action_distribution: Dict[str, float]
    sizing_distribution: Dict[float, float]
    reasoning: str
    confidence: float
    key_factors: Dict[str, any]
    future_plan: Optional[Dict[str, any]]
```

**关键改进**：
- ✅ 翻前改为**Range-based**（hand在range中的位置，而非绝对hand_strength）
- ✅ 决策返回**分布+元数据**（reasoning, confidence, key_factors用于调试）
- ✅ 支持**Multi-street planning**（考虑未来街道）

---

### 2. Analysis Layer（分析层）

**职责**：Range分析、Equity计算、Board分析

**核心接口**：

```python
class IRangeEngine(ABC):
    @abstractmethod
    def get_ideal_range(self, position: Position, action_history: list) -> Range:
        """获取GTO理论范围"""
        pass

    @abstractmethod
    def get_hand_percentile(self, hand: Hand, range_obj: Range, board: list = None) -> float:
        """Hand在range中的位置（0-1）"""
        pass

    @abstractmethod
    def analyze_range_interaction(self, hero_range: Range, villain_range: Range,
                                  board: list) -> RangeAdvantage:
        """Range vs Range交互分析"""
        pass

class IEquityEngine(ABC):
    @abstractmethod
    def calculate_equity(self, hand: Hand, villain_range: Range, board: list) -> EquityInfo:
        """计算完整equity信息（不只是单点equity）"""
        pass

    @abstractmethod
    def calculate_range_equity(self, hero_range: Range, villain_range: Range, board: list) -> float:
        """Range vs Range equity"""
        pass

class IBoardAnalyzer(ABC):
    @abstractmethod
    def analyze(self, board: list[Card]) -> BoardAnalysis:
        """Board texture分析"""
        pass
```

**数据结构**：
```python
@dataclass
class EquityInfo:
    """完整的equity信息"""
    point_equity: float  # 单点equity
    equity_distribution: Dict[str, float]  # {'crushing': 0.2, 'strong': 0.3, ...}
    equity_vs_calling_range: Optional[float]
    equity_vs_raising_range: Optional[float]
    outs: int
    implied_odds_factor: float

@dataclass
class RangeAdvantage:
    """Range优势分析"""
    advantage_score: float  # -1 到 1
    advantage_type: str  # 'nut', 'range', 'none'
    hero_nut_advantage: float  # 坚果优势
    hero_range_size_ratio: float
    hero_equity_distribution: Dict[str, float]
    villain_equity_distribution: Dict[str, float]
    board_favors: str  # 'hero', 'villain', 'neutral'

@dataclass
class BoardAnalysis:
    """Board分析"""
    board: list[Card]
    texture: str  # 'dry', 'wet', 'dynamic'
    is_paired: bool
    is_monotone: bool
    is_connected: bool
    draw_heavy: bool
    broadway_heavy: bool
    equity_realization_factor: float  # IP vs OOP
```

**关键改进**：
- ✅ Equity不再是单点值，而是**完整的EquityInfo**（包含分布、outs、implied odds）
- ✅ Range advantage考虑**nut advantage + range size + equity分布**
- ✅ Board analysis包含**equity realization factor**（IP vs OOP的实现率差异）

---

### 3. Model Layer（建模层）

**职责**：对手建模、分类、趋势追踪

**接口定义**：
```python
class IOpponentModel(ABC):
    @abstractmethod
    def classify_player(self, player_id: str) -> PlayerType:
        """分类玩家"""
        pass

    @abstractmethod
    def get_profile(self, player_id: str) -> PlayerProfile:
        """获取完整画像"""
        pass

    @abstractmethod
    def update_observation(self, player_id: str, action: Action, context: dict):
        """实时更新观察"""
        pass

    @abstractmethod
    def predict_range(self, player_id: str, position: Position, action_history: list) -> Range:
        """基于profile预测range"""
        pass
```

**数据结构**：
```python
@dataclass
class PlayerProfile:
    """玩家画像"""
    player_id: str
    player_type: PlayerType  # LAG, TAG, LOOSE_PASSIVE, etc.

    # 基础统计
    vpip: float
    pfr: float
    af: float  # Aggression Factor
    wtsd: float

    # 位置统计
    stats_by_position: Dict[Position, Dict[str, float]]

    # 趋势
    cbet_freq_flop: float
    cbet_freq_turn: float
    cbet_freq_river: float
    fold_to_cbet_flop: float
    fold_to_3bet: float
    three_bet_freq: float

    # 样本量和可靠性
    sample_size: int
    hands_observed: int
    confidence: float
```

**关键改进**：
- ✅ **不再返回UNKNOWN**：即使是Random也分类为具体类型（PASSIVE等）
- ✅ **实时更新**：每个action都更新profile
- ✅ **置信度**：根据样本量计算置信度，用于GTO-Exploit平衡

---

### 4. Exploit Layer（Exploit层）

**职责**：基于对手profile计算exploit调整

**接口定义**：
```python
class IExploitEngine(ABC):
    @abstractmethod
    def calculate_adjustment(self, villain_tendencies: Dict, ctx: StrategyContext,
                            gto_baseline: StrategyDecision) -> ExploitAdjustment:
        """计算exploit调整"""
        pass

@dataclass
class ExploitAdjustment:
    """Exploit调整"""
    adjustments: Dict[str, float]  # {'value_bet_freq': +0.15, 'bluff_freq': -0.10, ...}
    reasoning: str
    confidence: float
```

**Exploit策略示例**：
```python
# vs PASSIVE
{
    'value_bet_freq': +0.15,    # 多bet强牌
    'bluff_freq': -0.10,         # 少bluff
    'thin_value': +0.10,         # 扩大value range
    'defense_freq': -0.05        # 少防守
}

# vs LAG
{
    'value_bet_freq': -0.05,
    'bluff_freq': -0.15,
    'defense_freq': +0.15,       # 多防守
    'trap_freq': +0.10           # 增加trap
}

# vs TIGHT
{
    'bluff_freq': +0.20,
    'thin_value': -0.15,
    'steal_freq': +0.15
}
```

---

### 5. Decision Integration Layer（决策整合层）

**职责**：整合所有信息，生成最终决策，提供trace

```python
class DecisionIntegrator:
    def decide(self, game_state: GameState) -> Tuple[Action, DecisionTrace]:
        """完整的决策流程"""

        # Phase 1: Analysis
        hero_range = self.range_engine.get_ideal_range(...)
        villain_range = self.opponent_model.predict_range(...)
        equity_info = self.equity_engine.calculate_equity(...)
        range_advantage = self.range_engine.analyze_range_interaction(...)
        board_analysis = self.board_analyzer.analyze(...)

        # Phase 2: Strategy
        ctx = StrategyContext(...)
        final_decision = self.strategy.decide(ctx)

        # Phase 3: Action selection
        selected_action = self._select_action(final_decision, game_state)

        # Phase 4: Trace
        trace = DecisionTrace(...)
        self.trace_system.record(trace)

        return selected_action, trace
```

**DecisionTrace**（全链路追踪）：
```python
@dataclass
class DecisionTrace:
    trace_id: str
    timestamp: float

    # Input
    game_state: GameState

    # Analysis results
    hero_range: Range
    villain_range: Range
    equity_info: EquityInfo
    range_advantage: RangeAdvantage
    board_analysis: BoardAnalysis

    # Strategy decisions
    gto_decision: Optional[StrategyDecision]
    exploit_decision: Optional[StrategyDecision]
    final_decision: StrategyDecision

    # Selected action
    selected_action: Action

    # Performance
    analysis_time_ms: float
    strategy_time_ms: float
    total_time_ms: float
```

---

## 🔧 横向支撑系统

### 1. Trace System（追踪系统）

**功能**：
- 记录每个决策的完整trace
- 支持查询和过滤
- 可视化决策树

**使用场景**：
```python
# 调试特定位置的决策
traces = trace_system.query({'position': 'BTN', 'street': 'flop'})

# 可视化单个决策
trace_system.visualize(trace_id='abc123')
```

### 2. Metrics System（性能监控）

**功能**：
- 监控延迟（P50, P95, P99）
- 监控胜率（按策略、位置、街道）
- 监控模块性能

**使用场景**：
```python
# 性能报告
report = metrics_system.get_report()
# {
#   'latency_p50': 8.2ms,
#   'latency_p95': 15.3ms,
#   'gto_strategy_winrate': +420 BB/100,
#   'exploit_strategy_winrate': +580 BB/100
# }
```

### 3. Testing Framework（测试框架）

**功能**：
- 单元测试（每个模块独立）
- 集成测试（完整决策流程）
- A/B测试（策略对比）

**使用场景**：
```python
# A/B测试
compare_strategies(
    strategy_a=GTOStrategy(...),
    strategy_b=HybridStrategy(...),
    num_hands=10000,
    opponents=['Random', 'WeakAI', 'Human']
)
```

### 4. Config Manager（配置管理）

**功能**：
- 策略参数配置（threshold、sizing等）
- 动态加载和热更新
- 版本管理

**使用场景**：
```python
# 加载配置
config = ConfigManager.load('gto_config_v2.yaml')

# 动态更新
config.update('open_thresholds.BTN', 0.25)
```

---

## 📊 与当前代码的对比

### 当前架构的问题

| 问题 | 当前代码 | 新架构 |
|------|---------|--------|
| **翻前决策** | 基于hand_strength查表 | Range-based（hand在range中的位置） |
| **Equity使用** | 翻前计算但不用（99%浪费） | 翻前不计算，翻后完整EquityInfo |
| **Exploit layer** | opponent_type=UNKNOWN导致100%死代码 | 始终激活，基于实时profile |
| **Range分析** | 只看size，不看质量 | Nut advantage + equity分布 + board interaction |
| **决策输出** | 单一action | 分布 + 元数据（reasoning, confidence） |
| **可调试性** | 黑盒，无法追踪 | 全链路trace，每个决策可视化 |
| **可测试性** | 模块耦合，难以单测 | 接口隔离，每个模块独立可测 |
| **代码复用** | 70%死代码 | 100%有效代码，可插拔设计 |

### 代码量对比

```
当前：
  advisor/: 5000行（70%死代码）
  有效代码：1500行

新架构：
  advisor/core/interfaces/: 800行（接口定义）
  advisor/strategies/: 1500行（GTO + Exploit + Hybrid）
  advisor/analysis/: 1200行（Range + Equity + Board）
  advisor/modeling/: 800行（对手建模）
  advisor/integration/: 600行（决策整合）
  advisor/support/: 400行（Trace + Metrics）
  Total: 5300行（100%有效代码）
```

---

## 🚀 实施路径

### Phase 1: 核心重构（4-6周）

**Week 1-2: 接口和数据结构**
- [ ] 定义所有核心接口（IStrategy, IRangeEngine, IEquityEngine, etc.）
- [ ] 定义数据结构（StrategyContext, EquityInfo, RangeAdvantage, etc.）
- [ ] 实现基础的DecisionIntegrator框架

**Week 3-4: Analysis Layer**
- [ ] 实现RangeEngine（range管理 + range interaction分析）
- [ ] 实现EquityEngine（完整EquityInfo计算）
- [ ] 实现BoardAnalyzer

**Week 5-6: Strategy Layer**
- [ ] 实现GTOStrategy（Range-based preflop + postflop）
- [ ] 迁移已修复的Phase 1逻辑
- [ ] 集成测试

**验收标准**：
- vs Random: ≥ +400 BB/100
- 决策延迟: P95 < 20ms
- 单元测试覆盖率: > 80%

---

### Phase 2: 对手建模和Exploit（4-6周）

**Week 1-2: Model Layer**
- [ ] 实现OpponentModel（分类 + profile管理）
- [ ] 实现PlayerStorage（持久化）
- [ ] 实现实时趋势追踪

**Week 3-4: Exploit Layer**
- [ ] 实现ExploitEngine（调整计算）
- [ ] 实现ExploitStrategy
- [ ] 实现HybridStrategy（GTO-Exploit平衡）

**Week 5-6: 测试和调优**
- [ ] vs弱AI测试
- [ ] vs不同player type的对手
- [ ] A/B测试（GTO vs Hybrid）

**验收标准**：
- vs Random: ≥ +420 BB/100
- vs弱AI（PASSIVE）: ≥ +550 BB/100
- vs弱AI（LAG）: ≥ +350 BB/100

---

### Phase 3: 高级特性（2-3个月）

**Month 1: Multi-street Planning**
- [ ] 实现multi-street EV计算
- [ ] 集成到策略决策中
- [ ] 测试复杂场景（draw heavy boards）

**Month 2: Solver Integration**
- [ ] 定义SolverInterface
- [ ] 集成PioSolver导出数据
- [ ] 实现SolverStrategy

**Month 3: 深度学习**
- [ ] 训练NN近似器（基于CFR数据）
- [ ] 实现NeuralStrategy
- [ ] 全面测试

**验收标准**：
- vs GTO Bot: 接近平衡（±50 BB/100）
- vs职业选手数据回测: > 0 BB/100

---

## 🎯 技术亮点

### 1. Range-based思维（真正的GTO）
```python
# 不是这样（当前）
if hand_strength >= 0.50:
    raise

# 而是这样（新架构）
percentile = range_engine.get_hand_percentile(hand, hero_range, board)
if percentile >= 0.75:  # Top 25% of our range
    action = 'raise'
elif percentile >= 0.40:  # Middle range
    action = random.choice(['call', 'raise'], p=[0.85, 0.15])
else:
    action = 'fold'
```

### 2. Equity分布（不只是单点）
```python
# 不是这样（当前）
equity = 0.58  # 只有一个数

# 而是这样（新架构）
equity_info = EquityInfo(
    point_equity=0.58,
    equity_distribution={
        'crushing': 0.15,  # vs 15%的villain hands我们碾压
        'strong': 0.30,    # vs 30%我们强势领先
        'ahead': 0.25,     # vs 25%我们微弱领先
        'flip': 0.20,      # vs 20%是flip
        'behind': 0.10     # vs 10%我们落后
    },
    outs=9,
    implied_odds_factor=1.3
)

# 决策时考虑分布
if equity_info.equity_distribution['crushing'] + equity_info.equity_distribution['strong'] >= 0.40:
    # 对villain range的40%有strong+优势
    action = 'value_bet'
```

### 3. Range Advantage（深度分析）
```python
# 不是这样（当前）
if len(hero_range) >= len(villain_range) * 1.2:
    bet_freq += 0.2  # 固定调整

# 而是这样（新架构）
range_adv = range_engine.analyze_range_interaction(hero_range, villain_range, board)
# RangeAdvantage(
#   advantage_score=0.35,
#   advantage_type='nut',  # Hero有坚果优势
#   hero_nut_advantage=0.8,  # Hero拥有80%的nuts
#   hero_range_size_ratio=1.3,
#   board_favors='hero'
# )

if range_adv.advantage_type == 'nut':
    # 坚果优势 → 极化策略（大bet + 高频）
    sizing = 0.75
    bet_freq = 0.65
elif range_adv.advantage_type == 'range':
    # Range优势 → 中等sizing，高频
    sizing = 0.5
    bet_freq = 0.70
```

### 4. 可插拔设计（易于调试和A/B测试）
```python
# 轻松切换策略
advisor = PokerAdvisor(
    strategy=GTOStrategy(...),  # 或ExploitStrategy(...), HybridStrategy(...)
    opponent_model=OpponentModel(...),
    trace_system=TraceSystem(...)
)

# A/B测试
results = compare_strategies(
    strategies=[
        GTOStrategy(config_v1),
        GTOStrategy(config_v2),
        HybridStrategy(...)
    ],
    num_hands=10000
)

# 可视化对比
visualizer.plot_comparison(results)
```

### 5. 全链路Trace（完全可观测）
```python
action, trace = advisor.decide(game_state)

# 查看决策路径
print(trace.reasoning)
# "Value bet: equity 0.68 >= threshold 0.50
#  Range advantage: +0.35 (nut advantage)
#  Board favors: hero
#  Bet frequency: 0.65"

# 查看关键因素
print(trace.final_decision.key_factors)
# {
#   'equity': 0.68,
#   'value_threshold': 0.50,
#   'range_advantage': 0.35,
#   'nut_advantage': 0.80,
#   'bet_frequency': 0.65
# }

# 可视化决策树
trace_system.visualize(trace.trace_id)
```

---

## 📈 预期性能

### vs Random
- **当前（Phase 1 fix）**: +408 BB/100
- **Phase 1（核心重构）**: +420 BB/100（优化sizing）
- **Phase 2（Exploit）**: +450 BB/100

### vs 弱AI
- **Phase 2**: +350 ~ +550 BB/100（取决于对手类型）

### vs GTO Bot
- **Phase 3**: ±50 BB/100（接近平衡）

### 延迟
- **当前**: 翻前52ms，翻后15ms
- **Phase 1**: 翻前5ms（移除浪费的equity计算），翻后8ms（优化）
- **Phase 2**: 翻前6ms，翻后10ms（增加对手建模）

---

## 🎓 总结

### 核心设计理念

```
完整性（方案B）+ 可插拔性（方案C）= 职业级可调试架构

1. Interface Segregation - 每个模块清晰的接口
2. Dependency Injection - 松耦合，易于测试
3. Layered Architecture - 分层架构，职责分离
4. Observability First - 全链路trace，可视化
5. Range-based Thinking - 真正的GTO思维
```

### 与当前架构的根本区别

| 维度 | 当前架构 | 新架构 |
|------|---------|--------|
| **核心思想** | Hand-centric + Threshold | Range-based + Distribution |
| **翻前算法** | Static lookup table | Hand在range中的动态位置 |
| **Equity** | 单点值（翻前浪费） | 完整分布（按需计算） |
| **Range分析** | 只看size | Nut adv + Equity dist + Board |
| **对手建模** | 架空（UNKNOWN） | 实时分类和profile |
| **Exploit** | 死代码 | 基于profile的动态调整 |
| **决策输出** | 单一action | 分布 + reasoning + confidence |
| **可观测性** | 黑盒 | 全链路trace + 可视化 |
| **可测试性** | 耦合 | 接口隔离，模块独立 |

### 这个架构能达到职业级吗？

**Phase 1-2**: 可以达到**中高级玩家水平**（能打赢弱AI和大部分业余玩家）

**Phase 3（+Solver）**: 可以接近**职业选手水平**（GTO基准正确）

**Phase 3（+深度学习）**: 有潜力**超越职业选手**（在特定场景的exploit能力）

**关键**：架构本身不保证性能，但提供了**达到职业级的必要基础**：
- ✅ Range-based thinking
- ✅ 完整的equity分析
- ✅ 对手适应性
- ✅ 可调试、可优化

---

## 下一步

等待你的确认，我可以立即开始：

1. **创建接口定义**（advisor/core/interfaces/）
2. **实现Phase 1的RangeEngine**
3. **实现Phase 1的GTOStrategy**

要开始吗？
