# Phase 2 开发概览 - 职业级AI决策系统

> **目标**: 构建达到/超越职业选手水平的德州扑克AI
> **时间**: 11-15周
> **核心**: 范围思维 + 对手建模 + GTO&Exploitative混合

---

## 📊 总体规划

```
Phase 2.1: 范围引擎          ████████░░░░  (3-4周)  [基础层]
Phase 2.2: 对手建模          ██████░░░░░░  (2-3周)  [中间层]
Phase 2.3: 策略引擎          ██████████░░  (4-5周)  [决策层]
Phase 2.4: 测试验证          ██████░░░░░░  (2-3周)  [质量保证]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
总计:                       ████████████  (11-15周)
```

---

## 🎯 Phase 2.1: 范围引擎 (3-4周)

### 为什么这是基础？

职业选手不会想"我拿AK怎么打"，而是想：
- "我的范围在这个牌面对对手范围有多少优势？"
- "对手会用什么范围在CO位open raise？"
- "翻牌圈他c-bet后，他的范围变成了什么？"

**范围引擎提供这些核心能力。**

### 核心交付物

#### Week 1-2: 范围数据库和基础框架

**1. 完整5人桌范围表**
```python
PREFLOP_RANGES_5MAX = {
    'UTG': {
        'tight': ['AA','KK','QQ',...],      # 8% 范围
        'normal': [...],                     # 12% 范围
        'loose': [...],                      # 15% 范围
    },
    'MP': {...},
    'CO': {...},
    'BTN': {...},
    'SB': {...},
    'BB': {...}  # 特殊：防守范围
}

THREE_BET_RANGES = {
    'value': {...},      # 价值3-bet
    'bluff': {...},      # 诈唬3-bet
    'polarized': {...},  # 极化3-bet
}
```

**2. Range类和操作**
```python
class Range:
    """范围类：管理手牌组合集合"""

    def __init__(self, combos: List[str])
    def remove_conflicting(self, known_cards) -> Range
    def filter_by_strength(self, threshold: float) -> Range
    def equity_vs_range(self, villain_range: Range, board) -> float
    def to_percentage(self) -> float
```

**3. 公共牌分析**
```python
class BoardAnalyzer:
    """分析公共牌结构"""

    def analyze_texture(self, board) -> Dict:
        # 返回：干燥/连牌/同花/高牌...

    def range_advantage(self, range1, range2, board) -> float:
        # 哪个范围在这个牌面更强
```

#### Week 3-4: 范围推断算法

**关键功能：根据行动推断对手范围**

```python
class RangeEstimator:
    """范围推断引擎"""

    def estimate_open_range(self, position, player_type) -> Range:
        # Nit在UTG open = 8%范围
        # LAG在BTN open = 45%范围

    def update_postflop(self, current_range, action, board) -> Range:
        # 对手c-bet → 缩小范围
        # 对手check → 移除最强牌
        # 对手大注 → 极化范围
```

**示例流程**：
```
初始: 对手CO open raise → 假设22%范围

翻牌K♠7♦3♣，对手c-bet 60%:
  → 移除完全air
  → 保留K+, 超对, 听牌
  → 新范围：约18%

转牌T♥，对手check:
  → 移除KK, AA (他们会bet)
  → 移除完全air
  → 新范围：约12% (中等强度)

河牌2♠，对手bet 75%:
  → 极化：两对+ 或 bluff
  → 新范围：约6%
```

### 测试目标

- [ ] 范围定义combo数量正确
- [ ] Equity计算与PokerStove一致 (±2%)
- [ ] 公共牌分类准确率 > 95%
- [ ] 范围推断与专家判断一致率 > 80%

---

## 🎭 Phase 2.2: 对手建模引擎 (2-3周)

### 为什么需要对手建模？

同样的牌，对不同对手打法完全不同：
- **对Fish**: 绝不bluff，薄价值下注
- **对Nit**: 大量偷池，尊重他的下注
- **对LAG**: 宽范围call down，trap
- **对Maniac**: 让他自杀，bluff catch

**对手建模让AI有针对性地exploit对手弱点。**

### 核心交付物

#### Week 1: 统计追踪系统

**实时追踪对手数据**：
```python
class OpponentStats:
    vpip: float = 0.0          # 入池率 (主动投钱%)
    pfr: float = 0.0           # 翻前加注率
    af: float = 0.0            # 激进度
    three_bet_pct: float = 0.0 # 3-bet频率
    cbet_flop: float = 0.0     # 翻牌c-bet频率
    fold_to_cbet: float = 0.0  # 对c-bet弃牌率
    wtsd: float = 0.0          # 摊牌率
    w_sd: float = 0.0          # 摊牌胜率
    # ... 20+ 统计指标
```

**持久化存储**：
- SQLite数据库
- 按玩家ID存储历史数据
- 跨session累积统计

