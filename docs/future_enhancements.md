# 未来增强特性 (Future Enhancements)

本文档记录了对手建模系统的高级特性想法，暂时搁置但值得未来探索。

---

## 🎯 高优先级增强

### 1. 长期记忆 vs 短期记忆 (时间加权统计)

#### 问题描述
当前系统对所有手牌赋予相同权重，无法捕捉玩家风格的**近期变化**。

**现实场景**:
```
前60手: 玩家打得很TAG (VPIP=22%, PFR=18%)
后20手: 突然疯狂 (连续all-in, VPIP=100%)

当前系统:
  综合VPIP = 38.3%  ← 平均值，丢失了"最近疯狂"的信息

理想系统:
  长期VPIP = 22%
  短期VPIP = 100%
  风格变化警告: "玩家可能在tilt！"
```

#### 常见触发场景
- **Tilt (情绪失控)**: 输了大底池后开始乱打
- **时间压力**: 要离开了，最后几手随便玩
- **策略调整**: 发现对手很紧，开始疯狂偷盲
- **对局阶段**: 锦标赛不同阶段打法不同

#### 可能的实现方案

##### 方案A: 双轨统计 (推荐)
```python
class OpponentStats:
    # 长期统计 (所有手牌)
    long_term_stats = {
        'vpip': 0.28,
        'pfr': 0.22,
        'af': 2.3,
    }

    # 短期统计 (最近N手，建议N=20)
    recent_window_size = 20
    recent_hands: deque(maxlen=20)  # 存储最近20个HandResult
    recent_stats = {
        'vpip': 0.45,  # 最近突然升高
        'pfr': 0.35,
        'af': 4.2,
    }

    # 风格变化检测
    def detect_style_shift(self) -> Optional[str]:
        """检测风格剧变"""
        if len(self.recent_hands) < 10:
            return None  # 样本不足

        vpip_diff = abs(self.recent_stats['vpip'] - self.long_term_stats['vpip'])

        if vpip_diff > 0.20:
            if self.recent_stats['vpip'] > self.long_term_stats['vpip']:
                return "LOOSER" # 变松了 (可能tilt)
            else:
                return "TIGHTER"  # 变紧了 (可能收手)

        return None

    # 综合判断 (加权平均)
    def get_effective_vpip(self, recency_weight=0.7) -> float:
        """
        获取加权VPIP

        Args:
            recency_weight: 最近手牌的权重 (0.0-1.0)
                           0.7 = 70%权重给最近20手
        """
        if len(self.recent_hands) >= 10:
            return (
                recency_weight * self.recent_stats['vpip'] +
                (1 - recency_weight) * self.long_term_stats['vpip']
            )
        else:
            return self.long_term_stats['vpip']
```

**优点**:
- ✅ 实现简单
- ✅ 能检测明显的风格变化
- ✅ 可调节权重

**缺点**:
- ⚠️ 需要存储最近N手的数据 (违背增量更新原则)
- ⚠️ 增加内存占用: 每玩家 +20 × HandResult

##### 方案B: 指数移动平均 (EMA)
```python
class OpponentStats:
    vpip: float = 0.0
    alpha: float = 0.1  # 衰减因子 (0.05-0.2)

    def update_vpip_ema(self, did_vpip: bool):
        """
        使用EMA更新VPIP

        新值权重 = alpha
        旧值权重 = 1 - alpha

        alpha=0.1 → 最近10手影响约63%
        alpha=0.05 → 最近20手影响约63%
        """
        new_value = 1.0 if did_vpip else 0.0
        self.vpip = self.alpha * new_value + (1 - self.alpha) * self.vpip
```

**优点**:
- ✅ 完全增量更新，不存储历史
- ✅ 平滑过渡，不会突变
- ✅ 类似金融领域的成熟技术

**缺点**:
- ⚠️ 无法区分"长期"和"短期"
- ⚠️ 参数调优困难 (alpha多大合适？)
- ⚠️ 早期手数少时不准

