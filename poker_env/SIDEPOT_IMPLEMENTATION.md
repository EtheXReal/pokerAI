# Side Pot Implementation

## 概述

完整的德州扑克边池（Side Pot）支持已实现并通过测试。边池是德州扑克中处理多人all-in时的核心机制，确保每个玩家只能赢得他们有资格竞争的pot部分。

## 实现文件

### [poker_env/side_pot.py](side_pot.py)

包含两个核心组件：

#### 1. `SidePot` 数据类

```python
@dataclass
class SidePot:
    amount: float              # 边池金额
    eligible_seats: List[int]  # 有资格赢得此边池的玩家座位列表
    cap_per_player: float      # 每个玩家在此边池的投入上限
```

#### 2. `SidePotManager` 静态类

提供三个核心方法：

##### `calculate_side_pots()`

根据玩家投入计算边池结构。

**算法**：
1. 收集所有有投入的玩家（包括fold的玩家，他们的筹码留在pot中）
2. 按投入金额从少到多排序
3. 从最小投入开始，逐级创建边池
4. 每个边池包含投入≥该级别的所有玩家的筹码
5. 但只有still active的玩家才eligible赢得边池

**示例**：
```
3人游戏：
- Player A: 投入 30BB
- Player B: 投入 50BB (fold了)
- Player C: 投入 100BB

结果：
- Main Pot: 90BB (30×3), eligible=[A, C]  # B fold了不能赢
- Side Pot 1: 40BB (20×2), eligible=[C]   # 只有C投入≥50BB且active
- Side Pot 2: 50BB (50×1), eligible=[C]   # 只有C投入≥100BB
```

##### `distribute_pots()`

根据边池和牌力分配奖金。

**逻辑**：
1. 遍历每个边池（从main pot到side pots）
2. 在eligible玩家中找到最强的牌
3. 平分该边池给所有拥有最强牌的玩家（处理平局）

**示例**：
```
边池：
- Main Pot: 90BB, eligible=[A, C]
- Side Pot 1: 110BB, eligible=[C]

牌力：
- A: TWO_PAIR
- C: ONE_PAIR

结果：
- A wins Main Pot: 90BB
- A无法赢Side Pot 1（not eligible）
- C wins Side Pot 1: 110BB
```

##### `validate_side_pots()`

验证边池计算的正确性。

**检查**：
1. 所有边池金额之和 = 所有玩家投入之和
2. 每个边池的eligible玩家都是active的（未fold）

## 集成到游戏引擎

### [poker_env/poker_game.py](poker_game.py)

修改了 `_showdown()` 方法使用边池分配：

```python
def _showdown(self, ...):
    # 1. 评估所有active玩家的牌力
    hand_strengths_list = []
    for player in active_players:
        strength = HandEvaluator.evaluate_best_5(all_cards)
        hand_strengths_list.append((player.seat, strength))

    # 2. 计算边池
    side_pots = SidePotManager.calculate_side_pots(
        self.players, verbose=self.config.verbose
    )

    # 3. 验证边池（可选）
    SidePotManager.validate_side_pots(side_pots, self.players)

    # 4. 根据边池分配奖金
    player_winnings = SidePotManager.distribute_pots(
        side_pots, self.players, hand_strengths_list,
        verbose=self.config.verbose
    )

    # 5. 计算盈亏并返回结果
    ...
```

## 测试

### 单元测试 - [poker_env/side_pot.py](side_pot.py)

文件底部包含4个单元测试：

1. **Test 1**: 3人不同投入
   - 验证边池数量和金额正确
   - 验证eligible玩家列表正确

2. **Test 2**: 2人one all-in
   - 验证只有main pot
   - 验证金额计算正确

3. **Test 3**: 4人连锁all-in
   - 验证多级边池计算
   - 验证复杂场景的正确性

4. **Test 4**: 3人有fold
   - 验证fold玩家的筹码留在pot中
   - 验证fold玩家不在eligible列表中

**运行单元测试**：
```bash
python poker_env/side_pot.py
```

**结果**: ✓ 所有测试通过

### 集成测试 - [tests/performance/multiplayer_sidepot_test.py](../../tests/performance/multiplayer_sidepot_test.py)

完整的多人游戏场景测试：

1. **Test 1**: 3人简单边池
   - 所有人all-in
   - 验证showdown和边池分配

2. **Test 2**: 4人连锁all-in
   - 不同stack大小
   - 验证多级边池

3. **Test 3**: 3人有fold
   - 验证fold玩家的筹码处理
   - 验证边池分配正确性

