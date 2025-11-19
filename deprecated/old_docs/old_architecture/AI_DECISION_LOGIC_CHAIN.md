# AI决策逻辑链详解

## 核心问题回答

1. **三个引擎如何互相运作？**
2. **如何最终影响AI决策？**
3. **每一层代码文件的工作链条？**

---

## 完整决策流程图

```
用户输入 GameState
         │
         ↓
┌─────────────────────────────────────────────────────────┐
│  ProLevelAdvisor.advise()                              │
│  (advisor/strategy_engine/advisor.py)                  │
└─────────────────────────────────────────────────────────┘
         │
         ├──> 步骤1: 推断范围 (_estimate_ranges)
         │    │
         │    ├─> RangeEstimator.estimate_preflop_range()
         │    │   (strategy_engine/range_estimator.py)
         │    │   │
         │    │   ├─> 根据 position + action + player_type
         │    │   ├─> 调用 get_open_range() (preflop_ranges.py)
         │    │   └─> 返回 villain_range
         │    │
         │    └─> 返回: hero_range, villain_range
         │
         ├──> 步骤2: 计算Equity (_calculate_equity)
         │    │
         │    ├─> OptimizedEquityCalculator.calculate_vs_range()
         │    │   (range_engine/calculator_optimized.py)
         │    │   │
         │    │   ├─> 遍历 villain_range 中的每手牌
         │    │   ├─> 多线程并行计算 (ThreadPoolExecutor)
         │    │   ├─> 每个线程调用 calculate_equity()
         │    │   │   │
         │    │   │   └─> Monte Carlo模拟 (iterations次)
         │    │   │       │
         │    │   │       └─> UltraFastHandEvaluator (evaluator_fast_v2.py)
         │    │   │           └─> 查找预计算表 (41MB lookup table)
         │    │   │
         │    │   └─> 返回平均 equity
         │    │
         │    └─> 返回: equity (0.0-1.0)
         │
         ├──> 步骤3: 分析公共牌 (如果有board)
         │    │
         │    └─> BoardTexture.analyze()
         │        (range_engine/board_texture.py)
         │        │
         │        └─> 返回: dry/medium/wet, 同花/顺子可能性
         │
         ├──> 步骤4: 评估范围优势 (_assess_range_advantage)
         │    │
         │    └─> 比较 len(hero_range) vs len(villain_range)
         │        │
         │        └─> 返回: 'strong'/'medium'/'weak'
         │
         ├──> 步骤5: 构建GTO上下文 (_build_gto_context)
         │    │
         │    └─> GTOContext对象
         │        (包含 equity, range_advantage, position, spr, etc)
         │
         ├──> 步骤6: GTO基线决策 (_get_gto_decision)
         │    │
         │    ├─> GTOBaseline.preflop_strategy() 或 postflop_strategy()
         │    │   (strategy_engine/gto_baseline.py)
         │    │   │
         │    │   ├─> 翻前:
         │    │   │   ├─> calculate_preflop_hand_strength()
         │    │   │   ├─> _preflop_open_strategy() (基于位置阈值)
         │    │   │   ├─> _preflop_vs_open() (基于strength)
         │    │   │   ├─> _preflop_vs_3bet() (基于equity + opponent_type)
         │    │   │   └─> 返回 {'fold': x, 'call': y, 'raise': z}
         │    │   │
         │    │   └─> 翻后:
         │    │       ├─> 如果 facing_bet:
         │    │       │   ├─> calculate_mdf() (最小防守频率)
         │    │       │   ├─> calculate_pot_odds()
         │    │       │   └─> 基于 equity vs pot_odds 决策
         │    │       │
         │    │       └─> 如果未facing_bet:
         │    │           ├─> _calculate_bet_frequency() (范围优势+位置)
         │    │           ├─> calculate_optimal_bluff_frequency()
         │    │           └─> 基于 equity threshold 决策
         │    │
         │    └─> 返回: DecisionOutput (gto_decision)
         │
         ├──> 步骤7: Exploit调整 (_get_exploit_decision)
         │    │
         │    ├─> get_exploit_strategy(opponent_type)
         │    │   (opponent_modeling/exploits.py)
         │    │   │
         │    │   ├─> StrategyLibrary.get_strategy()
         │    │   │   │
         │    │   │   └─> 根据 PlayerType 返回对应策略
         │    │   │       ├─> FISH: 不bluff, 薄价值, 隔离加注
         │    │   │       ├─> NIT: 高频偷盲, 尊重aggression
         │    │   │       ├─> LAG: 放宽call, 慢打, 少bluff
         │    │   │       └─> MANIAC: trap, bluff catch
         │    │   │
         │    │   └─> 返回: ExploitStrategy对象
         │    │
         │    ├─> ExploitStrategy.apply_to_gto_strategy()
         │    │   │
         │    │   ├─> 如果 facing_bet: 调整防守频率
         │    │   ├─> 如果 equity > 0.65: 调整价值下注
         │    │   └─> 其他: 维持GTO
         │    │
         │    └─> 返回: DecisionOutput (exploit_decision)
         │
         ├──> 步骤8: 混合策略 (_merge_strategies)
         │    │
         │    ├─> _calculate_dynamic_weights()
         │    │   │
         │    │   ├─> 根据对手样本量调整权重
         │    │   │   (样本少 → 更GTO)
         │    │   ├─> 根据SPR调整权重
         │    │   │   (浅筹码 → 更GTO)
         │    │   └─> 返回: {'gto': w1, 'exploit': w2}
         │    │
         │    ├─> merge_decisions()
         │    │   │
         │    │   └─> final_distribution =
         │    │       gto_distribution * w1 + exploit_distribution * w2
         │    │
         │    └─> _add_sizing_options()
         │        │
         │        └─> 计算最优下注尺寸 (基于对手类型)
         │
         ├──> 步骤9: 添加决策依据
         │    │
         │    └─> 填充 reasoning 字段
         │        (equity, range_advantage, position, pot_odds, etc)
         │
         └──> 返回 DecisionOutput
              ├─> recommended_action: 'fold'/'call'/'raise'
              ├─> action_distribution: {'fold': 0.1, 'call': 0.3, 'raise': 0.6}
              ├─> optimal_sizing: 0.66 (pot的百分比)
              ├─> confidence: 0.85
              └─> reasoning: {...}
```