##### 方案C: 时间窗口对比
```python
class OpponentStats:
    stats_windows = {
        'all': {...},         # 所有手牌
        'last_100': {...},    # 最近100手
        'last_50': {...},     # 最近50手
        'last_20': {...},     # 最近20手
    }

    def get_trend_analysis(self):
        """分析统计趋势"""
        return {
            'vpip_trend': [
                self.stats_windows['all']['vpip'],      # 0.28
                self.stats_windows['last_100']['vpip'], # 0.30
                self.stats_windows['last_50']['vpip'],  # 0.35
                self.stats_windows['last_20']['vpip'],  # 0.50 ← 明显上升!
            ],
            'interpretation': "玩家VPIP持续上升，可能tilt或策略调整"
        }
```

**优点**:
- ✅ 能看到清晰的趋势变化
- ✅ 多个时间窗口提供不同视角

**缺点**:
- ⚠️ 内存占用大 (需要维护多个统计对象)
- ⚠️ 计算复杂度高

#### 推荐方案

**阶段1 (MVP)**: 方案A - 双轨统计
- 实现长期 + 短期(20手) 两个统计
- 提供风格变化警告
- 简单实用

**阶段2 (优化)**: 在方案A基础上加入EMA
- 长期统计用EMA平滑
- 短期统计用滑动窗口
- 两者结合

#### 实现复杂度估计
- **开发时间**: 2-3天
- **测试时间**: 1天
- **新增代码**: ~300行
- **内存增加**: 每玩家 +2KB (20个HandResult)

---

## 🎯 中优先级增强

### 2. 摊牌手牌分析 (Showdown Hand Strength Profiling)

#### 问题描述
当前系统只统计**行为频率** (他多少次下注、加注)，不分析**手牌强度与行为的关系**。

**现实场景**:
```
观察到的摊牌:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
手牌1:
  公共牌: K♠7♦2♣ (干燥高牌面)
  玩家下注: 15BB (2/3 pot)
  摊牌: A♠K♣ (顶对顶踢脚) ← 价值下注

手牌2:
  公共牌: J♥9♦3♠ (中等连牌面)
  玩家下注: 12BB (pot)
  摊牌: 7♠6♠ (完全air!) ← 纯诈唬

手牌3:
  公共牌: Q♣Q♦5♥ (对子面)
  玩家只是跟注
  摊牌: A♥A♦ (超对) ← 慢打陷阱

分析:
1. 他在干燥面会用顶对价值下注 (正常)
2. 他会用air诈唬，且尺寸较大 (激进)
3. 他拿超强牌会慢打 (可exploitable!)
```

#### 核心价值

职业玩家的思考:
> "我不只想知道他多少次下注 (频率)，
> 我想知道他**拿什么牌**会下注 (范围)。"

**当前系统**:
```
C-bet频率: 65%
→ 知道他65%的时候会c-bet
→ 但不知道他用什么牌c-bet
```

**理想系统**:
```
C-bet范围推断:
  在干燥面: 顶对+, 超对, A高 (65%范围)
  在湿面: 两对+, 同花听牌, 顺子听牌 (45%范围)

下注尺寸倾向:
  价值牌: 0.6-0.8 × pot
  诈唬牌: 0.8-1.2 × pot (尺寸偏大!)

慢打倾向:
  超强牌 (暗三+) 有30%概率慢打
```

#### 数据收集

需要记录每次摊牌:
```python
@dataclass
class ShowdownRecord:
    """单次摊牌记录"""
    hand_id: str
    street: StreetType         # 哪条街摊牌
    board: List[str]           # 公共牌 (5张)
    hero_hand: Tuple[str, str] # 对手底牌 (2张)

    # 牌力评估
    hand_rank: int             # 1=高牌, 2=对子, ..., 9=同花顺
    hand_strength_category: str # "air", "weak_pair", "top_pair",
                               # "two_pair", "trips", "overpair"

    # 牌面特征
    board_texture: str         # "dry", "wet", "paired"
    board_high_card: str       # "K" (最高公牌)

    # 行动历史
    actions_taken: List[ActionRecord]  # 他在这手做了什么
    final_action: str          # "bet", "raise", "call", "check"
    final_bet_size: float      # 如果下注，多大
    pot_size_at_action: float  # 当时底池

    # 结果
    won: bool                  # 是否赢得底池


class OpponentStats:
    showdown_records: List[ShowdownRecord] = field(default_factory=list)

    # 摊牌次数限制 (避免内存爆炸)
    max_showdown_records: int = 50
```

