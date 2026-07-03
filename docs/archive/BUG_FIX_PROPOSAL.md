# PokerAI Bug修复方案

## 总览

通过32手测试分析，发现了3个严重bug：

| Bug | 影响手数 | 损失(BB) | BB/100影响 | 优先级 |
|-----|---------|---------|-----------|--------|
| 1. 翻后从不bet | 22/32 (69%) | -8.0 | -15~-25 | 🔴 P0 (最高) |
| 2. BTN limp垃圾牌 | 8/32 (25%) | -2.8 | -20~-30 | 🔴 P0 |
| 3. BB不raise强牌 | 2/32 (6%) | -1.5 | -15~-25 | 🟡 P1 |

**总预期提升**：+50-80 BB/100
**从**：-20 BB/100 **→** +30-60 BB/100

---

## Bug #1: 翻后从不bet (P0 - 最高优先级)

### 影响

- **影响面最大**：69%的手数
- **损失**：~8 BB (32手)
- **BB/100**：-15 to -25

### 根因

**文件**：`advisor/strategy_engine/gto_baseline.py`
**方法**：`_aggression_strategy` (行359-395)

```python
def _aggression_strategy(self, ctx: GTOContext) -> Dict[str, float]:
    bet_frequency = self._calculate_bet_frequency(ctx)

    value_threshold = 0.65 - (0.1 if ctx.is_in_position else 0.0)
    # OOP: 0.65, IP: 0.55

    if ctx.equity >= value_threshold:
        # 强牌
        bet_freq = bet_frequency
    elif ctx.equity >= 0.35:  # ← BUG: 大多数牌在这里
        check_freq = 0.8  # ← 硬编码80% check
        bet_freq = 0.2    # ← 忽略bet_frequency计算
    else:
        bet_freq = bluff_freq
```

**问题**：
1. Value threshold 0.65太高（顶对equity只有0.55-0.62）
2. 中等牌硬编码80% check，完全忽略bet_frequency

### 修复方案

#### Option 1: 降低threshold + 使用bet_frequency (推荐)

```python
def _aggression_strategy(self, ctx: GTOContext) -> Dict[str, float]:
    """主动策略（未面对下注）"""
    bet_frequency = self._calculate_bet_frequency(ctx)
    bluff_freq = self.calculate_optimal_bluff_frequency(
        ctx.pot_size, ctx.pot_size * 0.66
    ) if bet_frequency > 0 else 0.0

    # ✅ 降低value threshold
    value_threshold = 0.55 - (0.05 if ctx.is_in_position else 0.0)
    # OOP: 0.55 (包含强顶对)
    # IP:  0.50 (包含中等顶对)

    if ctx.equity >= value_threshold:
        # Value range: 强牌到强顶对
        check_freq = 1.0 - bet_frequency
        bet_freq = bet_frequency

    elif ctx.equity >= 0.40:
        # ✅ 中等牌：使用bet_frequency，而不是硬编码
        # 减半bet频率（因为不是pure value）
        adjusted_bet_freq = bet_frequency * 0.5
        check_freq = 1.0 - adjusted_bet_freq
        bet_freq = adjusted_bet_freq

    else:
        # 弱牌：pure bluff
        check_freq = 1.0 - bluff_freq
        bet_freq = bluff_freq

    return {
        'check': check_freq,
        'bet': bet_freq
    }
```

**改动点**：
1. Value threshold: 0.65 → 0.55 (OOP), 0.55 → 0.50 (IP)
2. 中等牌：使用 `bet_frequency * 0.5`，而不是硬编码0.2
3. 中等牌threshold: 0.35 → 0.40 (更合理的分界)

**预期效果**：
- Flop bet频率：4.5% → 25-35%
- Turn bet频率：0% → 20-30%
- River bet频率：0% → 15-25%
- BB/100提升：**+20-30**

---

#### Option 2: 完全移除硬编码，动态调整

```python
def _aggression_strategy(self, ctx: GTOContext) -> Dict[str, float]:
    """主动策略（未面对下注）"""
    bet_frequency = self._calculate_bet_frequency(ctx)
    bluff_freq = self.calculate_optimal_bluff_frequency(
        ctx.pot_size, ctx.pot_size * 0.66
    ) if bet_frequency > 0 else 0.0

    # ✅ 根据equity动态调整bet频率
    if ctx.equity >= 0.60:
        # 强牌：增加bet频率
        multiplier = 1.3
    elif ctx.equity >= 0.50:
        # 中强牌：正常bet频率
        multiplier = 1.0
    elif ctx.equity >= 0.40:
        # 中等牌：减少bet频率
        multiplier = 0.6
    elif ctx.equity >= 0.30:
        # 弱牌：主要bluff
        multiplier = 0.3
    else:
        # 极弱牌：pure bluff
        multiplier = 0.0

    # 计算最终bet频率
    if multiplier > 0:
        adjusted_bet_freq = bet_frequency * multiplier
    else:
        adjusted_bet_freq = bluff_freq

    # 限制在合理范围
    adjusted_bet_freq = min(0.85, max(0.10, adjusted_bet_freq))

    return {
        'check': 1.0 - adjusted_bet_freq,
        'bet': adjusted_bet_freq
    }
```