#### Week 2: 对手分类器

**9种玩家类型**：

```
              Passive       Balanced      Aggressive
Tight         Nit          TAG           (罕见)
Medium        Calling St.  Solid Reg     LAG
Loose         Fish         LAP           Maniac
```

**分类算法**：
```python
def classify_opponent(stats: OpponentStats) -> Tuple[str, float]:
    """
    返回：(类型, 置信度)

    示例：
    VPIP=38%, PFR=8%, AF=0.8
      → ('Fish', 0.92)

    VPIP=24%, PFR=19%, AF=3.2
      → ('TAG', 0.85)
    """
```

**置信度系统**：
```
30手以下:   置信度 0.3  (观察中)
30-50手:    置信度 0.6  (初步判断)
50-100手:   置信度 0.8  (较可靠)
100手以上:  置信度 1.0  (高度可靠)
```

#### Week 3: Exploitative策略库

**针对每种类型的Exploit方案**：

```python
EXPLOIT_STRATEGIES = {
    'Fish': {
        'bluff_frequency': 0.0,      # ⚠️ 绝不bluff
        'value_bet_thin': True,      # ✅ 极薄价值下注
        'value_bet_sizing': 0.8,     # ✅ 大尺寸
        'isolate_freq': 0.8,         # ✅ 高频隔离
    },

    'Nit': {
        'steal_frequency': 0.8,      # ✅ 高频偷盲
        'bluff_frequency': 0.4,      # ✅ 较高bluff
        'fold_to_aggression': 0.7,   # ✅ 他激进时多弃牌
    },

    'LAG': {
        'call_down_light': True,     # ✅ 宽范围call
        'slowplay_freq': 0.2,        # ✅ 增加慢打
        'bluff_frequency': 0.15,     # 减少bluff
    },

    'Maniac': {
        'fold_to_aggression': 0.2,   # ✅ 他bluff多，少弃牌
        'call_down_light': True,     # ✅ bluff catch
        'slowplay_freq': 0.3,        # ✅ 经常trap
    }
}
```

### 测试目标

- [ ] 统计计算准确性100%
- [ ] 50手后分类准确率 > 85%
- [ ] 数据持久化完整性
- [ ] Exploit策略方向正确性

---

## 🧠 Phase 2.3: 动态策略引擎 (4-5周)

### 整合三层，输出最终决策

```
范围引擎: 我们有范围优势吗？
    ↓
对手建模: 对手是什么类型？有什么弱点？
    ↓
策略引擎: 综合决策 = GTO基线 + Exploitative调整
    ↓
输出: {'fold': 0.05, 'call': 0.25, 'r66': 0.50, ...}
```

### 核心交付物

#### Week 1-2: GTO基线策略

**翻前GTO近似**：
```python
基于位置和范围的平衡策略：
- UTG: 紧范围，少bluff
- BTN: 宽范围，多偷盲
- 3-bet频率基于位置和对手位置
- 防守范围基于pot odds
```

**翻后基于equity的策略**：
```python
决策因素：
1. 我方范围equity vs 对手范围
2. 位置优势
3. SPR (筹码底池比)
4. MDF (最小防守频率) = pot/(pot+bet)

c-bet频率 = f(范围优势, 位置, 公共牌结构)
bluff频率 = risk / (risk + reward)
```

**多人底池调整**：
```python
调整规则：
- Equity打折: 需要击败多人
- Bluff频率大幅降低
- 下注尺寸增加 (保护+从多人获利)
- 隐含赔率增加
```

#### Week 3: Exploitative策略整合

**GTO + Exploit混合**：
```python
final_strategy = (
    GTO_baseline * (1 - exploit_weight) +
    Exploitative_adjustment * exploit_weight
)

exploit_weight = min(
    opponent_deviation * confidence * user_setting,
    0.7  # 最多偏离GTO 70%
)
```

**动态aggression调整**：
```python
aggression_level = f(
    范围优势,      # +25%
    对手类型,      # +20%
    位置,          # +25%
    SPR,           # +15%
    历史互动       # +15%
)

例子：
- 我有范围优势 + 好位置 + 对Nit
  → 高aggression，多bluff

- 对手是Calling Station
  → 低aggression，不bluff，薄价值
```

#### Week 4-5: 集成和优化

**端到端流程**：
```python
class ProLevelAdvisor:
    def advise(self, game_state: Dict) -> Dict:
        # 1. 推断范围
        hero_range = self.range_engine.estimate_hero_range(...)
        villain_ranges = self.range_engine.estimate_villain_ranges(...)

        # 2. 分析对手
        opponent_profiles = self.opponent_model.classify_opponents(...)

        # 3. 计算范围equity
        equity = self.range_engine.calculate_equity(
            hero_range, villain_ranges, board
        )

        # 4. GTO基线
        gto_strategy = self.strategy_engine.gto_baseline(
            game_state, equity, hero_range, villain_ranges
        )

        # 5. Exploitative调整
        exploits = self.strategy_engine.get_exploits(opponent_profiles)

        # 6. 混合策略
        final_strategy = self.strategy_engine.blend(
            gto_strategy, exploits, weights
        )

        return {
            'action_probs': final_strategy,
            'recommended_action': max(final_strategy, key=...),
            'reasoning': {...}
        }
```

