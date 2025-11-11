# 🔴 严重Bug报告

## 发现日期: 2025-11-11

## Bug总结

Strategy Engine存在严重的决策逻辑错误，导致：
- QQ vs LAG 3-bet建议fold（应该call/4-bet）
- 无法达到预期盈利目标

---

## Bug 1: Hand Strength硬编码 ⭐⭐⭐⭐⭐

### 位置
`advisor/strategy_engine/advisor.py:358`

### 错误代码
```python
hand_strength = 0.7  # 简化
action_dist = self.gto_baseline.preflop_strategy(
    gto_ctx.position,
    hand_strength,  # ❌ 所有手牌都是0.7！
    game_state.action_history,
    game_state.effective_stack
)
```

### 影响
- **所有手牌**的strength都是0.7
- AA和72o使用相同的决策逻辑
- 完全忽略了实际手牌强度

### 修复方案
需要实现真实的hand strength计算：
```python
def calculate_hand_strength(hand: Hand, position: Position) -> float:
    """
    基于手牌计算strength (0.0-1.0)

    参考标准:
    - AA, KK: 0.95-1.0
    - QQ, JJ, AK: 0.85-0.95
    - TT, 99, AQ, AJs: 0.75-0.85
    - 88-22, suited connectors: 0.60-0.75
    - 弱牌: < 0.60
    """
    rank1 = hand.cards[0].rank
    rank2 = hand.cards[1].rank

    # 对子
    if rank1 == rank2:
        if rank1.value >= 13:  # AA, KK
            return 0.95
        elif rank1.value >= 11:  # QQ, JJ
            return 0.90
        elif rank1.value >= 9:  # TT, 99
            return 0.80
        else:  # 88-22
            return 0.65 + (rank1.value - 2) / 20

    # 高牌
    suited = (hand.cards[0].suit == hand.cards[1].suit)
    high = max(rank1.value, rank2.value)
    low = min(rank1.value, rank2.value)

    if high == 14:  # Ax
        if low >= 12:  # AK, AQ
            return 0.90 if suited else 0.85
        elif low >= 10:  # AJ, AT
            return 0.80 if suited else 0.70
        else:  # A9-A2
            return 0.65 if suited else 0.50

    # 其他牌...
    # (完整实现略)
```

---

## Bug 2: _preflop_vs_3bet阈值不合理 ⭐⭐⭐⭐⭐

### 位置
`advisor/strategy_engine/gto_baseline.py:145-164`

### 错误代码
```python
def _preflop_vs_3bet(self, position: Position, strength: float, stack: float):
    four_bet_threshold = 0.92  # ❌ 太高
    call_threshold = 0.75      # ❌ 太高

    if strength >= 0.75:
        return {'fold': 0.0, 'call': 0.9, '4bet': 0.1}
    elif strength >= 0.65:  # QQ (0.70) 会进这里
        return {'fold': 0.6, 'call': 0.4}  # ❌ fold 60%！
    else:
        return {'fold': 1.0}
```

### 影响
- QQ (strength ~0.90) 被当作0.70处理
- 进入"中等牌"逻辑：fold 60%
- 完全不合理

### 根本原因
1. threshold设置基于错误的strength值
2. 没有考虑对手类型（vs LAG应该更宽defend）
3. 没有使用实际equity

### 修复方案
```python
def _preflop_vs_3bet(self, position: Position, strength: float, stack: float,
                     equity: float = None, opponent_type: str = None):
    """
    面对3-bet的策略

    应该基于：
    1. Hand strength (真实值)
    2. Equity vs 对手3-bet范围
    3. 对手类型（LAG的3-bet范围宽 → 我们defend wider）
    4. SPR
    """
    # 对手类型调整
    if opponent_type == 'LAG':
        # vs LAG：他们3-bet范围宽，我们应该更宽defend
        four_bet_threshold = 0.88  # 降低
        call_threshold = 0.70      # 降低
    elif opponent_type == 'NIT':
        # vs Nit：他们3-bet范围紧，我们应该更紧defend
        four_bet_threshold = 0.95
        call_threshold = 0.85
    else:
        # 默认
        four_bet_threshold = 0.90
        call_threshold = 0.75

    # 如果有equity，优先使用equity
    if equity:
        # Equity > 50%几乎肯定应该至少call
        if equity >= 0.60:
            return {'fold': 0.0, 'call': 0.7, '4bet': 0.3}
        elif equity >= 0.50:
            return {'fold': 0.0, 'call': 0.9, '4bet': 0.1}
        elif equity >= 0.42:  # Pot odds typically ~42% vs 3-bet
            return {'fold': 0.2, 'call': 0.8}
        else:
            return {'fold': 0.8, 'call': 0.2}

    # 否则使用strength
    if strength >= four_bet_threshold:
        return {'fold': 0.0, 'call': 0.3, '4bet': 0.7}
    elif strength >= call_threshold:
        return {'fold': 0.0, 'call': 0.9, '4bet': 0.1}
    elif strength >= 0.60:  # 降低阈值
        return {'fold': 0.4, 'call': 0.6}  # 减少fold频率
    else:
        return {'fold': 1.0}
```