#### 可能的分析

##### 分析1: 价值下注范围
```python
def analyze_value_bet_range(self, board_texture='dry'):
    """分析在特定牌面的价值下注范围"""

    # 筛选: 干燥面 + 他下注了 + 摊牌
    records = [
        r for r in self.showdown_records
        if r.board_texture == board_texture
        and r.final_action in ['bet', 'raise']
    ]

    # 按手牌强度分组
    by_strength = defaultdict(list)
    for r in records:
        by_strength[r.hand_strength_category].append(r.final_bet_size / r.pot_size)

    return {
        'top_pair': {
            'frequency': len(by_strength['top_pair']) / len(records),
            'avg_size': mean(by_strength['top_pair']),  # 平均0.65×pot
        },
        'air': {
            'frequency': len(by_strength['air']) / len(records),
            'avg_size': mean(by_strength['air']),  # 平均0.85×pot (诈唬更大!)
        }
    }
```

##### 分析2: 慢打倾向
```python
def analyze_slowplay_tendency(self):
    """分析慢打倾向"""

    # 筛选: 拿超强牌的情况
    strong_hands = [
        r for r in self.showdown_records
        if r.hand_strength_category in ['trips', 'straight', 'flush', 'full_house']
    ]

    # 统计: 有多少次慢打 (check/call)
    slowplayed = [
        r for r in strong_hands
        if r.final_action in ['check', 'call']
    ]

    slowplay_rate = len(slowplayed) / len(strong_hands) if strong_hands else 0

    return {
        'slowplay_rate': slowplay_rate,  # 0.30 = 30%慢打
        'sample_size': len(strong_hands),
        'recommendation': (
            "警惕他的check，可能有陷阱"
            if slowplay_rate > 0.25
            else "他不太慢打，可以偷"
        )
    }
```

##### 分析3: 诈唬尺寸模式
```python
def analyze_bluff_sizing(self):
    """分析诈唬下注尺寸"""

    # 筛选: 他下注了 + 摊牌是垃圾牌
    bluffs = [
        r for r in self.showdown_records
        if r.final_action in ['bet', 'raise']
        and r.hand_strength_category in ['air', 'weak_pair']
    ]

    if not bluffs:
        return None

    bet_sizes = [r.final_bet_size / r.pot_size for r in bluffs]

    return {
        'avg_bluff_size': mean(bet_sizes),      # 0.85×pot
        'min_bluff_size': min(bet_sizes),       # 0.50×pot
        'max_bluff_size': max(bet_sizes),       # 1.50×pot
        'pattern': (
            "他诈唬喜欢下大注" if mean(bet_sizes) > 0.75
            else "他诈唬尺寸正常"
        )
    }
```

#### 实现复杂度

**数据收集**: 中等 (2天)
- 需要接入牌力评估器 (已有treys库)
- 需要牌面分类算法
- 需要摊牌数据解析

**分析算法**: 中等 (3天)
- 统计分析逻辑
- 范围推断启发式
- 可视化输出

**测试验证**: 困难 (2天)
- 数据稀疏性问题 (100手可能只摊牌5次)
- 需要大量真实数据验证

**总计**: 7-10天

#### 限制和挑战

⚠️ **数据稀疏性**:
```
问题: 玩家不常摊牌
  - 100手牌可能只摊牌 5-10次
  - 特定场景 (干燥面 + 顶对) 可能只有1-2个样本

解决: 需要累积足够数据
  - 至少200-300手
  - 或者跨session累积
```

⚠️ **样本偏差**:
```
问题: 摊牌的手牌不代表整体范围
  - 去摊牌的往往是中等强度牌
  - 很强的牌可能对手弃牌了 (没摊牌)
  - 诈唬成功的也没摊牌

结论: 只能看到"冰山一角"
```