---

## 三个引擎的互相作用

### 1. Range Engine → Strategy Engine

**数据流动：**
```
Range Engine 计算:
  hero_range = "22+,A2s+,..."
  villain_range = "88+,AJ+,..."
  equity = 0.68 (hero vs villain)
  board_texture = "dry"
         │
         ↓
Strategy Engine 使用:
  if equity > 0.65:
      return {'raise': 0.70, ...}  # 价值下注
```

**具体影响：**
- **Equity决定动作**：equity > 0.65 → value bet，equity < 0.35 → bluff/fold
- **范围大小影响激进度**：hero_range宽 → 可以多bluff
- **Board texture影响c-bet频率**：dry board → 高频c-bet，wet board → 谨慎

**代码位置：**
- Range Engine: `advisor/range_engine/calculator_optimized.py`
- 传递到: `advisor/strategy_engine/advisor.py` line 133-139
- 使用于: `advisor/strategy_engine/gto_baseline.py` line 243-279

---

### 2. Opponent Modeling → Strategy Engine

**数据流动：**
```
Opponent Modeling 分析:
  player_type = FISH
  tendencies = ["跟注太多", "不爱弃牌"]
  weaknesses = ["对价值下注总是call"]
         │
         ↓
Strategy Engine 调整:
  exploit_strategy = {
      'bluff_frequency': 0.0,      # 不bluff
      'value_bet_thin': True,      # 薄价值下注
      'value_bet_sizing': 0.8      # 大尺寸
  }
         │
         ↓
最终决策:
  GTO: {'bet': 0.60, 'check': 0.40}
  Exploit调整: bet频率 +0.20 (因为对Fish)
  Final: {'bet': 0.80, 'check': 0.20}
```

**具体影响：**

**vs FISH (exploit_weight=0.4):**
- GTO说bet 60% → Exploit调整+20% → 最终bet 68%
- 不bluff（因为Fish不弃牌）
- 薄价值下注（因为Fish call太多）
- 大尺寸（Fish对尺寸不敏感）

