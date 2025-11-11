# Range被架空的完整证据

## 概述

虽然项目中精心定义了GTO翻前范围（Preflop Ranges），但**AI决策完全不使用这些范围**，而是依赖简化的hand_strength系统。

本文档展示range是如何被架空的完整代码证据。

---

## 证据1：Range的定义（被忽略）

### 文件：advisor/range_engine/preflop_ranges.py

#### BTN开池范围定义（95-114行）

```python
# ===== BTN (Button) 范围 =====
# 最佳位置，可以玩最宽范围

BTN_OPEN_RANGES = {
    'tight': {
        'pairs': ['44+'],
        'suited': ['A2s+', 'K8s+', 'Q9s+', 'J8s+', 'T8s+', '98s'],
        'offsuit': ['A8o+', 'K9o+', 'QTo+', 'JTo'],  # ← K7o不在范围内
        # 总计: ~28.5%
    },
    'normal': {
        'pairs': ['22+'],
        'suited': ['A2s+', 'K5s+', 'Q7s+', 'J7s+', 'T7s+', '97s+', '86s+', '76s', '65s'],
        'offsuit': ['A5o+', 'K8o+', 'Q9o+', 'J9o+', 'T8o+', '98o'],  # ← K7o不在范围内（需要K8o+）
        # 总计: ~46.8%
    },
    'loose': {
        'pairs': ['22+'],
        'suited': ['A2s+', 'K2s+', 'Q4s+', 'J6s+', 'T6s+', '96s+', '85s+', '75s+', '65s', '54s'],
        'offsuit': ['A2o+', 'K7o+', 'Q8o+', 'J8o+', 'T8o+', '98o'],  # ← K7o在loose范围内 ✅
        # 总计: ~58.3%
    }
}
```

**状态**：✅ 精心设计的GTO范围，考虑了位置、牌力、频率

**问题**：❌ **完全不用于AI决策！**

---

## 证据2：Range的唯一使用（仅用于Equity计算）

### 文件：advisor/strategy_engine/advisor.py:227-252

```python
def _estimate_ranges(self, game_state: GameState) -> tuple:
    """推断hero和villain范围"""
    # Hero范围（简化：假设合理开池/跟注范围）
    try:
        pos = Position[game_state.position.upper()]
        hero_dict = get_open_range(pos.value, 'normal')  # ← 调用preflop_ranges
        hero_range = parse_range_dict(hero_dict)
    except:
        hero_range = Range.from_string("22+,A2s+,K5s+,Q8s+,J8s+,T8s+,A5o+,K9o+")

    # Villain范围
    if game_state.action_history and game_state.opponent_type:
        try:
            last_action = game_state.action_history[-1]
            villain_pos = Position.BTN  # 默认
            villain_range = self.range_estimator.estimate_preflop_range(
                villain_pos,
                Action[last_action.upper()],
                game_state.opponent_type
            )  # ← 也使用preflop_ranges
        except:
            villain_range = Range.from_string("22+,A2s+,K8s+,Q9s+,J9s+,T8s+")
    else:
        villain_range = Range.from_string("22+,A2s+,K8s+,Q9s+,J9s+,T8s+")

    return hero_range, villain_range
```

**用途**：✅ 获取hero和villain的range

**但是**：⚠️ 这些range**只传给equity计算**，不用于决策！

---

### 文件：advisor/strategy_engine/advisor.py:254-303

```python
def _calculate_equity(self,
                     hero_hand: Hand,
                     villain_range: Range,  # ← 使用了range
                     board: Optional[Board],
                     num_opponents: int,
                     game_state: GameState) -> float:
    """计算equity"""
    # ...省略...
    try:
        # 单挑
        if num_opponents == 1:
            iterations = self._get_iterations(game_state)
            # 计算 hero_hand vs villain_range 的equity
            equity = self.equity_calculator.calculate_vs_range(
                hero_hand,
                villain_range,  # ← 这里用了range！
                board,
                iterations=iterations,
                max_combos=max_combos
            )
        # ...多人底池逻辑...
    except Exception as e:
        # 出错返回默认值
        return 0.5

    return equity
```