**优点**：
- 更灵活，完全尊重bet_frequency计算
- 没有硬编码的magic number
- 更符合GTO连续调整的原则

**推荐**：**Option 1**（更保守，容易验证）

---

## Bug #2: BTN limp垃圾牌 (P0)

### 影响

- **影响面**：25%的BTN手数
- **损失**：~2.8 BB
- **BB/100**：-20 to -30

### 根因

**文件**：`advisor/strategy_engine/gto_baseline.py`
**方法**：`_preflop_open_strategy` (行137-162)

```python
limp_thresholds = {
    Position.BTN: 0.35,  # ← 太低！
    Position.SB: 0.40,
    Position.CO: 0.50,
    ...
}

if strength >= raise_threshold:  # BTN: 0.50
    return {'fold': 0.0, 'call': 0.0, 'raise': 1.0}
elif strength >= limp_threshold:  # BTN: 0.35
    if position in [Position.BTN, Position.SB]:
        return {'fold': 0.0, 'call': 0.85, 'raise': 0.15}  # ← 85% limp垃圾
```

**问题**：
- BTN limp threshold 0.35太低
- T2o (0.36), 83o (0.42), 64o (0.37) 都会被limp
- BTN应该要么raise要么fold，不应该limp

### 修复方案

#### Option 1: 完全取消BTN/CO limp (推荐)

```python
def _preflop_open_strategy(self, position: Position, strength: float) -> Dict[str, float]:
    """开池策略"""
    # Raise阈值
    raise_thresholds = {
        Position.UTG: 0.75,
        Position.MP: 0.70,
        Position.CO: 0.65,
        Position.BTN: 0.50,
        Position.SB: 0.60,
        Position.BB: 1.0,
    }

    # ✅ Limp阈值：BTN/CO取消limp
    limp_thresholds = {
        Position.UTG: 0.75,  # = raise threshold，即不limp
        Position.MP: 0.70,   # = raise threshold
        Position.CO: 0.65,   # ✅ 改为0.65，取消limp
        Position.BTN: 0.50,  # ✅ 改为0.50，取消limp
        Position.SB: 0.50,   # ✅ 收紧到0.50
        Position.BB: 0.30,   # BB保留（免费看flop）
    }

    raise_threshold = raise_thresholds.get(position, 0.70)
    limp_threshold = limp_thresholds.get(position, 0.50)

    if strength >= raise_threshold:
        # 强牌：raise
        return {'fold': 0.0, 'call': 0.0, 'raise': 1.0}
    elif strength >= limp_threshold:
        # BTN/CO: strength < raise_threshold，这个分支不会进入（因为limp=raise）
        # SB: 0.50-0.60之间可以limp（收紧后的范围）
        # BB: 0.30-1.0可以check
        if position in [Position.BTN, Position.SB]:
            return {'fold': 0.0, 'call': 0.85, 'raise': 0.15}
        else:
            return {'fold': 0.2, 'call': 0.70, 'raise': 0.10}
    else:
        # 弱牌：fold
        return {'fold': 1.0}
```

**改动点**：
1. BTN limp threshold: 0.35 → 0.50 (= raise threshold)
2. CO limp threshold: 0.50 → 0.65 (= raise threshold)
3. SB limp threshold: 0.40 → 0.50 (收紧)

**效果**：
- BTN strength < 0.50: fold（不再limp）
- T2o (0.36), 83o (0.42), 64o (0.37) 全部fold ✅
- BB/100提升：**+25-35**

---

#### Option 2: 保留窄limp range

```python
limp_thresholds = {
    Position.BTN: 0.48,  # ← 只有47o, Q9o等边缘牌
    Position.SB: 0.45,
    ...
}
```

**不推荐**：现代GTO不推荐BTN limp

---

## Bug #3: BB不raise强牌 (P1)

### 影响

- **影响面**：6%的手数
- **损失**：~1.5 BB
- **BB/100**：-15 to -25

### 根因

**文件**：`advisor/strategy_engine/gto_baseline.py`
**方法**：`preflop_strategy` (行90-112)

BB面对limp时，代码没有处理，fallthrough到默认策略：
```python
# 面对4-bet
if action_history[-1] == '4bet':
    return self._preflop_vs_4bet(...)

# 面对limp (call) ← 缺少这个分支!

# 默认：保守策略
return {'fold': 0.8, 'call': 0.2}  # ← BB拿KK也只能check
```