**vs NIT (exploit_weight=0.4):**
- GTO说steal 50% → Exploit调整+30% → 最终steal 62%
- 更频繁bluff（因为Nit容易弃牌）
- 尊重他们的aggression（Nit raise=强牌）

**vs LAG (exploit_weight=0.4):**
- GTO说call 3-bet 40% → Exploit调整+20% → 最终call 52%
- 放宽call范围（因为LAG 3-bet宽）
- 少bluff（因为LAG不容易弃牌）
- 慢打（让LAG自己诈唬）

**代码位置：**
- Opponent Model: `advisor/opponent_modeling/exploits.py`
- 获取策略: `advisor/strategy_engine/advisor.py` line 399
- 应用调整: `advisor/strategy_engine/advisor.py` line 402-416
- 混合权重: `advisor/strategy_engine/advisor.py` line 447-478

---

### 3. Range Engine → Opponent Modeling

**数据流动：**
```
Opponent Modeling 需要:
  根据对手行动推断范围
         │
         ↓
RangeEstimator 使用:
  player_type = LAG
  action = '3bet'
  position = BTN
         │
         ↓
Range Engine 提供:
  LAG的BTN 3-bet范围 = "88+,A9s+,KTs+,..."
         │
         ↓
回到 Opponent Modeling:
  用这个范围计算exploit策略
```

**代码位置：**
- Range Estimator: `advisor/strategy_engine/range_estimator.py` line 55-109
- 调用: `advisor/strategy_engine/advisor.py` line 242

---

## 每一层代码文件的工作链条

### Layer 1: Range Engine（范围引擎）

#### 工作流程：

```
1. preflop_ranges.py
   └─> 定义标准范围表
       PREFLOP_RANGES = {
           'BTN': {'tight': [...], 'normal': [...], 'loose': [...]},
           ...
       }

2. range.py
   └─> Range类: 表示手牌组合集合
       ├─> from_string("22+,AK,AQs")
       ├─> to_hands() → List[Hand]
       └─> remove_conflicting(known_cards)

3. calculator_optimized.py ⭐
   └─> OptimizedEquityCalculator.calculate_vs_range()
       │
       ├─> 步骤1: 过滤有效villain hands
       │   for vh in villain_range:
       │       if 不冲突: add to valid_hands
       │
       ├─> 步骤2: 判断单线程 vs 多线程
       │   if len(valid_hands) <= 5:
       │       单线程处理
       │   else:
       │       多线程处理 (ThreadPoolExecutor)
       │
       ├─> 步骤3: 每个线程执行
       │   def calc_equity_worker(villain_hand):
       │       return calculate_equity(hero, villain, board, iterations)
       │
       │       └─> Monte Carlo模拟
       │           for i in range(iterations):
       │               1. 发出剩余公共牌
       │               2. 评估双方牌力
       │               3. 比较胜负
       │
       │           └─> evaluator_fast_v2.py
       │               UltraFastHandEvaluator.evaluate_best_5()
       │               │
       │               └─> 查找预计算表
       │                   key = cards_to_key_fast(cards)
       │                   score = LOOKUP_TABLE[key]
       │
       └─> 步骤4: 聚合结果
           返回平均 equity

4. board_texture.py
   └─> BoardTexture.analyze(board)
       ├─> 判断 dry/medium/wet
       ├─> 同花可能性
       ├─> 顺子可能性
       └─> 高牌/中牌/低牌分布
```

**关键参数（当前配置）：**
- iterations = 1000（原始精度）
- max_combos = 100（采样数量）
- max_workers = 4（线程数）

**性能：**
- UltraFastHandEvaluator: 7.6x加速
- 多线程: ~4x加速（在大范围时）
- 总体: 30x加速（相比原始实现）

---

### Layer 2: Opponent Modeling（对手建模）

#### 工作流程：