**用途**：✅ 计算hero_hand vs villain_range的equity

**关键问题**：❌ **equity计算出来后，并不用于开池决策！**

---

## 证据3：AI决策完全不看Range（只看hand_strength）

### 文件：advisor/strategy_engine/advisor.py:355-378

```python
def _get_gto_decision(self,
                     game_state: GameState,
                     gto_ctx: GTOContext) -> DecisionOutput:
    """获取GTO基线决策"""
    if game_state.street == 'preflop':
        # 翻前策略
        try:
            # ✅ 计算真实hand strength
            hand_strength = calculate_preflop_hand_strength(game_state.hero_hand)  # ← 只看strength！

            action_dist = self.gto_baseline.preflop_strategy(
                gto_ctx.position,
                hand_strength,  # ← 传入strength，不是range！
                game_state.action_history,
                game_state.effective_stack,
                equity=gto_ctx.equity,  # equity传了，但在开池决策中不用
                opponent_type=game_state.opponent_type.name if game_state.opponent_type else None
            )
        except:
            action_dist = {'fold': 0.3, 'call': 0.5, 'raise': 0.2}
    else:
        # 翻后策略
        action_dist = self.gto_baseline.postflop_strategy(gto_ctx)

    # ...转换为标准格式...
```

**关键点**：
- ❌ **没有传入hero_range**
- ❌ **没有检查hand是否在range内**
- ❌ **只传入hand_strength**

---

### 文件：advisor/strategy_engine/gto_baseline.py:68-108

```python
def preflop_strategy(self,
                    position: Position,
                    hand_strength: float,  # ← 接收strength，不是range！
                    action_history: List[str],
                    effective_stack: float,
                    equity: float = None,
                    opponent_type: str = None) -> Dict[str, float]:
    """
    翻前GTO策略

    Args:
        position: 位置
        hand_strength: 手牌强度 (0.0-1.0)  ← 参数是strength！
        action_history: 行动历史 ['open', '3bet', ...]
        effective_stack: 有效筹码 (BB)
        equity: vs对手范围的equity (可选)
        opponent_type: 对手类型 (可选)

    Returns:
        动作概率分布
    """
    # 未面对下注：开池或弃牌
    if not action_history or action_history[-1] in ['fold', 'check']:
        return self._preflop_open_strategy(position, hand_strength)  # ← 传入strength

    # 面对open raise
    if action_history[-1] == 'open':
        return self._preflop_vs_open(position, hand_strength, effective_stack)

    # 面对3-bet
    if action_history[-1] == '3bet':
        return self._preflop_vs_3bet(position, hand_strength, effective_stack,
                                     equity=equity, opponent_type=opponent_type)

    # 面对4-bet
    if action_history[-1] == '4bet':
        return self._preflop_vs_4bet(hand_strength, effective_stack)

    # 默认：保守策略
    return {'fold': 0.8, 'call': 0.2}
```

**关键点**：
- ❌ **所有preflop决策方法都接收hand_strength**
- ❌ **没有任何方法接收hero_range**
- ❌ **没有检查hand是否在range内**

---

### 文件：advisor/strategy_engine/gto_baseline.py:110-158（修复后的版本）

```python
def _preflop_open_strategy(self, position: Position, strength: float) -> Dict[str, float]:
    """
    开池策略（包含limp逻辑）

    根据hand strength和位置决定：  ← 只根据strength！
    1. Raise (open) - 强牌
    2. Call (limp) - 中等牌，基于pot odds合理
    3. Fold - 弱牌
    """
    # Raise阈值 - 位置越好，开池范围越宽
    raise_thresholds = {
        Position.UTG: 0.75,
        Position.MP: 0.70,
        Position.CO: 0.65,
        Position.BTN: 0.50,  # ← 硬编码的阈值
        Position.SB: 0.60,
        Position.BB: 1.0,
    }

    # Limp阈值
    limp_thresholds = {
        Position.UTG: 0.60,
        Position.MP: 0.55,
        Position.CO: 0.50,
        Position.BTN: 0.35,  # ← 硬编码的阈值
        Position.SB: 0.40,
        Position.BB: 0.30,
    }

    raise_threshold = raise_thresholds.get(position, 0.70)
    limp_threshold = limp_thresholds.get(position, 0.50)

    if strength >= raise_threshold:  # ← 完全基于strength比较！
        return {'fold': 0.0, 'call': 0.0, 'raise': 1.0}
    elif strength >= limp_threshold:  # ← 完全基于strength比较！
        if position in [Position.BTN, Position.SB]:
            return {'fold': 0.0, 'call': 0.85, 'raise': 0.15}
        else:
            return {'fold': 0.2, 'call': 0.70, 'raise': 0.10}
    else:
        return {'fold': 1.0}
```

