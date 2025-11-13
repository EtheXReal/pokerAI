# AI翻前决策流程分析

## 问题：AI决策依赖hand_strength还是range？

### 完整决策流程追踪

#### 步骤1: 调用入口（advisor.py:118-186）

```python
def advise(self, game_state: GameState) -> DecisionOutput:
    # 步骤1: 推断范围
    hero_range, villain_range = self._estimate_ranges(game_state)  # Line 129

    # 步骤2: 计算equity
    equity = self._calculate_equity(
        game_state.hero_hand,
        villain_range,  # ← 使用range计算equity
        game_state.board,
        game_state.num_opponents,
        game_state
    )  # Line 132

    # 步骤6: GTO基线决策
    gto_decision = self._get_gto_decision(game_state, gto_ctx)  # Line 157
```

#### 步骤2: GTO决策（advisor.py:355-378）

```python
def _get_gto_decision(self, game_state: GameState, gto_ctx: GTOContext) -> DecisionOutput:
    if game_state.street == 'preflop':
        # ✅ 关键：计算hand_strength
        hand_strength = calculate_preflop_hand_strength(game_state.hero_hand)  # Line 363

        # ✅ 关键：调用preflop_strategy，传入hand_strength
        action_dist = self.gto_baseline.preflop_strategy(
            gto_ctx.position,
            hand_strength,  # ← 传入strength，不是range！
            game_state.action_history,
            game_state.effective_stack,
            equity=gto_ctx.equity,  # equity也传了，但不是主要依据
            opponent_type=...
        )  # Line 365
```

#### 步骤3: GTO策略（gto_baseline.py:68-108）

```python
def preflop_strategy(self,
                    position: Position,
                    hand_strength: float,  # ← 接收strength
                    action_history: List[str],
                    effective_stack: float,
                    equity: float = None,
                    opponent_type: str = None) -> Dict[str, float]:

    # 未面对下注：开池或弃牌
    if not action_history or action_history[-1] in ['fold', 'check']:
        return self._preflop_open_strategy(position, hand_strength)  # Line 92

    # 面对open raise
    if action_history[-1] == 'open':
        return self._preflop_vs_open(position, hand_strength, effective_stack)

    # 面对3-bet（这里会用equity）
    if action_history[-1] == '3bet':
        return self._preflop_vs_3bet(position, hand_strength, effective_stack,
                                     equity=equity, opponent_type=opponent_type)
```

#### 步骤4: 开池决策（gto_baseline.py:110-127）

```python
def _preflop_open_strategy(self, position: Position, strength: float) -> Dict[str, float]:
    """开池策略"""
    position_thresholds = {
        Position.UTG: 0.75,
        Position.MP: 0.70,
        Position.CO: 0.65,
        Position.BTN: 0.50,  # ← K7o问题的关键
        Position.SB: 0.60,
        Position.BB: 1.0,
    }

    threshold = position_thresholds.get(position, 0.70)

    if strength >= threshold:  # ← 完全基于strength！
        return {'fold': 0.0, 'raise': 1.0}
    else:
        return {'fold': 1.0}
```

---

## 结论

### AI翻前决策依赖：**100% hand_strength，0% range**

**证据**：
1. ✅ `_preflop_open_strategy` 只接收 `strength` 参数
2. ✅ 决策完全基于 `strength >= threshold`
3. ✅ Range**完全不参与决策**，只用于equity计算
4. ✅ Equity在某些场景下使用（如vs 3-bet），但在开池决策中**完全不用**

### Range的实际用途

Range只用于两个地方：
1. **Equity计算** - `_calculate_equity(hero_hand, villain_range, board)`
   - 计算我们的牌 vs 对手范围的胜率
   - 在某些场景下参考（如vs 3-bet）
2. **Range Advantage评估** - `_assess_range_advantage(hero_range, villain_range, board)`
   - 评估范围优势（strong/medium/weak）
   - 但这个只影响翻后决策，不影响翻前开池决策

### Range **不参与**的决策

1. ❌ 开池决策（`_preflop_open_strategy`）- 只用strength
2. ❌ 面对open决策（`_preflop_vs_open`）- 只用strength
3. ❌ 手牌是否在开池范围内的判断 - **根本不检查**

---

## Hand Strength计算方法

### 计算逻辑（hand_strength.py:11-66）