```
1. models.py
   └─> 定义数据结构
       PlayerType枚举:
       ├─> UNKNOWN
       ├─> NIT (紧凶)
       ├─> TAG (标准紧凶)
       ├─> LAG (松凶)
       ├─> FISH (鱼)
       ├─> CALLING_STATION (跟注站)
       ├─> MANIAC (疯子)
       └─> ...

2. classifier.py
   └─> PlayerClassifier.classify()
       │
       ├─> 输入: OpponentStats
       │   ├─> vpip: 入池率
       │   ├─> pfr: 翻前加注率
       │   ├─> af: 激进度
       │   └─> 3bet_pct: 3-bet频率
       │
       ├─> 分类规则:
       │   if vpip < 20 and pfr < 15:
       │       return NIT
       │   elif vpip > 40 and af > 3:
       │       return LAG/MANIAC
       │   elif vpip < 25 and af > 2:
       │       return TAG
       │   ...
       │
       └─> 输出: PlayerType + confidence

3. exploits.py ⭐
   └─> StrategyLibrary.get_strategy(player_type)
       │
       ├─> 选择策略:
       │   if player_type == FISH:
       │       return _build_fish_strategy()
       │   elif player_type == NIT:
       │       return _build_nit_strategy()
       │   ...
       │
       └─> ExploitStrategy对象
           ├─> tendencies: ["跟注太多", "不爱弃牌"]
           ├─> weaknesses: ["对价值下注总是call"]
           │
           ├─> 翻前策略:
           │   ├─> preflop_steal: StrategyAdvice
           │   ├─> preflop_iso: StrategyAdvice
           │   ├─> preflop_3bet: StrategyAdvice
           │   └─> preflop_vs_3bet: StrategyAdvice
           │
           ├─> 翻后策略:
           │   ├─> postflop_cbet: StrategyAdvice
           │   ├─> postflop_bluff: StrategyAdvice
           │   ├─> postflop_value: StrategyAdvice
           │   └─> postflop_defense: StrategyAdvice
           │
           └─> apply_to_gto_strategy()
               ├─> 输入: GTO action_distribution
               ├─> 根据context调整频率
               └─> 输出: 调整后的 distribution

4. 示例：vs FISH的exploit
   ExploitStrategy(FISH):
       weaknesses = ["对价值下注总是call", "不会fold"]

       postflop_value = StrategyAdvice(
           action="极薄价值下注",
           frequency="非常高",
           sizing="大尺寸 (0.75-1.0 pot)"
       )

       postflop_bluff = StrategyAdvice(
           action="避免bluff",
           frequency="极低或0",
           reason="Fish不会弃牌"
       )

   应用到GTO:
       GTO: {'bet': 0.60, 'bluff': 0.20}
       Exploit调整:
           bet频率 +0.20 (因为薄价值有效)
           bluff频率 -0.20 (因为Fish不弃牌)
       Final: {'bet': 0.80, 'bluff': 0.0}
```

---

### Layer 3: Strategy Engine（策略引擎）

#### 工作流程：

