# AI决策系统重构方案

## 当前问题总结

### 1. Range系统被架空 ❌

```python
# 精心定义的Range完全不用于决策
BTN_OPEN_RANGES = {
    'loose': {'offsuit': ['A2o+', 'K7o+', ...]}  # 被忽略
}

# 决策只看strength
if strength >= threshold:  # 完全不检查hand是否在range内
    return {'raise': 1.0}
```

### 2. Strength系统过于简化 ❌

- 不考虑位置（K7o在BTN vs UTG价值不同）
- 不考虑对手范围（vs Random vs vs NIT）
- 不考虑动态因素（SPR、pot odds、对手类型）

### 3. 两套系统矛盾 ❌

- Range说：K8o在BTN normal范围内
- Strength说：K8o (0.49) < threshold (0.50) → fold/limp

---

## 重构方案对比

### 方案1：基于Range的决策系统（推荐 ✅）

#### 优点
- ✅ 使用精心定义的GTO范围
- ✅ 专业、精确、易于维护
- ✅ 可以根据对手类型调整tightness
- ✅ 与已有的range定义完全一致
- ✅ 易于理解和调试

#### 缺点
- ⚠️ 需要重构接口（传入Hand而不是strength）
- ⚠️ 需要定义limp range
- ⚠️ 静态范围，不能根据特定对手动态调整

#### 实现复杂度
**中等** - 需要修改接口，但逻辑简单

#### 代码示例

```python
def _preflop_open_strategy(self, position: Position, hand: Hand,
                          tightness: str = 'normal') -> Dict[str, float]:
    """
    基于预定义Range的开池策略

    Args:
        position: 位置
        hand: 手牌（Hand对象）
        tightness: 打法风格 ('tight', 'normal', 'loose')
    """
    from advisor.range_engine.preflop_ranges import get_open_range, parse_range_dict

    # 1. 获取open range
    range_dict = get_open_range(position.value, tightness)
    open_range = parse_range_dict(range_dict)

    # 2. 获取limp range（稍宽于open range）
    limp_tightness = 'loose' if tightness == 'normal' else 'normal'
    limp_dict = get_open_range(position.value, limp_tightness)
    limp_range = parse_range_dict(limp_dict)

    # 3. 检查手牌是否在范围内
    if hand in open_range:
        # 强牌：主要raise，少量limp作为trap
        return {'fold': 0.0, 'call': 0.1, 'raise': 0.9}
    elif hand in limp_range:
        # 中等牌：主要limp，少量raise作为bluff
        if position in [Position.BTN, Position.SB]:
            return {'fold': 0.0, 'call': 0.85, 'raise': 0.15}
        else:
            # EP/MP limp风险高
            return {'fold': 0.2, 'call': 0.70, 'raise': 0.10}
    else:
        # 弱牌：fold
        return {'fold': 1.0}


def _get_hero_tightness(self, game_state: GameState) -> str:
    """
    根据游戏情况动态选择tightness

    Returns:
        'tight', 'normal', 'loose'
    """
    # 1. 根据对手类型
    if game_state.opponent_type:
        if game_state.opponent_type in [PlayerType.FISH, PlayerType.CALLING_STATION]:
            return 'loose'  # vs弱手打宽
        elif game_state.opponent_type in [PlayerType.LAG, PlayerType.MANIAC]:
            return 'tight'  # vs激进玩家打紧
        elif game_state.opponent_type in [PlayerType.NIT]:
            return 'loose'  # vs NIT可以偷盲

    # 2. 根据SPR
    if game_state.spr < 10:
        return 'loose'  # 浅筹码可以all-in更宽
    elif game_state.spr > 50:
        return 'tight'  # 深筹码需要更好的postflop能力

    # 3. 默认
    return 'normal'
```

#### 调用处修改

```python
# advisor/strategy_engine/advisor.py:355-378
def _get_gto_decision(self, game_state, gto_ctx):
    if game_state.street == 'preflop':
        # 获取tightness
        tightness = self._get_hero_tightness(game_state)

        # 调用preflop_strategy
        action_dist = self.gto_baseline.preflop_strategy(
            gto_ctx.position,
            game_state.hero_hand,  # ← 传入Hand而不是strength
            game_state.action_history,
            game_state.effective_stack,
            tightness=tightness,  # ← 传入动态tightness
            equity=gto_ctx.equity,
            opponent_type=game_state.opponent_type.name if game_state.opponent_type else None
        )
```

---

### 方案2：基于Equity的决策系统