```python
def calculate_preflop_hand_strength(hand: Hand) -> float:
    """
    将手牌映射到0.0-1.0的强度值

    分类处理：
    1. 对子 → _pair_strength()
    2. Ace高张 → _ace_high_strength()
    3. King高张 → _king_high_strength()
    4. Queen高张 → _queen_high_strength()
    5. Jack高张 → _jack_high_strength()
    6. Ten高张 → _ten_high_strength()
    7. 其他 → _other_strength()
    """
    rank1 = hand.cards[0].rank
    rank2 = hand.cards[1].rank
    suited = (hand.cards[0].suit == hand.cards[1].suit)
    is_pair = (rank1 == rank2)

    if is_pair:
        return _pair_strength(rank1)

    high_rank = max(rank1, rank2)
    low_rank = min(rank1, rank2)

    if high_rank == Rank.ACE:
        return _ace_high_strength(low_rank, suited)
    # ... 依次处理
```

### K7o的计算（hand_strength.py:126-141）

```python
def _king_high_strength(low_rank: Rank, suited: bool) -> float:
    if low_rank.value >= 12:  # KQ
        return 0.78 if suited else 0.70
    elif low_rank.value >= 11:  # KJ
        return 0.74 if suited else 0.65
    elif low_rank.value >= 10:  # KT
        return 0.70 if suited else 0.61
    elif low_rank.value >= 9:  # K9
        return 0.64 if suited else 0.53
    elif low_rank.value >= 8:  # K8
        return 0.62 if suited else 0.49
    elif low_rank.value >= 7:  # K7
        return 0.60 if suited else 0.46  # ← K7o = 0.46
    else:  # K6-K2
        return 0.58 if suited else 0.42
```

### Strength分级标准

```python
# hand_strength.py:20-28注释
强度标准:
- 0.95-1.00: AA, KK
- 0.85-0.95: QQ, JJ, AKs
- 0.75-0.85: TT, 99, AKo, AQs, AJs
- 0.65-0.75: 88-22, AQo, KQs, AJo, ATs
- 0.55-0.65: Suited connectors, suited Ax
- 0.45-0.55: 中等suited, offsuit broadway
- < 0.45: 弱牌
```

---

## Hand Strength计算是否科学？

### ✅ 优点

1. **简单高效** - O(1)查表，无需计算
2. **考虑了关键因素**：
   - ✅ 对子强度（AA > KK > QQ...）
   - ✅ 高牌强度（A > K > Q...）
   - ✅ 同花加分（suited bonus）
   - ✅ 连张加分（connector bonus）

3. **相对合理的分级**：
   - AA (1.00), KK (0.95), QQ (0.90) - 符合直觉
   - AKs (0.92) > AKo (0.85) - 同花优势
   - K9o (0.53) > K7o (0.46) - 踢脚牌影响

### ❌ 问题

#### 1. **不考虑位置**
```python
# K7o在不同位置的真实价值：
# UTG: 几乎垃圾（fold）
# BTN: 可玩牌（limp/raise）
# 但strength永远是0.46，不会根据位置调整
```

#### 2. **不考虑对手范围**
```python
# K7o vs 不同对手的equity：
# vs Random (100%范围): ~50% equity
# vs UTG open (tight范围): ~35% equity
# vs BTN open (loose范围): ~42% equity
# 但strength永远是0.46
```

#### 3. **不考虑动态因素**
- ❌ SPR（深筹码 vs 浅筹码）
- ❌ 对手类型（vs FISH vs vs NIT）
- ❌ 已投入筹码（pot odds）

#### 4. **阈值过于粗糙**
```python
# BTN threshold = 0.50
# K8o (0.49) - fold  ← 为什么0.49就不能open？
# K7o (0.46) - fold
# K9o (0.53) - raise ← 为什么0.53就能open？
#
# 0.46-0.53之间只差0.07，但决策完全相反
```

#### 5. **与Preflop Ranges不一致**

```python
# BTN_OPEN_RANGES['normal'] 包含：
# 'offsuit': ['A5o+', 'K8o+', 'Q9o+', 'J9o+', 'T8o+', '98o']
# 这说明K8o应该能open

# 但hand_strength系统：
# K8o = 0.49 < 0.50 → fold ✗
#
# 两套系统矛盾！
```

#### 6. **Suited Bonus可能过小**

```python
# K7s vs K7o的真实equity差距：
# K7s vs random: ~52%
# K7o vs random: ~50%
# 差距: ~2%

# 但strength差距：
# K7s: 0.60
# K7o: 0.46
# 差距: 0.14 (14%)

# Suited bonus = 0.14 可能合理，但需要验证
```