```
1. advisor.py ⭐⭐ 主决策引擎
   └─> ProLevelAdvisor.advise(game_state)
       │
       ├─> 初始化组件:
       │   self.range_estimator = RangeEstimator()
       │   self.equity_calculator = EquityCalculator(iterations=1000)
       │   self.gto_baseline = GTOBaseline()
       │   self.classifier = PlayerClassifier()
       │
       ├─> 决策流程 (9步):
       │   │
       │   ├─> 步骤1: _estimate_ranges()
       │   │   ├─> hero_range = get_open_range(position, 'normal')
       │   │   └─> villain_range = range_estimator.estimate_preflop_range(...)
       │   │
       │   ├─> 步骤2: _calculate_equity()
       │   │   ├─> villain_hands = villain_range.to_hands()
       │   │   ├─> 限制 max_combos = 100
       │   │   ├─> iterations = _get_iterations(game_state)
       │   │   └─> equity = equity_calculator.calculate_vs_range(...)
       │   │
       │   ├─> 步骤3: 分析board
       │   │   └─> board_texture = BoardTexture(board)
       │   │
       │   ├─> 步骤4: _assess_range_advantage()
       │   │   ├─> 比较 len(hero_range) vs len(villain_range)
       │   │   └─> 返回 'strong'/'medium'/'weak'
       │   │
       │   ├─> 步骤5: _build_gto_context()
       │   │   └─> GTOContext(equity, range_advantage, position, spr, ...)
       │   │
       │   ├─> 步骤6: _get_gto_decision()
       │   │   └─> gto_baseline.preflop_strategy() / postflop_strategy()
       │   │
       │   ├─> 步骤7: _get_exploit_decision()
       │   │   ├─> exploit_strategy = get_exploit_strategy(opponent_type)
       │   │   └─> exploit_strategy.apply_to_gto_strategy(gto_decision)
       │   │
       │   ├─> 步骤8: _merge_strategies()
       │   │   ├─> weights = _calculate_dynamic_weights()
       │   │   │   ├─> 考虑对手样本量
       │   │   │   ├─> 考虑SPR
       │   │   │   └─> 返回 {'gto': 0.6, 'exploit': 0.4}
       │   │   │
       │   │   └─> final = gto * 0.6 + exploit * 0.4
       │   │
       │   └─> 步骤9: 添加reasoning
       │       └─> 记录所有决策依据
       │
       └─> 返回 DecisionOutput

2. gto_baseline.py ⭐ GTO策略核心
   └─> GTOBaseline类
       │
       ├─> 翻前策略:
       │   │
       │   ├─> preflop_strategy()
       │   │   ├─> 根据 action_history 判断场景:
       │   │   │   ├─> 无行动 → _preflop_open_strategy()
       │   │   │   ├─> facing open → _preflop_vs_open()
       │   │   │   ├─> facing 3-bet → _preflop_vs_3bet()
       │   │   │   └─> facing 4-bet → _preflop_vs_4bet()
       │   │   │
       │   │   └─> 返回 action_distribution
       │   │
       │   ├─> _preflop_open_strategy()
       │   │   └─> 基于位置阈值:
       │   │       UTG: strength > 0.75 (top 25%)
       │   │       BTN: strength > 0.50 (top 50%)
       │   │
       │   ├─> _preflop_vs_open()
       │   │   └─> 基于strength:
       │   │       > 0.85: 3-bet
       │   │       > 0.65: call
       │   │       < 0.65: fold
       │   │
       │   └─> _preflop_vs_3bet()
       │       └─> 优先使用equity:
       │           > 0.65: 4-bet
       │           > 0.48: call (超过pot odds)
       │           < 0.42: fold
       │
       └─> 翻后策略:
           │
           ├─> postflop_strategy()
           │   ├─> 判断是否facing_bet:
           │   │   ├─> 是 → _defense_strategy()
           │   │   └─> 否 → _aggression_strategy()
           │   │
           │   └─> 多人底池调整
           │       └─> equity *= equity^(num_opponents-1)
           │
           ├─> _defense_strategy()
           │   ├─> pot_odds = bet / (pot + bet)
           │   ├─> mdf = pot / (pot + bet)
           │   │
           │   └─> 决策逻辑:
           │       if equity > pot_odds + 0.05:
           │           call频率高，raise少量
           │       elif equity ≈ pot_odds:
           │           混合策略 (按MDF)
           │       else:
           │           主要fold
           │
           └─> _aggression_strategy()
               ├─> bet_frequency = f(range_advantage, position, board_texture)
               ├─> bluff_freq = bet / (pot + bet)
               │
               └─> 决策逻辑:
                   if equity > 0.65:
                       价值下注
                   elif equity > 0.35:
                       少量半bluff
                   else:
                       主要check，少量pure bluff

3. range_estimator.py
   └─> RangeEstimator.estimate_preflop_range()
       │
       ├─> 步骤1: 根据player_type获取tightness
       │   NIT/TAG → 'tight'
       │   LAG/FISH → 'loose'
       │   其他 → 'normal'
       │
       ├─> 步骤2: 根据action选择范围
       │   │
       │   ├─> OPEN:
       │   │   └─> get_open_range(position, tightness)
       │   │
       │   ├─> 3-BET:
       │   │   └─> _estimate_3bet_range()
       │   │       LAG: "88+,A9s+,KTs+,..."  (宽)
       │   │       TAG: "99+,AJs+,KQs,..."   (中)
       │   │       NIT: "JJ+,AKs,AKo"        (窄)
       │   │
       │   └─> CALL:
       │       └─> _estimate_call_range()
       │           CALLING_STATION: 非常宽
       │           LAG: 宽
       │           TAG: 中等
       │           NIT: 紧
       │
       └─> 返回 Range对象

4. decision.py
   └─> 数据结构定义
       │
       ├─> GameState (输入)
       │   ├─> street: 'preflop'/'flop'/'turn'/'river'
       │   ├─> position: 'BTN'/'CO'/'BB'/...
       │   ├─> hero_hand: Hand
       │   ├─> pot_size: float
       │   ├─> effective_stack: float
       │   ├─> board: Board
       │   ├─> facing_bet: float
       │   ├─> opponent_type: PlayerType
       │   └─> ...
       │
       └─> DecisionOutput (输出)
           ├─> recommended_action: str
           ├─> action_distribution: Dict[str, float]
           ├─> optimal_sizing: float
           ├─> confidence: float
           └─> reasoning: Dict[str, Any]
```