---

## Bug 3: Equity未被使用 ⭐⭐⭐⭐

### 位置
`advisor/strategy_engine/advisor.py:130-182`

### 问题
```python
# 步骤2: 计算equity
equity = self._calculate_equity(...)  # equity = 0.70

# 步骤6: GTO决策
gto_decision = self._get_gto_decision(game_state, gto_ctx)
# ❌ 但是gto_decision完全不用equity！只用硬编码的0.7 strength
```

### 影响
- 花费30秒计算equity
- 然后完全不用
- 决策基于错误的hardcoded strength

### 修复方案
在preflop_strategy中传入equity：
```python
action_dist = self.gto_baseline.preflop_strategy(
    gto_ctx.position,
    hand_strength,
    game_state.action_history,
    game_state.effective_stack,
    equity=gto_ctx.equity,  # ✅ 传入真实equity
    opponent_type=game_state.opponent_type.name if game_state.opponent_type else None
)
```

---

## Bug 4: Pot Odds计算错误 ⭐⭐⭐

### 位置
`advisor/strategy_engine/advisor.py:173`

### 错误代码
```python
'pot_odds': gto_ctx.pot_size / (gto_ctx.pot_size + gto_ctx.bet_to_call) if gto_ctx.bet_to_call else 0
```

### 问题
公式反了！应该是：
```python
'pot_odds': gto_ctx.bet_to_call / (gto_ctx.pot_size + gto_ctx.bet_to_call) if gto_ctx.bet_to_call else 0
```

### 影响
- 显示pot odds = 0.000（应该是42.9%）
- 但这只是显示问题，决策逻辑中没有用到

---

## Bug 5: GameState缺少关键字段 ⭐⭐⭐

### 位置
`advisor/strategy_engine/advisor.py:346-347`

### 问题
```python
facing_bet=game_state.facing_bet,
bet_to_call=game_state.bet_to_call,
```

但GameState定义中这两个字段是Optional，在3-bet场景下都是None！

### 影响
- 无法正确识别是否facing bet
- 无法计算pot odds
- 防守策略无法工作

### 修复方案
在GameState中正确设置这些字段：
```python
# QQ vs LAG 3-bet场景
game_state = GameState(
    ...
    pot_size=10.0,
    facing_bet=7.5,    # ✅ 需要设置
    bet_to_call=7.5,   # ✅ 需要设置
    action_history=['open', '3bet']
)
```

---

## 预期性能影响

修复这些bug后，预期：

### vs Random
- 当前: 未测试（AI太慢）
- 修复后: **+60 BB/100**（目标）

### vs SimpleHeuristic
- 当前: +16.6 BB/100（SimpleHeuristic vs Random）
- 修复后: **+15 BB/100**（目标）

### vs 不同类型
- vs Nit: **+25 BB/100**
- vs TAG: **+5 BB/100**
- vs Fish: **+45 BB/100**
- vs LAG: **+10 BB/100**
- vs Maniac: **+35 BB/100**

---

## 修复优先级

1. **立即修复** (P0):
   - Bug 1: 实现真实hand strength计算
   - Bug 2: 修复_preflop_vs_3bet阈值

2. **高优先级** (P1):
   - Bug 3: 在决策中使用equity
   - Bug 5: GameState字段设置

3. **中优先级** (P2):
   - Bug 4: Pot odds计算公式

---

## 测试计划

修复后需要重新测试：
1. QQ vs LAG 3-bet → 应该call/4-bet
2. AA vs TAG → 应该raise 100%
3. 72o vs Nit → 应该fold 100%
4. 场景测试全部重跑
5. 对局模拟（vs Random 1000手）

---

## 结论

当前Strategy Engine有**严重的逻辑错误**，导致：
- ❌ 所有手牌使用相同strength (0.7)
- ❌ QQ被错误地建议fold
- ❌ Equity计算结果未被使用
- ❌ 无法达到预期盈利目标

**必须立即修复这些bug才能继续性能优化。**

---

**报告人**: Claude
**严重性**: 🔴 Critical
**状态**: 待修复
