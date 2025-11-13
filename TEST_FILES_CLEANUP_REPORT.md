# 测试文件梳理报告

## 合格标准（基于 test_advisor_v2_full_postflop.py）
1. ✅ 完整的4个街道决策（preflop → flop → turn → river）
2. ✅ 支持多轮加注（bet → raise → 3-bet → 4-bet...）
3. ✅ 使用advisor_v2架构（DecisionIntegrator + RangeEngine + EquityEngine + BoardAnalyzer + GTOStrategy）
4. ✅ 真实的德州扑克逻辑（不是"翻前决策 → 直接showdown"的假扑克）

---

## 📂 分类汇总

### ✅ 保留 - 合格的测试文件

#### 1. 性能测试（唯一合格）
- **`tests/performance/test_advisor_v2_full_postflop.py`** ⭐
  - 状态：**合格标准**
  - 原因：完整4街道 + 多轮加注 + advisor_v2架构 + 真扑克
  - 用途：advisor_v2的完整性能验证

#### 2. 单元测试（保留 - 有用）
以下是组件级别的单元测试，测试特定功能，应保留：

**advisor_v2 单元测试：**
- `tests/advisor_v2/test_range_engine.py` - 测试RangeEngine
- `tests/advisor_v2/test_gto_strategy.py` - 测试GTOStrategy
- `tests/advisor_v2/test_decision_integrator.py` - 测试DecisionIntegrator

**advisor v1 单元测试（如果还在使用v1）：**
- `tests/advisor/test_equity.py` - Equity计算测试
- `tests/advisor/test_equity_extreme_cases.py` - 极端情况测试
- `tests/advisor/test_hand_vs_range.py` - Hand vs Range equity
- `tests/advisor/test_multiway_equity.py` - 多人底池equity
- `tests/advisor/test_range.py` - Range解析测试
- `tests/advisor/test_range_engine.py` - RangeEngine测试
- `tests/advisor/test_range_vs_range.py` - Range vs Range equity
- `tests/advisor/test_range_plus_notation.py` - Range+标记
- `tests/advisor/test_range_set_operations.py` - Range集合操作
- `tests/advisor/test_ultra_precision.py` - 高精度测试

**其他有用单元测试：**
- `tests/verification/test_bb_raise_vs_limp.py` - BB对limp的反应验证
- `tests/experiments/test_strength_vs_range.py` - 手牌强度实验

---

### ❌ 删除 - 废物测试文件（假扑克）

这些测试只有翻前决策，然后直接showdown，**不是真正的德州扑克**：

#### 根目录废物文件
- ❌ `test_performance.py` - 老的性能测试，advisor v1
- ❌ `test_scenarios.py` - advisor v1场景测试
- ❌ `test_strategy_engine_quick.py` - advisor v1快速测试

#### tests/performance/ 废物文件
- ❌ `test_vs_random_1000hands.py`
  - 问题：**假扑克**（只有翻前 → showdown）
  - 使用：advisor v1 (ProLevelAdvisor)
  - 替代：用 test_advisor_v2_full_postflop.py --hands 1024

- ❌ `test_advisor_v2_vs_random_32hands.py`
  - 问题：**假扑克**（只有翻前 → showdown）
  - 使用：advisor_v2架构
  - 替代：用 test_advisor_v2_full_postflop.py --hands 32

- ❌ `test_advisor_v2_detailed_32hands.py`
  - 问题：**假扑克**（只有翻前 → showdown）
  - 使用：advisor_v2架构
  - 替代：用 test_advisor_v2_full_postflop.py --hands 32 --verbose

- ❌ `test_50hands_detailed.py`
  - 问题：**假扑克**（只有翻前 → showdown）
  - 使用：advisor v1
  - 替代：用 test_advisor_v2_full_postflop.py --hands 50

- ❌ `test_full_postflop_10hands.py`
  - 名字说是"full postflop"但需要检查是否真的是完整翻后
  - 如果也是假扑克，删除