---

## 关键算法公式

### 1. Equity计算（Monte Carlo）

```python
def calculate_equity(hero_hand, villain_hand, board, iterations):
    wins = 0
    ties = 0

    for i in range(iterations):
        # 发出剩余公共牌
        remaining_board = deal_remaining_cards(board)

        # 评估双方牌力
        hero_strength = evaluate_best_5(hero_hand + remaining_board)
        villain_strength = evaluate_best_5(villain_hand + remaining_board)

        # 比较
        if hero_strength > villain_strength:
            wins += 1
        elif hero_strength == villain_strength:
            ties += 1

    equity = (wins + ties/2) / iterations
    return equity
```

### 2. MDF（最小防守频率）

```python
def calculate_mdf(pot, bet):
    """
    MDF = pot / (pot + bet)

    例子: pot=10, bet=7
    MDF = 10 / (10+7) = 0.588 = 58.8%

    含义: 至少要用58.8%的范围跟注，否则对手无风险bluff
    """
    return pot / (pot + bet)
```

### 3. Pot Odds（底池赔率）

```python
def calculate_pot_odds(pot, call_amount):
    """
    Pot Odds = call / (pot + call)

    例子: pot=10, call=5
    Pot Odds = 5 / (10+5) = 0.333 = 33.3%

    含义: 需要至少33.3%的equity才值得跟注
    """
    return call_amount / (pot + call_amount)
```

### 4. 最优Bluff频率

```python
def calculate_optimal_bluff_frequency(pot, bet):
    """
    Optimal Bluff % = bet / (pot + bet)

    例子: pot=10, bet=7
    Bluff % = 7 / (10+7) = 0.412 = 41.2%

    含义: 在所有bet中，41.2%应该是bluff，58.8%是value
    这样对手用MDF防守时，我们的bluff和value都不会亏
    """
    return bet / (pot + bet)
```

### 5. 多人底池Equity打折

```python
def multiway_equity_discount(equity, num_opponents):
    """
    Multiway Equity ≈ equity^num_opponents

    例子: equity=0.70, 2个对手
    Multiway = 0.70^2 = 0.49

    含义: 需要同时击败多人，equity大幅下降
    """
    return equity ** num_opponents
```

### 6. SPR（筹码底池比）

```python
def calculate_spr(effective_stack, pot_size):
    """
    SPR = effective_stack / pot_size

    例子: stack=100, pot=10
    SPR = 100/10 = 10

    含义:
    - SPR < 3: 浅筹码，适合all-in
    - SPR 3-10: 中等，标准打法
    - SPR > 10: 深筹码，需要强牌commit
    """
    return effective_stack / pot_size if pot_size > 0 else 999
```

---

## 决策权重系统

### 动态权重计算

```python
def _calculate_dynamic_weights(game_state):
    """
    默认权重: gto=0.6, exploit=0.4

    调整因素:
    1. 对手样本量:
       hands_played < 30: gto+0.2, exploit-0.2 (样本少→更GTO)
       hands_played > 100: 维持默认

    2. 筹码深度:
       spr < 3: gto+0.1, exploit-0.1 (浅筹码→更GTO)
       spr > 10: 维持默认

    3. 对手偏差:
       偏差大: exploit+0.2 (有明显弱点→更exploit)
       偏差小: 维持默认
    """
    gto_weight = 0.6
    exploit_weight = 0.4

    if hands_played < 30:
        gto_weight += 0.2
        exploit_weight -= 0.2

    if spr < 3:
        gto_weight += 0.1
        exploit_weight -= 0.1

    # 归一化
    total = gto_weight + exploit_weight
    return {
        'gto': gto_weight / total,
        'exploit': exploit_weight / total
    }
```

