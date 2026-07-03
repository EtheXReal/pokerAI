# 项目路线图

> **项目**: 德州扑克 AI 决策系统（个人研究项目，非牟利）
> **最终目标**: 达到职业水平决策质量的扑克 AI，通过模拟对局验证
> **当前阶段**: Phase 2 中期（GTO 基线完成，待接入对手建模）
> **最近更新**: 2026-07（大重构：v1 退役、poker_core 提取、测试全绿）

---

## 📊 整体进度

```
Phase 1: 游戏引擎 (poker_env)         ████████████████████  100%  ✅
Phase 2: AI决策系统 (advisor)         ████████████████░░░░   80%  ⏳
  2.1 范围/Equity/牌面分析            ████████████████████  100%  ✅
  2.2 对手建模                        ████████████████████  100%  ✅已接入决策链
  2.3 GTO策略 + 决策编排              ████████████████░░░░   80%  ✅基线可用
  2.4 Exploit混合层                   ████████████████░░░░   80%  ✅已实现并验证
  2.5 系统性评估                      ████████████░░░░░░░░   60%  ✅4风格×开关对比
Phase 3: 数据捕获和UI（所有者自行开发）░░░░░░░░░░░░░░░░░░░░    0%
```

---

## Phase 1: 游戏引擎 ✅ 完成

`poker_env/`：2-10 人 No-Limit Hold'em，完整四街、all-in、边池、最小加注规则。
经 512 手对战模拟与多人边池集成测试验证。

## Phase 2: AI 决策系统 ⏳ 当前阶段

### 已完成

- **2.1 分析层**：RangeEngine（范围表 + hand percentile）、EquityEngine（Monte Carlo + LRU 缓存）、BoardAnalyzer
- **2.2 对手建模**（已接入决策链）：20+ 统计指标、9 种玩家分类、exploit 策略库、SQLite 持久化 —— `advisor/modeling/`
- **2.3 GTO 基线**：GTOStrategy（range percentile 决策）+ DecisionIntegrator（编排 + DecisionTrace）
- **2.4 Exploit 层**：ExploitEngine（按对手类型的动作空间调整）+ BalanceCalculator（GTO-Exploit 按样本量加权），管线：对局 → StatsTracker → PlayerClassifier → ExploitEngine
- **2.5 评估协议**：`tests/performance/evaluation_suite.py`（多风格对手 × exploit 开/关对比、位置分解、标准误）

### 基准成绩（2026-07-03，256手×2 duplicate对拆，seed=42，exploit开）

> duplicate对拆：同一副牌AI两边各打一次、配对计分，消除发牌运气。
> ⚠️ 此前所有基准都受"all-in从未被应对"引擎bug污染（all-in底池只结算盲注），
> 已废弃。修复后all-in真实结算整个筹码，方差随之显著变大，
> 单seed数字只是弱信号——下一步需要多seed平均。

| 对手风格 | BB/100 | ±SE | 说明 |
|---------|--------|-----|------|
| aggressive | +39.9 | 87.5 | |
| tight | +30.1 | 46.7 | |
| passive | +18.3 | 13.0 | |
| tag（会看牌） | -1.1 | 29.7 | 从初版-160修复至此 |
| random | -13.8 | 28.8 | 噪声内，待多seed确认 |

历史提交中修复的结构性bug（都在真实对局中暴露）：
- **betting round：all-in后对手从未被要求应对**（用户实战发现"all-in只输1BB"）、
  all-in玩家被误判负、BB option被跳过
- 单挑位置名'BTN/SB'映射失败（BTN一直用MP最紧范围，翻前弃81%）
- 盲注误判为facing bet、BB空范围percentile退化、fold_to_cbet统计从未计算
- 范围收缩对乱打bot失真（现按对手信息量分档）

### 下一步（按优先级）

1. **多 seed 评估**：all-in真实化后方差变大，单seed基准不可靠 → 8+ seed平均
2. **all-in 应对策略**：引擎修复后AI首次面对真实全下压力，需校验/加强
   facing shove 的 equity 阈值与筹码承诺逻辑
3. **基线微调**：vs random 的残余漏损、GTOStrategy sizing 分层
4. **多人桌（3-5人）决策支持**（当前决策链主要在 2 人桌验证）
5. ~~CLI 复盘工具~~ → 已升级实现为 **1v1 人机对战网页**（`webplay/`，含AI决策透视）

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