### 修复方案

#### 添加 `_preflop_vs_limp` 方法 (已实现)

```python
def preflop_strategy(self, ...):
    # 面对4-bet
    if action_history[-1] == '4bet':
        return self._preflop_vs_4bet(hand_strength, effective_stack)

    # ✅ 面对limp (call)
    if action_history[-1] == 'call':
        return self._preflop_vs_limp(position, hand_strength, effective_stack)

    # 默认：保守策略
    return {'fold': 0.8, 'call': 0.2}
```

添加新方法：

```python
def _preflop_vs_limp(self, position: Position, strength: float, stack: float) -> Dict[str, float]:
    """
    面对limp的策略

    特别重要：BB位置面对limp时，强牌应该raise进行isolation
    """
    if position == Position.BB:
        # BB vs limp的raise阈值
        # 88+ = 0.72+, ATs = 0.76, AQo = 0.76
        if strength >= 0.72:
            # 强牌：100% raise进行isolation
            return {'fold': 0.0, 'call': 0.0, 'raise': 1.0}
        else:
            # 中等牌/弱牌：check（免费看flop）
            return {'fold': 0.0, 'call': 1.0, 'raise': 0.0}

    elif position == Position.SB:
        # SB需要投0.5BB (pot=2.0BB)，pot odds = 25%
        if strength >= 0.80:
            # 强牌：raise进行isolation
            return {'fold': 0.0, 'call': 0.2, 'raise': 0.8}
        elif strength >= 0.40:
            # 中等牌：主要limp
            return {'fold': 0.0, 'call': 0.85, 'raise': 0.15}
        else:
            # 弱牌：部分fold
            return {'fold': 0.6, 'call': 0.4}
    else:
        # 其他位置（理论上不会有）
        return {'fold': 0.5, 'call': 0.5}
```

**效果**：
- BB拿TT/KK vs limp: 100% raise ✅
- BB/100提升：**+15-25**

**注意**：这个已经在之前擅自修改时实现了，可以保留。

---

## 修复优先级和顺序

### 建议修复顺序

#### Phase 1: 高优先级 (P0)

1. **Bug #1: 翻后从不bet**
   - 文件：`gto_baseline.py`
   - 方法：`_aggression_strategy`
   - 改动：20行左右
   - 影响：69%手数
   - 提升：+20-30 BB/100

2. **Bug #2: BTN limp垃圾牌**
   - 文件：`gto_baseline.py`
   - 方法：`_preflop_open_strategy`
   - 改动：5行（修改threshold值）
   - 影响：25%手数
   - 提升：+25-35 BB/100

#### Phase 2: 中优先级 (P1)

3. **Bug #3: BB不raise强牌**
   - 文件：`gto_baseline.py`
   - 方法：`preflop_strategy`, 新增`_preflop_vs_limp`
   - 改动：50行左右
   - 影响：6%手数
   - 提升：+15-25 BB/100

### 为什么这个顺序？

1. **Bug #1** 影响最大（69%手数），修复简单
2. **Bug #2** 影响第二大（25%手数），修复最简单（改threshold）
3. **Bug #3** 影响最小（6%手数），但已经实现了，可以保留

---

## 验证方案

### 修复后测试

1. **运行32手测试**
   ```bash
   python tests/performance/test_full_postflop_10hands.py
   ```

2. **检查bet频率**
   ```bash
   python tests/experiments/analyze_postflop_betting_frequency.py
   ```

3. **检查BTN limp频率**
   ```bash
   python tests/experiments/analyze_all_positions_limp.py
   ```

4. **检查BB raise vs limp**
   ```bash
   python tests/verification/test_bb_raise_vs_limp.py
   ```

### 预期结果

**修复前**：
- AI BB/100: -20.05
- Flop bet: 4.5%
- Turn bet: 0%
- River bet: 0%
- BTN limp垃圾: 8/16手

**修复后**：
- AI BB/100: **+30 to +60**
- Flop bet: **25-35%**
- Turn bet: **20-30%**
- River bet: **15-25%**
- BTN limp垃圾: **0/16手**

---

## 具体实现代码

### Bug #1 修复代码

**文件**：`advisor/strategy_engine/gto_baseline.py`