### 最终决策混合

```python
def merge_decisions(gto_decision, exploit_decision, weights):
    """
    final_distribution = gto * w_gto + exploit * w_exploit

    例子:
    gto = {'fold': 0.2, 'call': 0.5, 'raise': 0.3}
    exploit = {'fold': 0.1, 'call': 0.3, 'raise': 0.6}
    weights = {'gto': 0.6, 'exploit': 0.4}

    final = {
        'fold': 0.2*0.6 + 0.1*0.4 = 0.16,
        'call': 0.5*0.6 + 0.3*0.4 = 0.42,
        'raise': 0.3*0.6 + 0.6*0.4 = 0.42
    }

    recommended = 'raise' or 'call' (随机选择)
    """
    final = {}
    for action in gto_decision.keys():
        final[action] = (
            gto_decision[action] * weights['gto'] +
            exploit_decision[action] * weights['exploit']
        )
    return final
```

---

## 完整示例：翻前决策

### 场景设置
```
Hero: AsKd on BTN
Villain: TAG on BB
Action: Hero opens to 3BB, Villain 3-bets to 9BB
Stack: 100BB
Pot: 9.5BB (3BB + 9BB - 0.5SB)
```

### 决策流程

```
步骤1: 推断范围
  hero_range = get_open_range('BTN', 'normal')
    → "22+,A2s+,K5s+,Q8s+,..." (约40%手牌)

  villain_range = estimate_preflop_range('BB', '3BET', TAG)
    → "99+,AJs+,KQs,AQo+" (约8%手牌)

步骤2: 计算Equity
  hero_hand = AsKd
  villain_range = [99,TT,JJ,QQ,KK,AA,AJs,AQs,AKs,AQo,AKo]

  OptimizedEquityCalculator.calculate_vs_range():
    遍历villain_range每手牌:
      vs 99: equity = 0.54
      vs TT: equity = 0.54
      vs JJ: equity = 0.56
      vs QQ: equity = 0.57
      vs KK: equity = 0.30
      vs AA: equity = 0.07
      vs AJs: equity = 0.70
      vs AQs: equity = 0.73
      vs AKs: equity = 0.50 (平局)
      vs AQo: equity = 0.74
      vs AKo: equity = 0.50

    加权平均 → equity = 0.52

步骤3: 分析公共牌
  board = None (翻前)
  → 跳过

步骤4: 范围优势
  len(hero_range) = 40% = 538 combos
  len(villain_range) = 8% = 108 combos
  538 > 108 * 1.3
  → range_advantage = 'strong'

步骤5: 构建GTO上下文
  GTOContext(
    street = PREFLOP,
    position = BTN,
    is_in_position = True,
    equity = 0.52,
    range_advantage = 'strong',
    pot_size = 9.5,
    effective_stack = 100,
    spr = 10.5,
    facing_bet = 9.0,
    bet_to_call = 6.0
  )

步骤6: GTO基线决策
  GTOBaseline.preflop_strategy():
    action_history = ['open', '3bet']
    → 调用 _preflop_vs_3bet()

    使用equity决策 (equity=0.52):
      equity >= 0.48 且 < 0.55
      → {'fold': 0.0, 'call': 0.90, '4bet': 0.10}

  gto_decision = {
    'fold': 0.0,
    'call': 0.90,
    '4bet': 0.10
  }

步骤7: Exploit调整
  opponent_type = TAG

  get_exploit_strategy(TAG):
    tendencies = ["紧凶", "平衡3-bet"]
    weaknesses = ["3-bet范围偏价值"]

    preflop_vs_3bet.advice:
      "可以放宽call范围" (因为TAG 3-bet range紧)

  apply_to_gto_strategy():
    facing_bet = True, context = 'defense'

    调整: call频率 +0.05

  exploit_decision = {
    'fold': 0.0,
    'call': 0.95,
    '4bet': 0.05
  }

步骤8: 混合策略
  _calculate_dynamic_weights():
    对手样本量 > 30 → 权重不变
    spr = 10.5 > 3 → 权重不变

    weights = {'gto': 0.6, 'exploit': 0.4}

  merge_decisions():
    final = {
      'fold': 0.0*0.6 + 0.0*0.4 = 0.0,
      'call': 0.90*0.6 + 0.95*0.4 = 0.92,
      '4bet': 0.10*0.6 + 0.05*0.4 = 0.08
    }

  recommended_action = 'call' (概率最高)

步骤9: 添加推理
  reasoning = {
    'equity': 0.52,
    'range_advantage': 'strong',
    'opponent_type': 'TAG',
    'pot_odds': 6/(9.5+6) = 0.387 = 38.7%,
    'position': 'IP',
    'spr': 10.5,
    'street': 'preflop',
    'strategy_weights': {'gto': 0.6, 'exploit': 0.4},
    'decision_rationale':
      "Equity (52%) > Pot Odds (38.7%), call有利。"
      "vs TAG 3-bet，主要是价值牌，我们AK有52% equity。"
      "有位置优势，可以看flop后决策。"
  }

返回 DecisionOutput:
  recommended_action = 'call'
  action_distribution = {'fold': 0.0, 'call': 0.92, '4bet': 0.08}
  optimal_sizing = 0 (不需要，是call)
  confidence = 0.85
  reasoning = {...}
```