---

## 更科学的方法

### 方案1: 基于真实Equity（推荐）

```python
def _preflop_open_strategy(self, position, hand, villain_range):
    """基于真实equity的开池策略"""
    # 计算真实equity
    equity = calculate_equity(hand, villain_range)

    # 基于equity的阈值（比strength更准确）
    equity_thresholds = {
        Position.BTN: 0.48,  # 需要48%+ equity才open
    }

    threshold = equity_thresholds.get(position, 0.52)

    if equity >= threshold:
        return {'raise': 1.0}
    elif equity >= threshold - 0.15:  # Limp range
        return {'call': 0.8, 'raise': 0.2}
    else:
        return {'fold': 1.0}
```

**优点**：
- ✅ 考虑对手范围
- ✅ 动态调整（vs tight vs loose）
- ✅ 更准确

**缺点**：
- ⚠️ 需要计算（但已有equity calculator）

### 方案2: 直接使用Preflop Ranges（最简单）

```python
def _preflop_open_strategy(self, position, hand, tightness='normal'):
    """基于预定义范围的开池策略"""
    from advisor.range_engine.preflop_ranges import get_open_range, parse_range_dict

    # 获取该位置的open range
    range_dict = get_open_range(position.value, tightness)
    open_range = parse_range_dict(range_dict)

    # 检查手牌是否在范围内
    if hand in open_range:
        return {'raise': 1.0}
    elif hand in extended_limp_range:  # 定义limp range
        return {'call': 0.8, 'raise': 0.2}
    else:
        return {'fold': 1.0}
```

**优点**：
- ✅ 与已定义的GTO范围一致
- ✅ 专业、精确
- ✅ 易于维护

**缺点**：
- ⚠️ 需要定义limp范围

### 方案3: 混合方法

保留strength系统，但：
1. 调整阈值（BTN: 0.50 → 0.45）
2. 添加limp range
3. 微调K7o/K8o的strength值

---

## 控制变量实验设计

### 实验目的
证明AI翻前决策依赖hand_strength还是range

### 实验设计

#### 实验1: 修改Hand Strength（保持Range不变）

**修改**：将K7o的strength从0.46提高到0.55
```python
# hand_strength.py:139
elif low_rank.value >= 7:  # K7
    return 0.62 if suited else 0.55  # 0.46 → 0.55
```

**预期**：
- 如果决策依赖strength：K7o应该从fold变为raise ✅
- 如果决策依赖range：K7o应该继续fold（因为不在BTN normal range内）

#### 实验2: 修改Range（保持Hand Strength不变）

**修改**：将BTN normal range扩展到包含K7o
```python
# preflop_ranges.py:105
'offsuit': ['A5o+', 'K7o+', 'Q9o+', 'J9o+', 'T8o+', '98o'],  # K8o+ → K7o+
```

**预期**：
- 如果决策依赖range：K7o应该从fold变为raise ✅
- 如果决策依赖strength：K7o应该继续fold（strength仍然是0.46 < 0.50）

#### 实验3: 同时修改（验证实验）

**修改**：同时修改strength和range
**预期**：K7o应该raise（无论依赖哪个系统）

### 运行方法

```bash
# Baseline（不修改）
python tests/performance/test_full_postflop_10hands.py

# 实验1（修改strength）
# 修改 hand_strength.py:139
python tests/performance/test_full_postflop_10hands.py

# 实验2（修改range）
# 修改 preflop_ranges.py:105
python tests/performance/test_full_postflop_10hands.py
```

### 结果判断

| 实验 | Strength | Range | K7o决策 | 结论 |
|------|----------|-------|---------|------|
| Baseline | 0.46 | K8o+ | Fold | - |
| 实验1 | 0.55 | K8o+ | ? | 如果Raise→依赖strength |
| 实验2 | 0.46 | K7o+ | ? | 如果Fold→依赖strength |

---

## 总结

### 当前AI决策机制

**100%依赖hand_strength，0%依赖range**

### Hand Strength的科学性

**部分科学，但有明显缺陷**：
- ✅ 考虑了对子、高牌、同花、连张
- ❌ 不考虑位置、对手范围、SPR、pot odds
- ❌ 与预定义的GTO ranges不一致
- ❌ 阈值过于粗糙（0.01的差距导致完全相反的决策）

### 推荐改进方向

1. **短期**：调整阈值 + 添加limp逻辑
2. **长期**：改为基于Preflop Ranges或真实Equity的决策系统