⚠️ **推断难度**:
```
问题: 从有限样本推断整体范围很难
  - 看到他用A高诈唬1次 ≠ 他总是用A高诈唬
  - 需要贝叶斯推断、范围构建等高级技术

这是PhD级别的研究课题
```

#### 推荐实现路径

**阶段1 (基础)**: 记录摊牌数据
- 存储ShowdownRecord
- 基础统计 (摊牌次数、胜率)
- 手牌强度分布

**阶段2 (中级)**: 简单分析
- 慢打倾向
- 诈唬尺寸模式
- 价值牌vs诈唬牌比例

**阶段3 (高级)**: 范围推断
- 基于历史摊牌推断当前范围
- 贝叶斯更新
- 与GTO范围对比

---

## 🎯 低优先级增强

### 3. 位置相关的细分统计

当前系统有`PositionStats`但未充分利用。

**增强**:
- 分析玩家在不同位置的打法差异
- 识别"位置感"差的玩家 (在EP和BTN打法相同)

### 4. 多人底池行为分析

当前系统主要针对单挑或简单场景。

**增强**:
- 多人底池中的打法 (更保守？)
- 是否会squeeze (挤压加注)
- 对多人下注的反应

### 5. 街道间的一致性分析

**增强**:
- 翻牌check，转牌突然下注 (delayed c-bet)
- 翻牌下注，转牌放弃 (give up)
- 连续三条街下注 (triple barrel)

---

## 📊 优先级总结

| 特性 | 价值 | 复杂度 | ROI | 推荐阶段 |
|------|------|--------|-----|---------|
| 长期vs短期统计 | 高 | 中 | 高 | Phase 2.3 或 Phase 3 |
| 摊牌手牌分析 | 中 | 高 | 中 | Phase 3 或 Phase 4 |
| 位置细分 | 低 | 低 | 低 | Phase 4 |
| 多人底池 | 中 | 中 | 中 | Phase 3 |
| 街道一致性 | 低 | 中 | 低 | Phase 4 |

---

## 🤔 与现有系统的关系

### 当前系统 (Phase 2.2 Week 1)

```
已实现:
✅ 基础统计 (VPIP, PFR, AF, 3-bet%, C-bet%)
✅ 增量更新算法
✅ 多玩家追踪
✅ 序列化支持

能力:
→ 识别Fish, TAG, LAG, Maniac
→ 提供基本的exploit策略
→ 已经比90%的玩家强
```

### 未来增强后

```
Phase 2.3 + 长期vs短期:
→ 识别tilt和风格变化
→ 动态调整策略
→ 提升到顶尖玩家水平

Phase 3 + 摊牌分析:
→ 更精准的范围推断
→ 识别慢打、诈唬模式
→ 接近准职业水平

Phase 4 + 所有增强:
→ 全方位对手建模
→ 接近AI求解器水平
→ 这是研究级别的系统
```

---

## 💭 设计哲学

### 80/20原则

```
20%的特性 → 80%的价值
━━━━━━━━━━━━━━━━━━━━━
基础统计 (当前) → 大部分决策已经够用

80%的特性 → 20%的价值
━━━━━━━━━━━━━━━━━━━━━
高级特性 (未来) → 边际收益递减
```

### 实用主义

> "完美是优秀的敌人"

- 先把基础做扎实
- 再逐步添加高级特性
- 每个特性都要实际测试ROI

### 数据驱动

- 所有增强都要基于**真实数据**验证
- 避免过度工程化
- 保持系统简洁可维护

---

## 📚 参考资料

### 相关论文
- "The Mathematics of Poker" - Bill Chen & Jerrod Ankenman
- "Expert Heads-Up No-Limit Hold'em" - Will Tipton (Vol 1-3)
- Pluribus AI (Facebook) - 多人德州扑克AI

### 类似系统
- PokerTracker 4 - 商业对手追踪软件
- Hold'em Manager 3 - 另一个商业软件
- 它们都实现了"长期vs短期"和"摊牌分析"

---

**最后更新**: 2025-01-10
**状态**: 概念设计，暂未实现
**联系**: 与"自然语言解释生成"一起作为Phase 4的探索方向
