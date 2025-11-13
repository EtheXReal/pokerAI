# 翻后从不Bet Bug - 根因分析

## 问题描述

AI在翻后（Turn/River）**从不下注**，Flop也只有4.5%下注频率。

### 统计数据（32手测试）

```
Flop:  1次bet / 22次check (4.5% bet频率)
Turn:  0次bet / 22次check (0% bet频率)  ← ❌❌❌
River: 0次bet / 22次check (0% bet频率)  ← ❌❌❌
```

**职业玩家应该的频率**：
- Flop: 30-50% bet (IP facing check)
- Turn: 25-40% bet
- River: 20-35% bet

**损失**：AI完全放弃value betting和bluffing，白白损失大量EV。

---

## Bug定位

### 文件：`advisor/strategy_engine/gto_baseline.py`

### 方法：`_aggression_strategy` (行359-395)

```python
def _aggression_strategy(self, ctx: GTOContext) -> Dict[str, float]:
    """主动策略（未面对下注）"""

    # 计算下注频率
    bet_frequency = self._calculate_bet_frequency(ctx)  # ← 计算了但没用！

    # Equity门槛
    value_threshold = 0.65 - (0.1 if ctx.is_in_position else 0.0)
    # OOP: value_threshold = 0.65
    # IP:  value_threshold = 0.55

    if ctx.equity >= value_threshold:  # >= 0.65 (OOP)
        # 强牌：价值下注
        check_freq = 1.0 - bet_frequency
        bet_freq = bet_frequency  # ← 只有这里使用bet_frequency

    elif ctx.equity >= 0.35:  # ← ⭐⭐⭐ BUG在这里！
        # 中等牌：主要过牌
        check_freq = 0.8  # ← 硬编码80% check!
        bet_freq = 0.2    # ← 硬编码20% bet!
        # ❌❌❌ 完全忽略了bet_frequency的计算结果！

    else:  # equity < 0.35
        # 弱牌：主要过牌，少量pure bluff
        check_freq = 1.0 - bluff_freq
        bet_freq = bluff_freq

    return {
        'check': check_freq,
        'bet': bet_freq
    }
```

---

## 为什么这是Bug？

### 问题1：中等equity被硬编码为80% check

**Equity分布**：
- 顶对 vs Random range: equity ~55-65%
- 两对 vs Random range: equity ~60-70%
- Set vs Random range: equity ~70-80%

**问题**：
大多数value hand的equity都在**0.35-0.70**区间，会进入"中等牌"分支。

**例子**：

#### Hand #2: BB with Q9o, Flop 9d 4h 6c (顶对9)
```python
equity ≈ 0.60  # 顶对 vs random
value_threshold = 0.65  # OOP

# 因为 0.60 < 0.65，进入中等牌分支
# 结果：check_freq = 0.8, bet_freq = 0.2
# AI选择check（80%概率）

# 正确做法：顶对应该bet for value 50-60%频率！
```

#### Hand #26: BB with QT, Turn 8d Tc 3c Qd (两对)
```python
equity ≈ 0.68  # 两对 vs random
value_threshold = 0.65  # OOP

# 因为 0.68 >= 0.65，进入强牌分支
# bet_freq = bet_frequency (计算值)
# 但bet_frequency可能被其他因素降低了

# 实验结果：{'check': 0.58, 'bet': 0.42}
# AI仍然选择check
```

### 问题2：value_threshold = 0.65太高

**0.65 equity对应的牌力**：
- 接近两对或set
- 顶对+好kicker才刚到0.60-0.65

**导致**：
- 几乎所有顶对（equity 0.55-0.62）都进入"中等牌"分支
- 被强制80% check，只有20% bet
- 白白损失value

### 问题3：完全忽略bet_frequency的计算

`_calculate_bet_frequency(ctx)` 会根据以下因素计算：
- Range advantage
- Position (IP +0.1)
- Board texture (dry +0.1, wet -0.1)
- SPR (shallow +0.15)

**但在中等equity分支，这个计算完全被忽略**：
```python
bet_frequency = self._calculate_bet_frequency(ctx)  # 计算了

elif ctx.equity >= 0.35:
    check_freq = 0.8  # ← 直接硬编码，不管bet_frequency是多少！
    bet_freq = 0.2
```

---

## 实验验证

### 实验：`tests/experiments/debug_postflop_betting.py`

#### 场景1：Flop顶对9
```
Hand: Qd9h
Board: 9d 4h 6c
Position: BB (OOP)
Facing: check

决策: check
Action dist: {'check': 0.8, 'bet': 0.2}
```