**关键点**：
- ❌ **完全基于 strength >= threshold**
- ❌ **没有使用preflop_ranges**
- ❌ **没有检查hand是否在BTN_OPEN_RANGES内**

---

## 证据4：对比 - 如果使用Range应该怎么写

### 当前的错误做法（实际代码）

```python
def _preflop_open_strategy(self, position: Position, strength: float) -> Dict[str, float]:
    """只看strength"""
    raise_threshold = 0.50  # BTN

    if strength >= raise_threshold:  # ← K7o (0.46) < 0.50 → fold
        return {'raise': 1.0}
    else:
        return {'fold': 1.0}
```

**问题**：K7o strength=0.46 < 0.50，所以fold

**矛盾**：BTN_OPEN_RANGES['loose']包含K7o+，但AI不使用这个范围

---

### 正确的做法（应该这样写）

```python
def _preflop_open_strategy(self, position: Position, hand: Hand, tightness: str = 'normal') -> Dict[str, float]:
    """基于预定义范围的开池策略"""
    from advisor.range_engine.preflop_ranges import get_open_range, parse_range_dict

    # 获取该位置的open range
    range_dict = get_open_range(position.value, tightness)
    open_range = parse_range_dict(range_dict)

    # ✅ 检查手牌是否在范围内
    if hand in open_range:
        return {'raise': 1.0}
    elif hand in limp_range:  # 定义limp range
        return {'call': 0.8, 'raise': 0.2}
    else:
        return {'fold': 1.0}
```

**优点**：
- ✅ 使用精心定义的GTO范围
- ✅ K7o在loose模式下会被正确处理
- ✅ 与preflop_ranges.py一致

---

## 证据5：控制变量实验证明

### 实验设计

- **实验1**: 修改K7o strength (0.46→0.55)，保持range不变
- **实验2**: 修改BTN range包含K7o，保持strength不变

### 实验结果

| 实验 | K7o Strength | BTN Range | K7o在Range内？ | 决策 | 结论 |
|------|--------------|-----------|----------------|------|------|
| Baseline | 0.460 | K8o+ | ❌ NO | FOLD | - |
| 实验1 | **0.550** ⬆️ | K8o+ | ❌ NO | **RAISE** ✅ | **决策改变** |
| 实验2 | 0.460 | **K7o+** ⬆️ | ✅ YES | **FOLD** ❌ | **决策不变** |

**结论**：
- ✅ **实验1证明**：修改strength → 决策立即改变
- ✅ **实验2证明**：修改range → 决策完全不变

**这证明AI决策100%依赖strength，0%依赖range！**

---

## 证据6：Range定义 vs 实际决策的矛盾

### K7o的矛盾案例

#### 按照Range系统（preflop_ranges.py）

```python
BTN_OPEN_RANGES['loose'] = {
    'offsuit': ['A2o+', 'K7o+', 'Q8o+', 'J8o+', 'T8o+', '98o'],
}
```

**结论**：K7o在BTN loose范围内 → **应该可以open或limp**

#### 按照Strength系统（hand_strength.py + gto_baseline.py）

```python
# hand_strength.py:139
K7o strength = 0.46

# gto_baseline.py:117
BTN raise_threshold = 0.50
BTN limp_threshold = 0.35  # 修复后

# 决策
0.46 >= 0.50? NO  # 不raise
0.46 >= 0.35? YES  # ✅ limp（修复后）
```

