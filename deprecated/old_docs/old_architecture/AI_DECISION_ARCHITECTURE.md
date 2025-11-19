# AI 决策架构文档

## 概览

PokerAI使用三层架构进行决策：

```
                          ┌─────────────────────┐
                          │   ProLevelAdvisor   │ ← 主决策入口
                          │  (advisor.py)       │
                          └──────────┬──────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
              ▼                      ▼                      ▼
    ┌─────────────────┐   ┌─────────────────┐   ┌──────────────────┐
    │  Range Engine   │   │ Opponent Model  │   │ Strategy Engine  │
    │  范围引擎        │   │  对手建模        │   │  策略引擎         │
    └─────────────────┘   └─────────────────┘   └──────────────────┘
```

---

## 第一层：Range Engine（范围引擎）

**职责**：范围vs范围思维，equity计算

### 核心文件

#### 1. `advisor/range_engine/range.py`
- **Range类**：表示手牌组合集合
- 方法：
  - `from_string()`: 从字符串解析范围（如"22+,AK,AQs"）
  - `remove_conflicting()`: 移除与已知牌冲突的组合
  - `sample_hands()`: 从范围中采样具体手牌

#### 2. `advisor/range_engine/preflop_ranges.py`
- **翻前范围表**：定义5人桌各位置的标准范围
```python
PREFLOP_RANGES = {
    'UTG': {'tight': [...], 'normal': [...], 'loose': [...]},
    'CO': {...},
    'BTN': {...},
    'SB': {...},
    'BB': {...}
}
```

#### 3. `advisor/range_engine/calculator_optimized.py` ⭐ 关键
- **OptimizedEquityCalculator类**：计算equity（带多线程）
- 方法：
  - `calculate_equity(hero_hand, villain_hand, board, iterations)`
  - `calculate_vs_range(hero_hand, villain_range, board)` ← 多线程加速
- **当前配置**：
  - iterations=1000（原始精度）
  - max_workers=4（多线程）

#### 4. `advisor/range_engine/evaluator_fast_v2.py` ⭐ 性能关键
- **UltraFastHandEvaluator类**：快速手牌评估
- **预计算查找表**：2,598,960个5张牌组合
- **7.6x加速**：使用bitmask和整数比较

#### 5. `advisor/range_engine/board_texture.py`
- **BoardTexture类**：分析公共牌结构
- 功能：
  - 是否干燥/连牌/同花面
  - 高牌/中牌/低牌分布
  - 影响c-bet频率和下注尺寸

---

## 第二层：Opponent Modeling（对手建模）

**职责**：识别对手类型，提供exploit策略

### 核心文件

#### 1. `advisor/opponent_modeling/models.py`
- **PlayerType枚举**：9种玩家类型
```python
class PlayerType(Enum):
    UNKNOWN = 0
    NIT = 1          # 紧凶
    TAG = 2          # 标准紧凶
    LAG = 3          # 松凶
    FISH = 4         # 鱼
    CALLING_STATION = 5
    MANIAC = 6
    WEAK_TIGHT = 7
    SOLID_PLAYER = 8
```

#### 2. `advisor/opponent_modeling/classifier.py`
- **PlayerClassifier类**：分类对手类型
- 基于统计数据：
  - VPIP（入池率）
  - PFR（翻前加注率）
  - AF（激进度）
  - 3-bet频率等

#### 3. `advisor/opponent_modeling/stats.py`
- **OpponentStats类**：追踪对手统计数据
- 20+个指标

#### 4. `advisor/opponent_modeling/exploits.py`
- **EXPLOIT_STRATEGIES字典**：针对每种类型的exploit方案
```python
EXPLOIT_STRATEGIES = {
    'FISH': {
        'bluff_frequency': 0.0,      # 不bluff
        'value_bet_thin': True,      # 薄价值下注
    },
    'NIT': {
        'steal_frequency': 0.8,      # 高频偷盲
        'bluff_frequency': 0.4,
    },
    ...
}
```

---

## 第三层：Strategy Engine（策略引擎）

**职责**：整合三层，输出最终决策

### 核心文件

#### 1. `advisor/strategy_engine/advisor.py` ⭐⭐ 最核心
- **ProLevelAdvisor类**：主决策类
- **核心方法**：`advise(game_state: GameState) -> DecisionOutput`

**决策流程**：
```python
def advise(self, game_state):
    # 步骤1: 推断范围
    hero_range, villain_range = self._estimate_ranges(game_state)

    # 步骤2: 计算equity
    equity = self._calculate_equity(
        game_state.hero_hand,
        villain_range,
        game_state.board
    )

    # 步骤3: 评估范围优势
    range_advantage = self._assess_range_advantage(...)

    # 步骤4: GTO基线策略
    gto_strategy = self.gto_baseline.get_strategy(
        game_state, equity, range_advantage
    )

    # 步骤5: Exploitative调整
    exploit_adjustments = self._get_exploits(game_state.opponent_type)

    # 步骤6: 混合策略
    final_strategy = self._blend_strategies(gto_strategy, exploit_adjustments)

    # 步骤7: 选择最优动作
    recommended_action = max(final_strategy, key=final_strategy.get)

    return DecisionOutput(
        recommended_action=recommended_action,
        action_probs=final_strategy,
        optimal_sizing=...,
        reasoning={...}
    )
```

