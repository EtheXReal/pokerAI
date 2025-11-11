# K7o Fold问题分析

## 问题描述

在Hand #3中，AI在BTN位置拿着K7o选择fold，这在德州扑克中是不合理的决策。BTN是最佳位置，K7o应该是标准的open raise手牌。

## 问题手牌

```
Hand #3 - AI Position: BTN
AI: 7cKh (K7o)
Random: 9h6c
Pot: 1.5BB
AI folds  ← 问题决策
```

## 根本原因

AI使用了**两套独立的系统**来处理翻前决策，它们之间存在矛盾：

### 系统1: Preflop Ranges（未被使用）

定义在 `advisor/range_engine/preflop_ranges.py:95-114`

```python
BTN_OPEN_RANGES = {
    'tight': {
        'offsuit': ['A8o+', 'K9o+', 'QTo+', 'JTo'],
        # K7o不在范围内
    },
    'normal': {
        'offsuit': ['A5o+', 'K8o+', 'Q9o+', 'J9o+', 'T8o+', '98o'],
        # K7o不在范围内（需要K8o+）
    },
    'loose': {
        'offsuit': ['A2o+', 'K7o+', 'Q8o+', 'J8o+', 'T8o+', '98o'],
        # K7o在范围内 ✅
    }
}
```

**用途**：这个范围只在 `advisor.py:232` 用于推测hero自己的范围和villain的范围，**不用于实际决策**。

### 系统2: Hand Strength + Threshold（实际决策使用）

#### 步骤1: 计算K7o的strength

定义在 `advisor/strategy_engine/hand_strength.py:126-141`

```python
def _king_high_strength(low_rank: Rank, suited: bool) -> float:
    """King高张强度"""
    if low_rank.value >= 7:  # K7
        return 0.60 if suited else 0.46  # ← K7o = 0.46
```

**K7o strength = 0.46**

#### 步骤2: 与BTN threshold比较

定义在 `advisor/strategy_engine/gto_baseline.py:110-127`

```python
def _preflop_open_strategy(self, position: Position, strength: float) -> Dict[str, float]:
    """开池策略"""
    position_thresholds = {
        Position.UTG: 0.75,  # 只开最好的25%
        Position.MP: 0.70,
        Position.CO: 0.65,
        Position.BTN: 0.50,  # BTN可以开50%  ← 阈值
        Position.SB: 0.60,
        Position.BB: 1.0,
    }

    threshold = position_thresholds.get(position, 0.70)

    if strength >= threshold:  # 0.46 >= 0.50 ？
        return {'fold': 0.0, 'raise': 1.0}
    else:
        return {'fold': 1.0}  # ← AI选择fold
```

**决策链条**：
```
K7o strength (0.46) < BTN threshold (0.50)
→ return {'fold': 1.0}
→ AI folds
```

## 问题分析

### 1. 两套系统不一致

- **Preflop Ranges**: 精心设计的GTO范围，K7o在loose模式下可以open
- **Hand Strength**: 简化的strength评分系统，K7o = 0.46刚好低于BTN阈值0.50

### 2. AI没有使用Preflop Ranges做决策

查看 `advisor/strategy_engine/advisor.py` 的决策流程：

```python
# 步骤1: 推断范围（advisor.py:129）
hero_range, villain_range = self._estimate_ranges(game_state)
# ↑ 这里使用了preflop_ranges，但只用于equity计算

# 步骤6: GTO基线决策（advisor.py:157）
gto_decision = self._get_gto_decision(game_state, gto_ctx)
# ↓ 调用 gto_baseline.preflop_strategy

# gto_baseline.py:91
return self._preflop_open_strategy(position, hand_strength)
# ↑ 只使用hand_strength做决策，完全不考虑preflop_ranges
```

### 3. Strength阈值过于粗糙

BTN threshold = 0.50 意味着：
- **可以open**: K8o (0.49)刚好不行，K9o (0.53) ✅
- **不能open**: K7o (0.46) ✗
- **可以open**: A7o (0.50) ✅

这与标准的BTN GTO范围（应该包含K7o在loose模式下）不一致。

## 解决方案

有两种方法修复这个问题：

### 方案1: 调整BTN的strength threshold

```python
# gto_baseline.py:117
Position.BTN: 0.45,  # 从0.50降低到0.45
```

**优点**：
- 简单直接
- K7o (0.46) > 0.45 ✅

**缺点**：
- 可能会让更弱的牌（如Q7o=0.47）也open
- 不够精确

### 方案2: 使用Preflop Ranges做决策（推荐）

修改 `gto_baseline.py:_preflop_open_strategy` 直接检查手牌是否在范围内：

```python
def _preflop_open_strategy(self, position: Position, hand: Hand, tightness='normal') -> Dict[str, float]:
    """开池策略 - 基于预定义范围"""
    from advisor.range_engine.preflop_ranges import get_open_range, parse_range_dict

    # 获取该位置的open range
    range_dict = get_open_range(position.value, tightness)
    open_range = parse_range_dict(range_dict)

    # 检查手牌是否在范围内
    if hand in open_range:
        return {'fold': 0.0, 'raise': 1.0}
    else:
        return {'fold': 1.0}
```

**优点**：
- 使用精心设计的GTO范围
- 可以通过调整tightness（tight/normal/loose）来控制打法风格
- 更专业、更精确

**缺点**：
- 需要修改接口（传入Hand对象而不是strength）
- 需要在调用处传递tightness参数

### 方案3: 混合方法

保留strength系统，但降低BTN阈值并微调K7o的strength：

```python
# hand_strength.py:139
elif low_rank.value >= 7:  # K7
    return 0.62 if suited else 0.48  # K7o: 0.46 → 0.48

# gto_baseline.py:117
Position.BTN: 0.47,  # 0.50 → 0.47
```

这样K7o (0.48) > 0.47 ✅，但不会让太弱的牌进入范围。

## 推荐修复

**优先方案2**（使用Preflop Ranges），因为：
1. ✅ 符合GTO范围理论
2. ✅ 可配置（tight/normal/loose）
3. ✅ 与codebase中已定义的范围一致
4. ✅ 更容易维护和调整

**次选方案3**（调整阈值），如果不想大改代码结构。

## 相关文件

- `advisor/range_engine/preflop_ranges.py` - 定义GTO范围
- `advisor/strategy_engine/hand_strength.py:126-141` - K7o strength计算
- `advisor/strategy_engine/gto_baseline.py:110-127` - 开池决策逻辑
- `advisor/strategy_engine/advisor.py:232` - 范围推断（未用于决策）