---

## 性能关键点

### 1. Equity计算瓶颈

**问题：**
- 每个决策需要计算equity
- villain_range通常有10-100个组合
- 每个组合需要Monte Carlo采样1000次
- 总计算量：10-100 * 1000 = 10,000-100,000次模拟

**优化方案：**

1. **UltraFastHandEvaluator** (evaluator_fast_v2.py)
   - 预计算所有C(52,5)=2,598,960种5张牌组合
   - 存储为整数score，快速比较
   - **7.6x加速**

2. **多线程并行** (calculator_optimized.py)
   - ThreadPoolExecutor(max_workers=4)
   - 并行计算villain_range中的多个组合
   - **4x加速**（在大范围时）

3. **动态迭代次数** (advisor.py)
   - 关键决策：1000 iterations
   - 明显决策：300 iterations
   - **平均3x加速**

**总体加速：**7.6 * 4 * 3 ≈ **90x**

### 2. 当前配置

```python
# advisor.py
self.equity_calculator = EquityCalculator(iterations=1000)  # 原始精度
max_combos = 100  # 范围采样上限

# 动态迭代
preflop深筹码: 1000 iterations
postflop: 500 iterations
明显决策: 300 iterations

# calculator_optimized.py
max_workers = 4  # 多线程
```

---

## 总结：三引擎如何协同工作

```
                    用户输入
                       │
                       ↓
        ┌──────────────────────────────┐
        │  ProLevelAdvisor.advise()    │
        └──────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ↓              ↓              ↓
  ┌──────────┐  ┌──────────┐  ┌──────────┐
  │ Range    │  │ Opponent │  │ Strategy │
  │ Engine   │  │ Modeling │  │ Engine   │
  └──────────┘  └──────────┘  └──────────┘
        │              │              │
        │              │              │
        └──────────────┼──────────────┘
                       │
                       ↓
              GTO + Exploit混合
                       │
                       ↓
                DecisionOutput
```

### 数据流动

1. **Range Engine → Strategy**
   - 提供：hero_range, villain_range, equity, board_texture
   - 影响：决定GTO策略的基础（equity门槛、bluff频率）

2. **Opponent Modeling → Strategy**
   - 提供：player_type, exploit_adjustments
   - 影响：调整GTO策略的频率（steal、value bet、defense）

3. **Strategy Engine集成**
   - 计算GTO基线决策（基于equity + position + SPR）
   - 应用Exploit调整（基于opponent_type）
   - 动态混合（基于样本量 + 筹码深度）
   - 输出最终决策

### 关键影响因素（权重）

```
final_decision = f(
    Equity (30%):           Range Engine提供
    Range Advantage (25%):  Range Engine提供
    Position (20%):         GameState输入
    Opponent Type (15%):    Opponent Modeling提供
    SPR (10%):             GameState输入
)
```

每个因素通过三个引擎的协作，最终影响AI的决策分布和推荐行动。