#### 优点
- ✅ 最准确（动态计算vs对手范围）
- ✅ 自动考虑对手范围
- ✅ 可以处理复杂场景

#### 缺点
- ⚠️ Equity已经在计算了，但在开池决策中不用
- ⚠️ 需要定义equity阈值
- ⚠️ 可能过度依赖equity（忽略其他因素）

#### 实现复杂度
**简单** - Equity已经计算好了，只需使用

#### 代码示例

```python
def _preflop_open_strategy(self, position: Position, equity: float,
                          strength: float = None) -> Dict[str, float]:
    """
    基于Equity的开池策略

    Args:
        position: 位置
        equity: vs对手范围的equity (0.0-1.0)
        strength: 手牌强度（可选，用于backup）
    """
    # Equity阈值（根据位置调整）
    raise_equity_thresholds = {
        Position.UTG: 0.58,  # vs tight range需要更强
        Position.MP: 0.55,
        Position.CO: 0.52,
        Position.BTN: 0.48,  # vs loose range要求低
        Position.SB: 0.50,
    }

    # Limp阈值（基于pot odds + margin）
    # BTN: pot odds = 25%，所以limp阈值约35%
    limp_equity_thresholds = {
        Position.UTG: 0.48,
        Position.MP: 0.45,
        Position.CO: 0.42,
        Position.BTN: 0.35,  # 只需35% equity就profitable
        Position.SB: 0.38,
    }

    raise_threshold = raise_equity_thresholds.get(position, 0.52)
    limp_threshold = limp_equity_thresholds.get(position, 0.42)

    if equity >= raise_threshold:
        # 强牌：raise
        return {'fold': 0.0, 'call': 0.0, 'raise': 1.0}
    elif equity >= limp_threshold:
        # 中等牌：limp
        if position in [Position.BTN, Position.SB]:
            return {'fold': 0.0, 'call': 0.85, 'raise': 0.15}
        else:
            return {'fold': 0.2, 'call': 0.70, 'raise': 0.10}
    else:
        # 弱牌：fold
        return {'fold': 1.0}
```

#### 优势案例

```python
# K7o在不同场景下的equity：
# vs Random (100%): ~50% equity → 应该raise
# vs UTG tight (~15%): ~35% equity → 应该fold/limp
# vs BTN loose (~50%): ~42% equity → 应该limp

# 基于Equity的系统会自动适应！
```

---

### 方案3：混合方法（平衡）

#### 优点
- ✅ 保留现有strength系统
- ✅ 只需微调参数
- ✅ 改动最小

#### 缺点
- ⚠️ 仍然不解决根本问题
- ⚠️ Strength和Range仍然矛盾
- ⚠️ 不够专业

#### 实现复杂度
**简单** - 只需调整阈值和strength值

#### 代码示例

```python
# 方案3a: 调整阈值
position_thresholds = {
    Position.BTN: 0.45,  # 0.50 → 0.45（让K7o, K8o能pass）
}

# 方案3b: 微调K7o/K8o的strength
def _king_high_strength(low_rank: Rank, suited: bool) -> float:
    if low_rank.value >= 8:  # K8
        return 0.62 if suited else 0.51  # 0.49 → 0.51（让K8o能raise）
    elif low_rank.value >= 7:  # K7
        return 0.60 if suited else 0.48  # 0.46 → 0.48（让K7o能limp）
```

#### 问题
- K8o应该raise（在BTN normal range内）
- 但调整后K8o (0.51) > 0.45会raise ✅
- 但K9o (0.53)也会raise，Q8o (0.47)也会raise
- **范围变得难以控制**

---

## 推荐方案：方案1（基于Range）

### 为什么选择方案1？

1. ✅ **最专业**：使用预定义的GTO范围
2. ✅ **最一致**：与已有的range定义完全匹配
3. ✅ **最灵活**：可以根据对手类型动态调整tightness
4. ✅ **最易维护**：修改范围只需改preflop_ranges.py
5. ✅ **最易理解**：逻辑清晰（检查hand是否在range内）

### 为什么不选方案2（Equity）？

虽然更准确，但：
- ⚠️ Equity已经在计算了，但开池时对手范围估计不够准确
- ⚠️ 可能过度依赖equity（如A2o vs random equity高，但postflop难打）
- ⚠️ 不如直接使用经过验证的GTO范围

### 为什么不选方案3（混合）？

- ❌ 不解决根本问题
- ❌ Strength和Range仍然矛盾
- ❌ 阈值难以精确调整

