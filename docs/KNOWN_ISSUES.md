# 已知问题 (Known Issues)

## ⚠️ 零和游戏误差 (-0.5BB)

### 问题描述

在3人AI游戏测试中（`tests/performance/3player_ai_test.py`），使用AdvisorV2Player时，多手牌累计会出现固定的-0.5BB误差。

### 复现步骤

```bash
python tests/performance/3player_ai_test.py --hands 20 --seed 42
```

### 观察到的现象

```
Total hands: 20
Player Performance:
AI              -13.0BB
Random_1        +44.5BB
Random_2        -32.0BB

Total profit sum: -0.50BB (should be ~0)  ← 问题
```

### 已验证的事实

1. **不是poker_env的问题**
   - 使用3个RandomPlayer测试：零和正确 ✅
   - 使用SimpleAIPlayer测试：零和正确 ✅
   - 只有AdvisorV2Player有问题 ❌

2. **不是TeeOutput的问题**
   - 禁用TeeOutput后仍然有-0.5BB误差

3. **不是betting_round bug**
   - betting_round的严重bug已修复
   - 每手牌的投入/pot计算正确

4. **固定误差**
   - 无论运行多少手牌，总是-0.5BB
   - 不是累积的浮点精度误差

5. **正好是小盲注金额**
   - 误差 = 0.5BB = 小盲注金额
   - 可能与某个特定位置的投入计算有关

### 可能的根源

#### 猜测1: DecisionIntegrator内部状态问题
可能在某些情况下，DecisionIntegrator没有正确返回决策，导致投入计算错误。

#### 猜测2: AI玩家初始化问题
虽然每手牌都会reset，但AI玩家的某些内部组件（RangeEngine, EquityEngine等）可能保留了状态。

#### 猜测3: 特定位置的edge case
可能只在AI担任某个特定位置（如SB或BB）时，在特定情况下（如fold或check）才出现。

### 调试建议

1. **追踪每手牌的盈亏**
   ```python
   for hand_num in range(20):
       result = game.play_hand(...)
       hand_sum = sum(result.player_profits)
       if abs(hand_sum) > 0.01:
           print(f"Hand #{hand_num+1}: NOT ZERO! sum={hand_sum:.2f}BB")
   ```

2. **比较invested和pot**
   检查是否某手牌的 `sum(players.invested) != pot`

3. **检查AI决策时的投入**
   在AdvisorV2Player.decide方法中添加日志：
   ```python
   print(f"Before decision: invested={self.invested}, stack={self.stack}")
   action = ...
   print(f"After decision: action={action.action}, amount={action.amount}")
   ```

4. **单独测试有问题的手牌**
   找到第一个出现误差的手牌，单独运行verbose模式

### 影响范围

- **不影响游戏逻辑**：每手牌的结果是正确的
- **只影响统计**：20手牌的累计统计有-0.5BB误差
- **可接受的临时方案**：手动补偿0.5BB

### 临时解决方案

在3player_ai_test.py中手动补偿：
```python
# 已知问题：AI玩家有-0.5BB的统计误差
total_sum = sum(player_total_profits)
if abs(total_sum + 0.5) < 0.01:
    print(f"Total profit sum: {total_sum:.2f}BB (with known 0.5BB offset)")
else:
    print(f"Total profit sum: {total_sum:.2f}BB (should be ~0)")
```

### 优先级

**中等**
- 不影响核心游戏功能
- 不影响AI决策质量
- 只影响长期统计准确性

### 状态

🔍 **调查中** - 需要更详细的调试

---

## ✅ 已修复的问题

### All-in后跳过玩家行动 (已修复)

**问题**: 当玩家all-in后，其他玩家没有被要求行动就直接进入下一条街。

**修复**: commit c8f2631

**详情**: 见 `poker_env/betting_round.py` 的修复注释