**结论（修复前）**：K7o strength < 0.50 → **fold**

**结论（修复后）**：K7o strength >= 0.35 → **limp** ✅

---

### K8o的矛盾案例

#### 按照Range系统

```python
BTN_OPEN_RANGES['normal'] = {
    'offsuit': ['A5o+', 'K8o+', 'Q9o+', 'J9o+', 'T8o+', '98o'],
}
```

**结论**：K8o在BTN normal范围内 → **应该open**

#### 按照Strength系统

```python
# hand_strength.py:137
K8o strength = 0.49

# gto_baseline.py:124
BTN raise_threshold = 0.50

# 决策
0.49 < 0.50 → fold（修复前）
0.49 >= 0.35 → limp（修复后）
```

**矛盾**：
- Range说：K8o应该在BTN normal open范围内 → raise
- Strength说：K8o (0.49) < threshold (0.50) → fold（修复前）或limp（修复后）

**两套系统完全矛盾！**

---

## 总结：Range是如何被架空的

### Range的定义（精心设计）

```
advisor/range_engine/preflop_ranges.py:
  ├── UTG_OPEN_RANGES (tight/normal/loose)
  ├── MP_OPEN_RANGES
  ├── CO_OPEN_RANGES
  ├── BTN_OPEN_RANGES  ← K7o在loose范围内，K8o在normal范围内
  ├── SB_OPEN_RANGES
  ├── BB_CALL_RANGES
  ├── THREEBET_RANGES
  └── FOURBET_RANGES
```

**状态**：✅ 完整、专业、基于GTO理论

---

### Range的使用（被架空）

```
advisor/strategy_engine/advisor.py:
  ├── _estimate_ranges()  ← ✅ 调用preflop_ranges
  │   └── hero_range, villain_range
  │
  ├── _calculate_equity()  ← ✅ 使用range计算equity
  │   └── equity = calc(hero_hand vs villain_range)
  │
  ├── _get_gto_decision()  ← ❌ 不传入range，只传入strength
  │   └── hand_strength = calculate_preflop_hand_strength(hand)
  │       └── gto_baseline.preflop_strategy(position, hand_strength)  ← 只传strength！
  │
  └── gto_baseline.py:
      └── _preflop_open_strategy(position, strength)  ← ❌ 完全不看range
          └── if strength >= threshold:  ← 只比较strength和固定阈值
                  return {'raise': 1.0}
```

**结论**：
1. ✅ Range被定义了
2. ✅ Range被用于equity计算
3. ❌ **Range完全不参与决策**
4. ❌ **决策100%依赖hand_strength系统**

---

## 架空示意图

