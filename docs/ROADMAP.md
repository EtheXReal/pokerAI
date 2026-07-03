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
Phase 3: 工具化（复盘/分析界面）      ░░░░░░░░░░░░░░░░░░░░    0%
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

## Phase 3: 工具化（远期）

作为**本地研究工具**的收尾：

- 手牌复盘器：读入对局记录，逐街展示 DecisionTrace（范围/equity/决策依据）
- 交互式分析 CLI：手动输入局面，查看 AI 建议与推理
- 统计面板：模拟结果的批量分析与可视化

> 注：原 Phase 3 计划是 OCR 抓取在线扑克平台画面做实时建议。该部分调整为本地工具方向：
> 对真实平台的实时辅助（RTA）无论是否牟利都违反平台服务条款，不适合作为开发目标；
> 项目的核心价值（AI 决策质量、博弈论研究）通过本地模拟与复盘工具即可完整体现。

---

## 关键文档

- [README](../README.md) - 项目概览与快速开始
- [architecture.md](architecture.md) - 现行系统架构
- [future_enhancements.md](future_enhancements.md) - 对手建模高级特性想法
- [archive/](archive/) - 历史设计/调试文档（2025-11 开发期）