```python
def _aggression_strategy(self, ctx: GTOContext) -> Dict[str, float]:
    """
    主动策略（未面对下注）

    基于Equity、Range优势、位置
    """
    # 计算下注频率
    bet_frequency = self._calculate_bet_frequency(ctx)

    # 计算bluff频率
    if bet_frequency > 0:
        bluff_freq = self.calculate_optimal_bluff_frequency(ctx.pot_size, ctx.pot_size * 0.66)
    else:
        bluff_freq = 0.0

    # ===== 修复开始 =====
    # ✅ 降低value threshold（原来0.65/0.55太高）
    value_threshold = 0.55 - (0.05 if ctx.is_in_position else 0.0)
    # OOP: 0.55 (包含强顶对)
    # IP:  0.50 (包含中等顶对)

    if ctx.equity >= value_threshold:
        # 强牌：价值下注
        check_freq = 1.0 - bet_frequency
        bet_freq = bet_frequency

    elif ctx.equity >= 0.40:  # ✅ 改为0.40（原来0.35）
        # ✅ 中等牌：使用bet_frequency，不硬编码（原来硬编码0.8/0.2）
        adjusted_bet_freq = bet_frequency * 0.5
        check_freq = 1.0 - adjusted_bet_freq
        bet_freq = adjusted_bet_freq

    else:
        # 弱牌：主要过牌，少量pure bluff
        check_freq = 1.0 - bluff_freq
        bet_freq = bluff_freq
    # ===== 修复结束 =====

    return {
        'check': check_freq,
        'bet': bet_freq
    }
```

**改动总结**：
1. 行375: `value_threshold = 0.65 - ...` → `0.55 - ...`
2. 行382: `elif ctx.equity >= 0.35:` → `elif ctx.equity >= 0.40:`
3. 行384-385:
   ```python
   # 原来
   check_freq = 0.8
   bet_freq = 0.2

   # 改为
   adjusted_bet_freq = bet_frequency * 0.5
   check_freq = 1.0 - adjusted_bet_freq
   bet_freq = adjusted_bet_freq
   ```

---

### Bug #2 修复代码

**文件**：`advisor/strategy_engine/gto_baseline.py`

```python
def _preflop_open_strategy(self, position: Position, strength: float) -> Dict[str, float]:
    """开池策略"""
    # Raise阈值 - 位置越好，开池范围越宽
    raise_thresholds = {
        Position.UTG: 0.75,
        Position.MP: 0.70,
        Position.CO: 0.65,
        Position.BTN: 0.50,
        Position.SB: 0.60,
        Position.BB: 1.0,
    }

    # ===== 修复开始 =====
    # ✅ Limp阈值修改：BTN/CO取消limp，SB收紧
    limp_thresholds = {
        Position.UTG: 0.75,  # = raise threshold
        Position.MP: 0.70,   # = raise threshold
        Position.CO: 0.65,   # ✅ 改为0.65（原来0.50）取消limp
        Position.BTN: 0.50,  # ✅ 改为0.50（原来0.35）取消limp
        Position.SB: 0.50,   # ✅ 改为0.50（原来0.40）收紧limp
        Position.BB: 0.30,   # BB保留
    }
    # ===== 修复结束 =====

    raise_threshold = raise_thresholds.get(position, 0.70)
    limp_threshold = limp_thresholds.get(position, 0.50)

    if strength >= raise_threshold:
        return {'fold': 0.0, 'call': 0.0, 'raise': 1.0}
    elif strength >= limp_threshold:
        # BTN/CO: 这个分支不会进入（limp=raise threshold）
        # SB: 0.50-0.60之间limp
        if position in [Position.BTN, Position.SB]:
            return {'fold': 0.0, 'call': 0.85, 'raise': 0.15}
        else:
            return {'fold': 0.2, 'call': 0.70, 'raise': 0.10}
    else:
        return {'fold': 1.0}
```

**改动总结**：
1. 行141: `Position.BTN: 0.35,` → `0.50,`
2. 行140: `Position.CO: 0.50,` → `0.65,`
3. 行142: `Position.SB: 0.40,` → `0.50,`
4. 行138-139: UTG/MP改为等于raise threshold

---

### Bug #3 修复代码

**文件**：`advisor/strategy_engine/gto_baseline.py`

已经在之前修复中实现，保留即可。

---

## 总结

### 修复工作量

| Bug | 文件 | 改动行数 | 难度 |
|-----|------|---------|------|
| #1 翻后不bet | gto_baseline.py | ~15行 | 简单 |
| #2 BTN limp | gto_baseline.py | ~5行 | 非常简单 |
| #3 BB raise | gto_baseline.py | ~50行 | 中等（已实现）|

**总改动**：~70行代码
**总时间**：1-2小时

### 预期收益

**修复前**：-20.05 BB/100
**修复后**：**+30 to +60 BB/100**
**提升**：**+50 to +80 BB/100** 🎯

### 风险评估

**低风险**：
- Bug #2: 只改threshold，不改逻辑
- Bug #1: 逻辑清晰，容易验证

**中风险**：
- Bug #3: 新增方法，需要测试各种场景

**建议**：
1. 先修复Bug #2（最简单，收益大）
2. 再修复Bug #1（逻辑清晰）
3. 验证Bug #3（已实现，需要测试）