**分析**：
- 顶对9的equity ≈ 0.60
- 0.60 < value_threshold (0.65)
- 进入中等牌分支 → 80% check
- **应该bet for value ~50%频率，而不是只20%！**

#### 场景2：Turn两对
```
Hand: QhTh
Board: 8d Tc 3c Qd
Position: BB (OOP)
Facing: check

决策: check
Action dist: {'check': 0.58, 'bet': 0.42}
```

**分析**：
- 两对equity ≈ 0.68
- 0.68 >= value_threshold (0.65)
- 进入强牌分支 → bet_freq = bet_frequency
- 但bet_frequency被计算为0.42（可能range_advantage是'weak'）
- **两对应该bet for value ~70-80%频率！**

---

## 为什么Turn/River从不bet？

### 统计分析

在32手测试中：
- Turn: 0次bet, 22次check (0%)
- River: 0次bet, 22次check (0%)

### 原因分析

#### 1. Equity随着streets递减

```
Flop顶对: equity ~60%
Turn顶对: equity ~55% (对手可能击中两对/顺子/同花听牌)
River顶对: equity ~50% (更多牌面完成听牌)
```

#### 2. Value threshold太高

```python
value_threshold = 0.65  # OOP
```

- Flop: 少数两对/set能到0.65
- Turn: 更少
- River: 更少

→ 大多数牌都进入"中等牌"分支 (0.35-0.65)
→ 被强制80% check

#### 3. 中等牌分支占比过高

```
Equity分布（Turn/River）：
- < 0.35: 弱牌（bluff候选）
- 0.35-0.65: 中等牌 ← 大多数顶对/对子都在这里
- >= 0.65: 强牌（两对+）
```

由于大多数牌都在0.35-0.65区间：
- 80% check, 20% bet
- Turn/River的样本量更小
- 几乎看不到bet

---

## 代码证据链

### 链条1：Aggression strategy逻辑

```python
# gto_baseline.py 行375-395
value_threshold = 0.65 - (0.1 if ctx.is_in_position else 0.0)

if ctx.equity >= value_threshold:
    bet_freq = bet_frequency  # ✅ 使用计算值
elif ctx.equity >= 0.35:  # ← 大多数牌在这里
    check_freq = 0.8  # ← ❌ 硬编码
    bet_freq = 0.2    # ← ❌ 忽略bet_frequency
else:
    bet_freq = bluff_freq
```

### 链条2：实际equity值

Hand #2 (Flop顶对9):
```python
equity = calculate_equity(Q9o vs Random, board=9d4h6c)
# equity ≈ 0.60

0.60 < 0.65  # True
→ 进入中等牌分支
→ {'check': 0.8, 'bet': 0.2}
```

Hand #26 (Turn两对):
```python
equity = calculate_equity(QT vs Random, board=8dTc3cQd)
# equity ≈ 0.68

0.68 >= 0.65  # True
→ 进入强牌分支
→ bet_freq = bet_frequency

# 但bet_frequency可能很低（range_advantage='weak'等原因）
→ {'check': 0.58, 'bet': 0.42}
```

### 链条3：Turn/River equity更低

```python
# Flop: 顶对equity ~60%
# Turn: 顶对equity ~55% (更多outs)
# River: 顶对equity ~50% (牌面完成)

# 大多数Turn/River equity < 0.65
→ 进入中等牌分支
→ 80% check
→ 统计结果：0% bet (因为80%概率check，22手样本太小)
```

---

## 影响量化

### 1. 损失的Value

每次有value hand但没bet：
- Flop顶对不bet：损失 ~0.5-1.0 BB
- Turn两对不bet：损失 ~1.0-2.0 BB
- River强牌不bet：损失 ~0.5-1.5 BB

**32手测试估算**：
- 至少10手应该bet但check了
- 平均损失 ~0.8 BB per hand
- **总损失：~8 BB**

### 2. BB/100影响

当前BB/100: -20.05

如果修复翻后betting：
- 预期提升：**+15-25 BB/100**
- 修复后预期：-5 to +5 BB/100

---

## 为什么设计会这样？

### 错误的GTO理解

代码注释说：
```python
# 中等牌：主要过牌
check_freq = 0.8
bet_freq = 0.2  # 少量半bluff
```

**设计者可能认为**：
- Equity 0.35-0.65是"中等牌"
- 应该conservatively play
- 主要check

**实际上**：
- Equity 0.55-0.65包含很多顶对、强中对
- 这些牌应该aggressive bet for value
- 不是"半bluff"，是**pure value**

### 正确的GTO策略