#### tests/advisor/ 可能废弃的测试
- ❌ `test_advisor_scenarios.py` - advisor v1场景测试
- ❌ `test_classifier.py` - 分类器测试（如果不用了）
- ❌ `test_exploits.py` - exploit测试（如果不用了）
- ❌ `test_gto_baseline.py` - GTO baseline（v1）
- ❌ `test_opponent_stats.py` - 对手统计（如果不用了）
- ❌ `test_postflop_accuracy.py` - 翻后准确性（v1）
- ❌ `test_precision_challenge.py` - 精度挑战（v1）
- ❌ `test_storage.py` - 存储测试（如果不用了）
- ❌ `test_strategy_engine.py` - Strategy Engine（v1）
- ❌ `test_tracker.py` - Tracker测试（如果不用了）

#### scripts/ 废物脚本
- ❌ `scripts/test_r_sizing.py` - R sizing测试脚本

---

### ⚠️ 待确认 - 需要检查是否废弃

这些文件需要确认是否还在使用：
- `tests/performance/test_full_postflop_10hands.py` - 检查是否真的是完整翻后
- `tests/advisor/test_classifier.py` - 检查Classifier是否还在用
- `tests/advisor/test_exploits.py` - 检查Exploit是否还在用
- `tests/advisor/test_tracker.py` - 检查Tracker是否还在用
- `tests/advisor/test_storage.py` - 检查Storage是否还在用

---

## 🎯 清理建议

### 立即删除（20+个文件）

**根目录：**
```bash
rm test_performance.py
rm test_scenarios.py
rm test_strategy_engine_quick.py
```

**tests/performance/（假扑克）：**
```bash
rm tests/performance/test_vs_random_1000hands.py
rm tests/performance/test_advisor_v2_vs_random_32hands.py
rm tests/performance/test_advisor_v2_detailed_32hands.py
rm tests/performance/test_50hands_detailed.py
```

**scripts/：**
```bash
rm scripts/test_r_sizing.py
```

**tests/advisor/（advisor v1相关）：**
如果完全迁移到advisor_v2，可以考虑删除整个tests/advisor/目录，或至少删除以下场景测试：
```bash
rm tests/advisor/test_advisor_scenarios.py
rm tests/advisor/test_gto_baseline.py
rm tests/advisor/test_postflop_accuracy.py
rm tests/advisor/test_precision_challenge.py
rm tests/advisor/test_strategy_engine.py
```

### 保留的文件结构

```
tests/
├── advisor/                    # advisor v1单元测试（如果还用v1）
│   ├── test_equity.py          # ✅ 保留 - equity计算
│   ├── test_equity_extreme_cases.py  # ✅ 保留
│   ├── test_hand_vs_range.py   # ✅ 保留
│   ├── test_multiway_equity.py # ✅ 保留
│   ├── test_range*.py          # ✅ 保留 - range相关
│   └── test_ultra_precision.py # ✅ 保留
│
├── advisor_v2/                 # advisor_v2单元测试
│   ├── test_decision_integrator.py  # ✅ 保留
│   ├── test_gto_strategy.py    # ✅ 保留
│   └── test_range_engine.py    # ✅ 保留
│
├── performance/                # 性能测试
│   └── test_advisor_v2_full_postflop.py  # ✅ 保留 - 唯一合格的性能测试
│
├── verification/               # 验证测试
│   └── test_bb_raise_vs_limp.py  # ✅ 保留
│
└── experiments/                # 实验测试
    └── test_strength_vs_range.py  # ✅ 保留
```

---

## 📊 统计

- **总测试文件数：** 35个
- **保留：** 约15个（单元测试 + 1个性能测试）
- **删除：** 约20个（假扑克 + 旧版本 + 废弃脚本）
- **待确认：** 约5个

---

## 💡 使用新测试的方法

旧测试的替代方案：

```bash
# 旧：test_vs_random_1000hands.py --hands 1024 --threads 8
# 新：
python tests/performance/test_advisor_v2_full_postflop.py --hands 1024 --threads 8

# 旧：test_advisor_v2_vs_random_32hands.py
# 新：
python tests/performance/test_advisor_v2_full_postflop.py --hands 32 --threads 4

# 旧：test_advisor_v2_detailed_32hands.py
# 新：
python tests/performance/test_advisor_v2_full_postflop.py --hands 32 --threads 1 --verbose

# 旧：test_50hands_detailed.py
# 新：
python tests/performance/test_advisor_v2_full_postflop.py --hands 50 --threads 1 --verbose
```

优势：
- ✅ 真正的德州扑克（4个街道）
- ✅ 支持多轮加注
- ✅ advisor_v2架构
- ✅ 可配置手数、线程、随机种子
- ✅ 详细的action记录