---

## 实施计划

### 阶段1：重构接口（1-2小时）

**修改文件**：
1. `advisor/strategy_engine/gto_baseline.py`
   - 修改`preflop_strategy`接受`hand`和`tightness`参数
   - 修改`_preflop_open_strategy`使用range检查

2. `advisor/strategy_engine/advisor.py`
   - 添加`_get_hero_tightness`方法
   - 修改`_get_gto_decision`传入hand和tightness

**向后兼容**：
- 保留strength参数作为fallback
- 如果range检查失败，回退到strength系统

### 阶段2：定义Limp Range（30分钟）

**修改文件**：
1. `advisor/range_engine/preflop_ranges.py`
   - 添加`get_limp_range(position, tightness)`函数
   - 或者使用更宽的tightness作为limp range

**策略**：
```python
# Limp range = 比open range宽一档
if tightness == 'tight':
    limp_range = get_open_range(position, 'normal')
elif tightness == 'normal':
    limp_range = get_open_range(position, 'loose')
else:  # loose
    limp_range = get_open_range(position, 'loose')  # 已经最宽
```

### 阶段3：测试验证（30分钟）

1. 单元测试：K7o, K8o, K9o等边缘牌
2. 10手集成测试
3. 50手性能测试
4. 对比修复前后的结果

### 阶段4：优化调整（1小时）

根据测试结果：
- 调整limp range定义
- 调整tightness选择逻辑
- 微调mixed strategy比例

---

## 预期改进

### 翻前决策

| 案例 | 当前（Strength） | 重构后（Range） |
|------|-----------------|----------------|
| K8o BTN | limp (strength 0.49) | **raise** ✅ (在normal range) |
| K7o BTN | limp (strength 0.46) | **limp** ✅ (在loose range) |
| Q9o BTN | raise (strength 0.52) | **raise** ✅ (在normal range) |
| 72o BTN | fold (strength 0.38) | **fold** ✅ (不在任何range) |

### 一致性

- ✅ **Range和决策完全一致**
- ✅ **可以根据对手类型调整**（vs FISH用loose，vs LAG用tight）
- ✅ **易于理解和调试**（打印hand是否在range内）

### 性能

- 预期BB/100提升：+10 to +30（通过更准确的范围）
- 减少边缘牌的错误决策
- 更好的对手适应能力

---

## 风险和缓解

### 风险1：接口改动较大

**缓解**：
- 分阶段重构，先重构_preflop_open_strategy
- 保留strength参数作为fallback
- 充分测试向后兼容性

### 风险2：Limp range定义不准确

**缓解**：
- 初期使用保守的定义（limp range = loose open range）
- 通过测试逐步调整
- 参考GTO solver结果

### 风险3：性能可能下降

**缓解**：
- 在重构前先运行50-100手baseline测试
- 重构后运行相同测试对比
- 如果性能下降，回退并分析原因

---

## 替代方案：如果不重构

如果暂时不想重构，可以做以下优化：

### 短期优化（保留Strength系统）

1. ✅ **调整BTN阈值**：0.50 → 0.47
   - 让K8o (0.49) > 0.47 能raise
   - 让K7o (0.46) < 0.47继续limp

2. ✅ **微调边缘牌strength**：
   - K8o: 0.49 → 0.51
   - Q9o: 0.52（保持不变）
   - J9o: 0.51 → 0.52

3. ✅ **添加position modifier**：
   ```python
   adjusted_strength = strength * position_multiplier[position]
   # BTN: 1.05 (让牌看起来更强)
   # UTG: 0.95 (让牌看起来更弱)
   ```

**效果**：
- ⚠️ 临时解决，但Strength和Range仍然矛盾
- ⚠️ 阈值难以精确调整
- ⚠️ 不如重构来得彻底

---

## 总结

| 方案 | 准确性 | 一致性 | 灵活性 | 复杂度 | 推荐度 |
|------|--------|--------|--------|--------|--------|
| **方案1: Range** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | **✅ 强烈推荐** |
| 方案2: Equity | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⚠️ 备选 |
| 方案3: 混合 | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ❌ 不推荐 |

**最终推荐**：方案1（基于Range的决策系统）

**理由**：
- 最专业、最一致、最易维护
- 与已有的GTO范围定义完全匹配
- 实施复杂度适中（1-2天完成）
- 长期收益最大

**下一步**：
1. 确认是否采用方案1
2. 开始实施阶段1（重构接口）
3. 逐步测试和优化
