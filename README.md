# PokerAI - 德州扑克 AI 决策系统

> Range-based GTO + 对手建模的德州扑克 AI（个人研究项目，非牟利用途）
>
> 目标：构建达到职业水平决策质量的扑克 AI，通过自我博弈模拟验证策略

## 项目状态（2026-07 重构后）

- ✅ 游戏引擎完整（2-10人、四街、all-in、边池）
- ✅ Range-based 决策系统（范围/equity/牌面分析 + GTO 策略）
- ✅ 对手建模（20+ 统计指标、9 种玩家分类、exploit 策略库）——**已实现，待接入决策链**
- ✅ 单元测试 207 个全绿；vs Random 512 手 **+191 BB/100**（BTN +265 / BB +118）
- ⏳ 下一步：将对手建模接入 exploit 层，实现 GTO + Exploit 混合决策

## 架构

```
poker_core/          扑克基础原语（零第三方依赖）
  ├── cards.py       Card / Hand / Board / Rank / Suit
  ├── evaluator.py   7张牌牌型评估
  ├── range.py       Range 表示与集合操作（"22+,A2s+,K9o+"）
  └── position.py    Position / Street 枚举
        ↑
        ├──────────────────────┐
poker_env/                advisor/
  游戏引擎                  AI决策系统
  ├── poker_game.py         ├── core/         数据结构 + 模块接口（GameState 决策入口）
  ├── betting_round.py      ├── analysis/     RangeEngine / EquityEngine / BoardAnalyzer
  ├── side_pot.py           ├── strategy/     GTOStrategy（range percentile 决策）
  └── player.py             ├── modeling/     对手统计/分类/exploit库（原 Phase 2.2 成果）
                            ├── exploit/      GTO-Exploit 混合层（待实现）
                            ├── integration/  DecisionIntegrator（决策编排 + trace）
                            └── data/         翻前范围表 JSON
```

依赖方向：`poker_core ← poker_env / advisor`（advisor 不依赖 poker_env，通过 `GameState` 解耦）

## 快速开始

```bash
# 无第三方运行时依赖，只需 Python 3.10+
pip install pytest  # 测试用

# 单元测试（约3秒）
python -m pytest tests/core tests/modeling tests/advisor -q

# AI vs Random 对战模拟（512手约80秒）
python tests/performance/2player_env_random_test.py --hands 512 --seed 42

# 多人边池集成测试
python tests/performance/multiplayer_sidepot_test.py
```

## 决策流程

```
GameState（局面快照）
   → DecisionIntegrator.decide()
       1. RangeEngine:    hero理想范围 + 对手范围估计 + hand percentile
       2. EquityEngine:   vs 对手范围的 Monte Carlo equity（LRU缓存）
       3. BoardAnalyzer:  牌面结构（干/湿、听牌密度）
       4. GTOStrategy:    基于 range percentile 输出动作分布 + sizing
   → DecisionTrace（含所有中间结果，全链路可追踪）
```

核心理念：**范围思维**——决策不看手牌绝对强度，看它在当前范围中的相对位置（percentile）。

## 目录说明

| 目录 | 内容 |
|------|------|
| `poker_core/` | 基础原语，被 env 和 advisor 共用 |
| `poker_env/` | 游戏引擎（详见 [poker_env/README.md](poker_env/README.md)） |
| `advisor/` | AI 决策系统 |
| `tests/core` `tests/modeling` `tests/advisor` | 单元测试（pytest） |
| `tests/performance/` | 对战模拟脚本（不被 pytest 自动收集） |
| `scripts/` | 对手建模演示脚本 |
| `docs/` | [ROADMAP](docs/ROADMAP.md)、[架构](docs/architecture.md)、[未来增强](docs/future_enhancements.md) |
| `docs/archive/` | 历史分析/调试文档（2025-11 开发期） |

## 历史

项目经历过一次大重构（2026-07）：v1 决策系统（hand strength 阈值决策）因"范围被架空"的根本缺陷被 v2（range-based）取代并删除，同期清理了全部死代码与调试产物。详见 `docs/archive/` 中的分析文档。