**关键参数**（当前配置）：
```python
# advisor.py line 105
self.equity_calculator = EquityCalculator(iterations=1000)  # 原始精度

# advisor.py line 281
max_combos = 100  # 范围采样数量

# advisor.py line 206-225（动态迭代）
场景1: 翻前深筹码 → 1000 iterations
场景2: 小底池 → 300 iterations
场景3: 边缘决策 → 1000 iterations
场景4: 明显决策 → 300 iterations
场景5: 翻后 → 500 iterations
```

#### 2. `advisor/strategy_engine/gto_baseline.py` ⭐ 策略核心
- **GTOBaseline类**：GTO策略基线

**关键方法**：

##### 翻前策略
```python
def preflop_open(position, hand_strength):
    """开池策略"""
    # 基于位置和手牌强度

def preflop_vs_open(position, hand_strength, facing_raise):
    """面对open的策略"""
    # call/raise/fold频率

def preflop_vs_3bet(hand_strength, pot_odds):
    """面对3-bet的策略"""
    # 基于pot odds和手牌强度
```

##### 翻后策略
```python
def postflop_strategy(equity, position, spr, board_texture):
    """翻后策略（支持flop/turn/river）"""
    # 返回：check/bet/raise频率

def postflop_defense(pot_odds, equity):
    """翻后防守（基于MDF）"""
    # MDF = pot / (pot + bet)

def postflop_aggression(range_advantage, position):
    """翻后激进度调整"""
    # c-bet频率、bluff频率
```

##### 关键公式
```python
def calculate_mdf(pot, bet):
    """最小防守频率"""
    return pot / (pot + bet)

def optimal_bluff_frequency(pot, bet):
    """最优bluff频率"""
    return bet / (pot + bet)

def multiway_equity_discount(equity, num_opponents):
    """多人底池equity打折"""
    return equity ** num_opponents
```

#### 3. `advisor/strategy_engine/range_estimator.py`
- **RangeEstimator类**：推断对手范围
- 方法：
  - `estimate_preflop_range(position, action, player_type)`
  - `update_postflop_range(current_range, action, board)` ← 目前未充分使用

#### 4. `advisor/strategy_engine/decision.py`
- **数据结构定义**：
```python
@dataclass
class GameState:
    """输入：游戏状态"""
    street: str                 # 'preflop'/'flop'/'turn'/'river'
    position: str               # 'BTN'/'CO'/'BB'等
    hero_hand: Hand
    pot_size: float
    effective_stack: float
    board: Optional[Board]
    facing_bet: float
    opponent_type: PlayerType
    action_history: List[str]
    num_opponents: int
    ...

@dataclass
class DecisionOutput:
    """输出：AI决策"""
    recommended_action: str           # 'fold'/'call'/'raise'
    action_probs: Dict[str, float]   # 各动作概率
    optimal_sizing: float            # 最优下注尺寸
    confidence: float                # 决策置信度
    reasoning: Dict[str, Any]        # 推理过程
```

---

## 决策影响因素权重

```python
# advisor.py 中的权重系统
final_decision = f(
    equity: 30%,              # Range vs Range equity
    range_advantage: 25%,     # 哪方范围更强
    position: 20%,            # 位置优势
    opponent_type: 15%,       # 对手类型exploit
    spr: 10%                  # 筹码底池比
)
```

---

## 翻后决策能力

### AI是否支持翻后决策？

**是的！** AI完全支持翻后决策：

1. **advisor.py的advise()方法**支持所有street：
   - `street='preflop'`
   - `street='flop'`
   - `street='turn'`
   - `street='river'`

2. **GTOBaseline有完整的翻后策略**：
   - `postflop_strategy()`: 基于equity/position/SPR
   - `postflop_defense()`: 基于MDF
   - `postflop_aggression()`: c-bet/probe bet

3. **Range Engine支持翻后**：
   - BoardTexture分析公共牌
   - Equity计算支持任意board状态

### 为什么测试中没有翻后？

**因为测试脚本简化了！**

`tests/performance/test_50hands_detailed.py`为了简化：
- 翻前call后直接发出所有公共牌（flop+turn+river）
- 立即比牌
- **没有调用AI的翻后决策**

这是为什么对Random只有+2 BB/100的关键原因：
- ✅ 翻前决策正常工作
- ❌ 翻后位置优势完全没利用
- ❌ 没有c-bet/probe bet/check-raise等翻后技巧

---

## 完整调用链示例

