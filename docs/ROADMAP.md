# 项目路线图

> **项目**: 德州扑克 AI 决策系统（个人研究项目，非牟利）
> **最终目标**: 达到职业水平决策质量的扑克 AI，通过模拟对局验证
> **当前阶段**: Phase 2 中期（GTO 基线完成，待接入对手建模）
> **最近更新**: 2026-07（大重构：v1 退役、poker_core 提取、测试全绿）

---

## 📊 整体进度

```
Phase 1: 游戏引擎 (poker_env)         ████████████████████  100%  ✅
Phase 2: AI决策系统 (advisor)         ████████████░░░░░░░░   60%  ⏳
  2.1 范围/Equity/牌面分析            ████████████████████  100%  ✅
  2.2 对手建模                        ████████████████░░░░   80%  ✅代码完成，未接入
  2.3 GTO策略 + 决策编排              ████████████████░░░░   80%  ✅基线可用
  2.4 Exploit混合层                   ░░░░░░░░░░░░░░░░░░░░    0%
  2.5 系统性评估                      ████░░░░░░░░░░░░░░░░   20%  仅vs Random
Phase 3: 数据捕获和UI（所有者自行开发）░░░░░░░░░░░░░░░░░░░░    0%
```

---

## Phase 1: 游戏引擎 ✅ 完成

`poker_env/`：2-10 人 No-Limit Hold'em，完整四街、all-in、边池、最小加注规则。
经 512 手对战模拟与多人边池集成测试验证。

## Phase 2: AI 决策系统 ⏳ 当前阶段

### 已完成

- **2.1 分析层**：RangeEngine（范围表 + hand percentile）、EquityEngine（Monte Carlo + LRU 缓存）、BoardAnalyzer
- **2.2 对手建模**（代码完成，未接入决策链）：20+ 统计指标、9 种玩家分类、exploit 策略库、SQLite 持久化 —— 位于 `advisor/modeling/`
- **2.3 GTO 基线**：GTOStrategy（range percentile 决策）+ DecisionIntegrator（编排 + DecisionTrace）
- **基准成绩**（2026-07，512 手 vs Random，seed=42）：**+191 BB/100**（BTN +265 / BB +118）

### 下一步（按优先级）

1. **接入对手建模 → Exploit 层**（原 Phase 2.2/2.3 的断点，最高价值）
   - 对战循环中用 `StatsTracker` 实时累积对手统计
   - `PlayerClassifier` 分类结果传入 `GameState.opponent_type`
   - 实现 `advisor/exploit/`：根据对手类型调整 GTOStrategy 输出（混合权重）
2. **系统性评估协议**
   - vs 多种风格对手（tight/aggressive/passive/calling station）各 1000+ 手
   - 位置分解 + 置信区间，固定 seed 保证可复现
   - 目标：vs Random +60、vs Fish +45、vs TAG ≥0（BB/100）
3. **翻后范围动态更新**（根据行动序列缩小范围，提高翻后 percentile 精度）
4. **多人桌（3-5人）决策支持**（当前决策链主要在 2 人桌验证）

## Phase 3: 数据捕获和UI（项目所有者自行开发）

**前置条件**: Phase 2 完成

### Phase 3.1: OCR数据捕获
- PokerStars配置文件（区域坐标、52张牌模板图）
- 屏幕截图和预处理、卡牌模板匹配 (OpenCV)、数字OCR (Tesseract)
- 位置和按钮识别、错误处理和容错
- 目标：识别准确率 > 95%，延迟 < 1秒

### Phase 3.2: UI界面
- 桌面悬浮窗：实时显示建议（主要动作/概率分布/牌力评估）、置顶/可调/半透明、设置面板
- CLI测试工具：交互式测试、手动输入局面、查看决策推理

### Phase 3.3: 集成测试
- 端到端流程测试、真实环境验证、性能和稳定性测试

> 注：此阶段由项目所有者自行开发。CLI 交互工具（手动输入局面查看决策推理）属于
> Phase 2 决策系统的本地调试工具，可以协助开发。

---

## 关键文档

- [README](../README.md) - 项目概览与快速开始
- [architecture.md](architecture.md) - 现行系统架构
- [future_enhancements.md](future_enhancements.md) - 对手建模高级特性想法
- [archive/](archive/) - 历史设计/调试文档（2025-11 开发期）