```
┌─────────────────────────────────────────────────────────────┐
│         Preflop Ranges（精心设计的GTO范围）                    │
│                                                             │
│  BTN_OPEN_RANGES = {                                        │
│    'normal': {'offsuit': ['A5o+', 'K8o+', ...]}             │
│    'loose':  {'offsuit': ['A2o+', 'K7o+', ...]}             │
│  }                                                          │
│                                                             │
│  ✅ 专业、完整、基于GTO理论                                    │
└─────────────────────────────────────────────────────────────┘
                        │
                        ↓ get_open_range()
                        │
┌─────────────────────────────────────────────────────────────┐
│              advisor._estimate_ranges()                     │
│                                                             │
│  hero_range = parse_range_dict(get_open_range('BTN'))      │
│                                                             │
│  ✅ Range被获取                                              │
└─────────────────────────────────────────────────────────────┘
                        │
                        ↓ 传入equity计算
                        │
┌─────────────────────────────────────────────────────────────┐
│            advisor._calculate_equity()                      │
│                                                             │
│  equity = calc(hero_hand vs villain_range)                  │
│                                                             │
│  ✅ Range被用于equity计算                                    │
└─────────────────────────────────────────────────────────────┘
                        │
                        │ equity值被计算出来
                        ↓
┌─────────────────────────────────────────────────────────────┐
│             advisor._get_gto_decision()                     │
│                                                             │
│  hand_strength = calculate_preflop_hand_strength(hand)      │
│  K7o → strength = 0.46                                      │
│                                                             │
│  ❌ 不传入hero_range                                         │
│  ❌ 不检查hand是否在range内                                   │
│  ✅ 只传入hand_strength                                      │
│                                                             │
│  gto_baseline.preflop_strategy(position, hand_strength)     │
└─────────────────────────────────────────────────────────────┘
                        │
                        ↓ 传入strength
                        │
┌─────────────────────────────────────────────────────────────┐
│        gto_baseline._preflop_open_strategy()                │
│                                                             │
│  BTN raise_threshold = 0.50                                 │
│  BTN limp_threshold = 0.35                                  │
│                                                             │
│  if strength >= 0.50:  # K7o (0.46) < 0.50                  │
│      return {'raise': 1.0}                                  │
│  elif strength >= 0.35:  # K7o (0.46) >= 0.35 ✅            │
│      return {'call': 0.85, 'raise': 0.15}  # limp           │
│  else:                                                      │
│      return {'fold': 1.0}                                   │
│                                                             │
│  ❌ 完全基于strength vs threshold                            │
│  ❌ 完全不使用preflop_ranges                                 │
│  ❌ Range被架空！                                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 问题总结

1. **Range系统存在但不被使用**
   - ✅ 定义了完整的preflop ranges
   - ✅ 用于equity计算
   - ❌ **完全不用于决策**

2. **Strength系统主导决策**
   - ✅ 简单高效
   - ❌ 不考虑位置、对手、pot odds
   - ❌ 与range系统矛盾

3. **修复后的状态**
   - ✅ 添加了limp逻辑
   - ✅ K7o现在会limp而不是fold
   - ⚠️ 但仍然依赖strength，不依赖range

4. **长期解决方案**
   - 需要重构决策系统，改为基于range或equity
   - 或者至少让两套系统（range vs strength）保持一致

---

## 修复前后对比

### 修复前（只有fold和raise）

```python
# K7o在BTN
strength = 0.46
threshold = 0.50

if strength >= threshold:
    return {'raise': 1.0}
else:
    return {'fold': 1.0}  # ← K7o走这里，损失0.5BB
```

**结果**：K7o fold（-0.5BB EV损失）

---

### 修复后（添加了limp）

```python
# K7o在BTN
strength = 0.46
raise_threshold = 0.50
limp_threshold = 0.35

if strength >= raise_threshold:
    return {'raise': 1.0}
elif strength >= limp_threshold:  # ← K7o走这里
    return {'call': 0.85, 'raise': 0.15}  # limp
else:
    return {'fold': 1.0}
```

**结果**：K7o limp 85%（✅ 正确，不再损失EV）

---

### 理想状态（使用Range）

```python
# K7o在BTN
range_dict = get_open_range('BTN', 'loose')
open_range = parse_range_dict(range_dict)

if hand in open_range:  # K7o在loose范围内
    return {'raise': 1.0}  # or mixed strategy
elif hand in limp_range:
    return {'call': 0.85, 'raise': 0.15}
else:
    return {'fold': 1.0}
```

**优点**：
- ✅ 使用精心定义的GTO范围
- ✅ 可以根据对手类型调整tightness（tight/normal/loose）
- ✅ 与range系统完全一致

---

## 结论

**Range被架空的完整证据链**：

1. ✅ Range被精心定义（preflop_ranges.py）
2. ✅ Range被获取（advisor._estimate_ranges）
3. ✅ Range被用于equity计算（advisor._calculate_equity）
4. ❌ **Range不参与决策**（advisor._get_gto_decision只传strength）
5. ❌ **决策完全基于strength vs threshold**（gto_baseline._preflop_open_strategy）
6. ✅ **控制变量实验证明**：修改range不改变决策，修改strength立即改变决策

**当前状态**：
- ✅ 修复了limp逻辑，K7o不再fold
- ⚠️ 但仍然依赖strength系统，range仍然被架空

**推荐长期方案**：
- 重构决策系统，改为基于range或equity
- 或者调整strength值和threshold，使其与range系统保持一致