4. **Test 4**: 3人相等投入
   - 验证相同投入时的边池计算
   - 验证零和游戏特性

**运行集成测试**：
```bash
python tests/performance/multiplayer_sidepot_test.py
```

**结果**: ✓ 所有测试通过

## 关键设计决策

### 1. 为什么包含fold玩家的投入？

根据德州扑克规则，fold的玩家已经投入的筹码留在pot中，但他们无法赢得任何pot。

**实现**：
- `calculate_side_pots()` 包含所有有投入的玩家（fold或active）
- 但只有active玩家才在`eligible_seats`列表中

### 2. 如何处理平局（split pot）？

当多个玩家拥有相同强度的最强牌时，平分该边池。

**实现**：
```python
max_strength = max(strength for _, strength in eligible_strengths)
winners = [seat for seat, strength in eligible_strengths
           if strength == max_strength]
share = side_pot.amount / len(winners)
```

### 3. 边池顺序重要吗？

是的！必须从main pot到side pots依次分配，因为：
- Main pot: 所有人都可能赢
- Side Pot 1: 只有投入更多的人可能赢
- Side Pot 2: 只有投入最多的人可能赢

### 4. 如何处理all-in但不足最小加注的情况？

这种情况在betting_round.py中处理，不影响边池计算。边池只关心最终投入金额。

## 数学验证

### 不变量（Invariants）

1. **总额守恒**：
   ```
   sum(side_pot.amount for side_pot in side_pots) ==
   sum(player.invested for player in players)
   ```

2. **零和游戏**：
   ```
   sum(player_profits) == 0
   ```

3. **盈亏计算**：
   ```
   player_profit = player_winnings - player_invested
   ```

### 示例计算

**场景**: 3人游戏
- A: 30BB all-in
- B: 50BB fold
- C: 100BB call

**步骤1**: 排序投入
```
[(A, 30BB), (B, 50BB), (C, 100BB)]
```

**步骤2**: 计算边池
```
Main Pot:
  level_amount = 30BB
  contributors = 3 (A, B, C)
  pot_amount = 30 × 3 = 90BB
  eligible = [A, C]  # B fold了

Side Pot 1:
  level_amount = 50 - 30 = 20BB
  contributors = 2 (B, C)
  pot_amount = 20 × 2 = 40BB
  eligible = [C]  # 只有C active且投入≥50BB

Side Pot 2:
  level_amount = 100 - 50 = 50BB
  contributors = 1 (C)
  pot_amount = 50 × 1 = 50BB
  eligible = [C]
```

**步骤3**: 验证
```
Total = 90 + 40 + 50 = 180BB
Invested = 30 + 50 + 100 = 180BB ✓
```

**步骤4**: 分配（假设A最强牌）
```
A wins Main Pot: 90BB
C wins Side Pot 1: 40BB
C wins Side Pot 2: 50BB

Profits:
A: 90 - 30 = +60BB
B: 0 - 50 = -50BB
C: 90 - 100 = -10BB
Total: 60 - 50 - 10 = 0BB ✓
```

## 性能考虑

### 时间复杂度

- `calculate_side_pots()`: O(n²) 其中n是玩家数量
  - 排序: O(n log n)
  - 遍历玩家: O(n)
  - 每次迭代检查eligible: O(n)

- `distribute_pots()`: O(m × n) 其中m是边池数量，n是玩家数量
  - 通常m ≤ n，所以实际是O(n²)

### 空间复杂度

- O(n) 用于存储边池列表

### 优化空间

当前实现已经足够高效，因为：
1. 扑克游戏通常≤10人
2. 边池计算只在showdown时发生（不频繁）
3. 代码清晰易维护比微优化更重要

## 已知限制

无。当前实现支持：
- ✅ 2-10人游戏
- ✅ 多级边池（无限制）
- ✅ Fold玩家的筹码处理
- ✅ Split pot（平局）
- ✅ All-in但不足最小加注
- ✅ 零和游戏验证

## 未来可能的扩展

1. **Ante支持**：如果添加ante，需要在blind投入前处理
2. **Dead money**：某些变体中可能有dead blinds
3. **Straddle**：可选的第三盲注，影响行动顺序和边池
4. **更详细的日志**：添加更多调试信息

## 总结

边池实现是完整的、经过测试的，并且符合德州扑克的标准规则。代码清晰、文档完善、测试覆盖全面。

可以安全地用于：
- 多人扑克AI训练
- 扑克模拟和分析
- 在线扑克游戏开发
- 教学和研究

**实现完成日期**: 2025-01-13
**测试状态**: ✓ 全部通过
**代码质量**: 生产就绪