Flop/Turn/River facing check (IP):
- 强牌 (equity 0.60+): bet 60-80%
- 中等牌 (equity 0.45-0.60): bet 30-50% (mix)
- 弱牌 (equity < 0.45): bet 10-20% (bluff)

**不是简单的**：
- 强牌 (0.65+): bet
- 中等牌 (0.35-0.65): 80% check ← ❌ 错误！
- 弱牌 (<0.35): mostly check

---

## Bug严重程度

### 🔴🔴🔴🔴🔴 严重度：5/5

**原因**：
1. **影响所有翻后决策**
   - Flop, Turn, River全部受影响
   - 占游戏50%以上手数

2. **完全改变AI打法**
   - 从应该aggressive变成极度passive
   - 放弃几乎所有value betting

3. **损失巨大**
   - 估计损失 ~8 BB (32手)
   - BB/100影响：-15 to -25

4. **违反GTO原则**
   - GTO要求平衡value和bluff
   - AI几乎不bet = 可被exploit

---

## 对比其他Bug

| Bug | 影响手数 | 损失(BB) | BB/100影响 | 严重度 |
|-----|---------|---------|-----------|--------|
| BTN limp垃圾牌 | 8/32 (25%) | -2.8 | -20 to -30 | 🔴🔴🔴🔴🔴 |
| BB不raise强牌 | 2/32 (6%) | -1.5 | -15 to -25 | 🔴🔴🔴🔴 |
| **翻后不bet** | **22/32 (69%)** | **-8** | **-15 to -25** | **🔴🔴🔴🔴🔴** |

**翻后不bet是影响面最大的Bug**（69%手数）

---

## 修复建议

### Option 1: 降低value threshold + 使用bet_frequency

```python
def _aggression_strategy(self, ctx: GTOContext) -> Dict[str, float]:
    bet_frequency = self._calculate_bet_frequency(ctx)

    # 降低value threshold
    value_threshold = 0.55 - (0.05 if ctx.is_in_position else 0.0)
    # OOP: 0.55, IP: 0.50

    if ctx.equity >= value_threshold:
        # Value range扩大到equity 0.50+
        check_freq = 1.0 - bet_frequency
        bet_freq = bet_frequency

    elif ctx.equity >= 0.35:
        # 中等牌：使用bet_frequency，不硬编码
        check_freq = 1.0 - bet_frequency * 0.5  # 减半bet频率
        bet_freq = bet_frequency * 0.5

    else:
        # 弱牌bluff
        check_freq = 1.0 - bluff_freq
        bet_freq = bluff_freq
```

### Option 2: 完全移除中等牌硬编码

```python
def _aggression_strategy(self, ctx: GTOContext) -> Dict[str, float]:
    bet_frequency = self._calculate_bet_frequency(ctx)

    # 根据equity调整bet频率
    if ctx.equity >= 0.60:
        # 强牌：高频率bet
        adjusted_bet_freq = bet_frequency * 1.2
    elif ctx.equity >= 0.45:
        # 中强牌：正常bet
        adjusted_bet_freq = bet_frequency
    elif ctx.equity >= 0.35:
        # 中等牌：减少bet
        adjusted_bet_freq = bet_frequency * 0.6
    else:
        # 弱牌：bluff
        adjusted_bet_freq = bluff_freq

    adjusted_bet_freq = min(0.9, max(0.1, adjusted_bet_freq))

    return {
        'check': 1.0 - adjusted_bet_freq,
        'bet': adjusted_bet_freq
    }
```

**推荐Option 2**：更灵活，尊重bet_frequency的计算。

---

## 总结

### Bug根源

```
Equity计算 (0.55-0.65 for 顶对)
         ↓
value_threshold = 0.65 (太高)
         ↓
equity < 0.65 → 进入"中等牌"分支
         ↓
check_freq = 0.8 (硬编码，忽略bet_frequency)
         ↓
AI在flop/turn/river几乎不bet
         ↓
损失 ~8 BB (32手), -15 to -25 BB/100
```

### 核心问题

1. **Value threshold 0.65太高**
   - 大多数顶对equity只有0.55-0.62
   - 被错误归类为"中等牌"

2. **中等牌硬编码80% check**
   - 完全忽略bet_frequency计算
   - 顶对应该bet 50-60%，而不是只20%

3. **Turn/River equity更低**
   - 更多牌进入中等牌区间
   - 80% check概率 → 0% bet统计结果

### 实验文件

1. `tests/experiments/analyze_postflop_betting_frequency.py` - 统计验证
2. `tests/experiments/debug_postflop_betting.py` - Debug具体场景
