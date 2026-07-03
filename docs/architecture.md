# 系统架构

> 2026-07 重构后的现行架构。原始五层设计文档见 [archive/ULTIMATE_ARCHITECTURE_DESIGN.md](archive/ULTIMATE_ARCHITECTURE_DESIGN.md)。

## 包结构与依赖方向

```
                    poker_core（基础原语，零依赖）
                    Card/Hand/Board/Range/HandEvaluator/Position
                         ↑                    ↑
              poker_env（游戏引擎）      advisor（AI决策系统）
```

- `poker_core` 不依赖任何东西（纯 Python，无第三方库）
- `poker_env` 与 `advisor` 互不依赖；对战测试中通过适配器把 `poker_env.GameState` 转换为 `advisor.core.data_structures.GameState`

## poker_env - 游戏引擎

| 模块 | 职责 |
|------|------|
| `poker_game.py` | 整手牌流程：发牌 → 四条街 → 摊牌 → 分池 |
| `betting_round.py` | 单条街的下注轮：行动顺序、合法动作校验、最小加注规则 |
| `side_pot.py` | 多人 all-in 的边池计算与分配 |
| `player.py` | 玩家抽象接口（`decide(game_state) → PlayerAction`） |
| `utils.py` | 座位/位置/金额取整工具 |

特性：2-10 人、完整 all-in 逻辑、raise-to 语义（含盲注）、随机种子可控。
详见 [poker_env/ARCHITECTURE.md](../poker_env/ARCHITECTURE.md)。

## advisor - AI 决策系统

### 分层

```
DecisionIntegrator（integration/）─ 决策编排 + DecisionTrace 可观测性
     │
     ├── Analysis 层（analysis/）
     │    ├── RangeEngine    范围管理：理想范围、对手范围估计、hand percentile
     │    ├── EquityEngine   Monte Carlo equity（vs range，LRU 缓存）
     │    └── BoardAnalyzer  牌面结构分析
     │
     ├── Strategy 层（strategy/）
     │    └── GTOStrategy    基于 range percentile 的动作分布 + sizing
     │
     ├── Modeling 层（modeling/）        ← 已实现，待接入决策链
     │    ├── stats.py       VPIP/PFR/AF 等 20+ 指标
     │    ├── tracker.py     实时统计更新
     │    ├── classifier.py  9 种玩家类型分类
     │    ├── exploits.py    针对各类型的 exploit 策略库
     │    └── storage.py     SQLite 持久化
     │
     ├── Exploit 层（exploit/）          ← 待实现：GTO-Exploit 混合
     │
     └── core/
          ├── data_structures.py  GameState（决策输入）、StrategyContext、
          │                       EquityInfo、RangeAdvantage、DecisionTrace 等
          └── interfaces/         各层的抽象接口（IStrategy、IRangeEngine...）
```

### 核心决策理念：范围思维

v1 系统的致命缺陷是用绝对 hand strength 阈值做决策（导致 BTN 位置 -320 BB/100）。
现行系统基于 **range percentile**：

1. 查表得到当前局面 hero 的 GTO 理想范围（`advisor/data/preflop_ranges.json`）
2. 计算手牌在该范围中的相对位置（percentile = 1 - 严格更强组合数/总数）
3. percentile 高 → value 动作；中 → call/check；低/不在范围 → fold
4. 翻后用当前成牌强度在范围内重新排序

### 数据流

```
GameState → DecisionIntegrator.decide()
  1. RangeEngine.get_ideal_range(position, history)      → hero理想范围
  2. RangeEngine.estimate_villain_range(...)              → 对手范围
  3. EquityEngine.calculate_equity(hand, villain_range)   → EquityInfo
  4. RangeEngine.get_hand_percentile(hand, range, board)  → 相对位置
  5. BoardAnalyzer.analyze(board)                         → 牌面结构
  6. GTOStrategy.decide(StrategyContext)                  → 动作分布+sizing
  → DecisionTrace（所有中间结果可追踪）
```

## 测试体系

| 位置 | 类型 | 运行 |
|------|------|------|
| `tests/core` | poker_core 单元测试 | pytest，秒级 |
| `tests/modeling` | 对手建模单元测试 | pytest，秒级 |
| `tests/advisor` | 决策系统单元测试（含 EquityEngine 精度测试） | pytest，秒级 |
| `tests/performance` | 端到端对战模拟（AI vs 可配置对手） | 手动运行脚本 |

对战模拟输出写入 `test_results/`（gitignored）。

## 遗留说明

- v1 决策系统（`advisor/strategy_engine` 的 ProLevelAdvisor 等）已于 2026-07 删除，
  其中有价值的部分已迁移：对手建模 → `advisor/modeling/`，基础原语 → `poker_core/`
- `advisor/config`、`advisor/support`、`advisor/strategies` 目前是预留空壳
- 历史调试分析见 `docs/archive/`