```python
# 1. 用户调用
game_state = GameState(
    street='flop',
    position='BTN',
    hero_hand=Hand.from_str('AhKd'),
    board=Board.from_str('Ks 7h 3c'),
    pot_size=6.0,
    effective_stack=94.0,
    facing_bet=4.0,
    opponent_type=PlayerType.TAG
)

advisor = ProLevelAdvisor()
decision = advisor.advise(game_state)

# 2. advisor.advise() 内部流程
#    a. 推断范围
hero_range = Range.from_string("22+,A2s+,K9s+,...")
villain_range = RangeEstimator.estimate_preflop_range('CO', 'RAISE', 'TAG')
#       → 假设CO TAG open range

#    b. 计算equity（多线程）
equity = OptimizedEquityCalculator.calculate_vs_range(
    hero_hand='AhKd',
    villain_range=villain_range,
    board='Ks 7h 3c',
    iterations=500  # 翻后场景
)
#       → 调用 UltraFastHandEvaluator (lookup table)
#       → 并行计算100个组合
#       → 返回 equity=0.78

#    c. 分析board texture
board_texture = BoardTexture.analyze('Ks 7h 3c')
#       → {'paired': False, 'flush_draw': False, 'straight_draw': True, ...}

#    d. GTO基线策略
gto_strategy = GTOBaseline.postflop_strategy(
    equity=0.78,
    position='BTN',
    spr=15.7,
    board_texture=board_texture,
    facing_bet=4.0,
    pot=6.0
)
#       → {'fold': 0.05, 'call': 0.25, 'raise': 0.70}

#    e. Exploitative调整
if opponent_type == TAG:
    # TAG对c-bet fold频率高
    adjustments = {'raise': +0.10}  # 增加bluff频率

#    f. 最终决策
final_strategy = blend(gto_strategy, adjustments, weight=0.4)
#       → {'fold': 0.04, 'call': 0.21, 'raise': 0.75}

recommended = 'raise'
sizing = calculate_sizing(pot, equity, range_advantage)
#       → 0.66 (2/3 pot)

# 3. 返回结果
return DecisionOutput(
    recommended_action='raise',
    optimal_sizing=0.66,
    action_probs={'fold': 0.04, 'call': 0.21, 'raise': 0.75},
    confidence=0.85,
    reasoning={
        'equity': 0.78,
        'range_advantage': 0.32,
        'position': 'in_position',
        'board_texture': 'dry_high_card'
    }
)
```

---

## 性能关键点

1. **UltraFastHandEvaluator** (evaluator_fast_v2.py)
   - 预计算查找表：41MB
   - 7.6x加速

2. **OptimizedEquityCalculator** (calculator_optimized.py)
   - 多线程并行计算
   - 4线程默认

3. **动态迭代次数** (advisor.py)
   - 关键决策：1000 iterations
   - 明显决策：300 iterations

4. **范围采样** (advisor.py)
   - max_combos=100
   - 平衡精度与速度

---

## 当前限制和问题

### 1. 测试脚本不完整
- ❌ 只测试翻前决策
- ❌ 翻后直接摊牌
- ❌ 没有利用位置优势

### 2. AI能力未充分测试
- ✅ AI有完整的翻后决策能力
- ❌ 但测试中从未调用
- ❌ +2 BB/100的结果不能反映真实实力

### 3. 可能的改进方向
1. **完善测试脚本**：添加翻后决策流程
2. **优化BTN策略**：可能开池范围太紧
3. **调整MDF计算**：防守频率可能需要调整

---

## 文件优先级（按影响力排序）

### 🔴 最高优先级（直接影响决策）
1. `advisor/strategy_engine/advisor.py` - 主决策入口
2. `advisor/strategy_engine/gto_baseline.py` - 策略核心
3. `advisor/range_engine/calculator_optimized.py` - Equity计算

### 🟡 中优先级（影响质量）
4. `advisor/range_engine/preflop_ranges.py` - 范围定义
5. `advisor/strategy_engine/range_estimator.py` - 范围推断
6. `advisor/opponent_modeling/exploits.py` - Exploit策略

### 🟢 低优先级（支持功能）
7. `advisor/range_engine/board_texture.py` - 牌面分析
8. `advisor/opponent_modeling/classifier.py` - 对手分类
9. `advisor/range_engine/evaluator_fast_v2.py` - 性能优化（不影响逻辑）

---

## 总结

**AI决策架构是完整的**，包括翻前和翻后策略。当前+2 BB/100的测试结果不能反映AI真实实力，因为：

1. ✅ AI有完整的三层架构（Range + Opponent + Strategy）
2. ✅ AI支持翻前和翻后所有street的决策
3. ✅ AI有GTO基线 + Exploitative调整
4. ❌ **但测试脚本只测试翻前，翻后直接摊牌**
5. ❌ **没有利用AI的翻后决策能力和位置优势**

**建议**：编写完整的测试脚本，包含翻后决策流程，才能真正评估AI实力。