**性能优化**：
- 目标: <100ms
- 缓存常用计算
- 并行处理多个对手
- 优化equity计算

### 测试目标

- [ ] 决策延迟 < 100ms (99分位)
- [ ] 内存稳定 (无泄漏)
- [ ] 策略平衡性 (自博弈接近0)
- [ ] Exploit有效性 (vs各类型胜率提升)

---

## ✅ Phase 2.4: 测试与验证 (2-3周)

### 多维度质量验证

#### 1. 单元测试和集成测试

```python
# 单元测试
test_range_operations()          # Range类功能
test_equity_calculation()        # Equity精度
test_opponent_classification()   # 分类准确性
test_strategy_generation()       # 策略生成

# 集成测试
test_end_to_end_decision()      # 完整决策流程
test_multiway_handling()         # 多人底池
test_error_handling()            # 异常处理
test_performance()               # 性能benchmark
```

#### 2. 对局模拟 (10,000手)

**vs 不同对手类型**：
```
ProAdvisor vs Random
  期望: +60 BB/100
  实际: _____

ProAdvisor vs Fish
  期望: +45 BB/100
  实际: _____

ProAdvisor vs Nit
  期望: +25 BB/100
  实际: _____

ProAdvisor vs TAG
  期望: 0~+5 BB/100
  实际: _____

ProAdvisor vs LAG
  期望: +10 BB/100
  实际: _____

ProAdvisor vs Maniac
  期望: +35 BB/100
  实际: _____

ProAdvisor 自博弈
  期望: 0 BB/100 (±3)
  实际: _____
```

#### 3. 典型场景测试 (50+场景)

**专家标注场景**：
```
场景1: 翻前UTG open AK, facing BTN 3-bet
  专家建议: 4-bet (70%), call (30%)
  AI输出: _____
  一致性: _____

场景2: 翻牌圈顶对面对大注
  专家建议: call (60%), raise (40%)
  AI输出: _____
  一致性: _____

...

总体一致率: _____ (目标 >75%)
```

#### 4. Exploitative测试

**验证exploit是否有效**：
```
场景: vs Fish，river拿中对
  GTO策略: check (60%), bet (40%)
  Exploit策略: bet (80%) [薄价值]

  验证: 运行1000次
  GTO EV: _____
  Exploit EV: _____ (应该更高)
```

#### 5. 职业玩家评审

**邀请职业玩家试用**：
- 提供CLI测试工具
- 收集反馈问卷
- 典型场景盲测
- 整体评分 (目标 >7/10)

### 交付文档

```markdown
# Phase 2 测试报告

## 1. 单元测试
- 覆盖率: _____
- 通过率: _____

## 2. 对局模拟
- vs Random: _____ BB/100
- vs Fish: _____ BB/100
- vs TAG: _____ BB/100
...

## 3. 场景测试
- 总场景数: 50
- 一致率: _____%

## 4. 性能
- 平均延迟: _____ms
- 99分位延迟: _____ms
- 内存占用: _____MB

## 5. 专家评审
- 参与人数: _____
- 平均评分: _____ / 10
- 主要反馈: ...

## 6. 成功标准达成情况
- [x] vs Random: +60 BB/100
- [ ] vs Fish: +45 BB/100
- ...

## 7. 已知问题和限制
- ...

## 8. 后续优化建议
- ...
```

---

## 📈 成功标准总结

### 必达标准 (P0)

- [ ] vs Random: +60 BB/100
- [ ] vs Fish: +45 BB/100
- [ ] 决策延迟 < 100ms
- [ ] 无内存泄漏
- [ ] 对手分类准确率 > 85% (50手后)

### 期望标准 (P1)

- [ ] vs TAG: 0~+5 BB/100
- [ ] 典型场景一致率 > 75%
- [ ] 职业玩家评分 > 7/10
- [ ] 自博弈接近0 (±3 BB/100)

### 加分标准 (P2)

- [ ] vs所有类型都盈利
- [ ] 场景一致率 > 85%
- [ ] 职业玩家评分 > 8/10

---

## 🚀 开始Phase 2.1

**下一步**: 创建范围引擎的基础框架

```bash
mkdir -p advisor/range_engine
mkdir -p advisor/opponent_modeling
mkdir -p advisor/strategy_engine
mkdir -p tests/advisor
```

**第一个任务**: 定义5人桌翻前范围表

准备好开始了吗？
