# 已知问题 (Known Issues)

## ✅ 所有已知问题已修复！

目前没有已知的游戏逻辑Bug。

---

## 📋 已修复的问题

### 1. ✅ 跳过玩家行动 - Postflop街道 (已修复)

**问题**: Flop/Turn/River上，在第二个玩家行动前就错误地结束了betting round，导致除了第一个玩家外，其他玩家都没有行动机会。

**用户发现的场景**:
```
=== Flop: Ks 5d 7h ===
Pot: 6.0BB
Random_1 checks         ← 只有Random_1行动！

=== Showdown ===        ← AI和Random_2都没行动就到showdown了！
AI: STRAIGHT
Random_1: HIGH_CARD
Random_2: TWO_PAIR
```

**根本原因**: betting_round.py 第124-131行的提前结束检查在玩家行动**之前**执行，条件`num_actions > 1`太宽松。

**修复**: commit d5e126e - 删除了错误的提前结束检查

**影响**: 这个bug也导致了零和游戏-0.5BB误差！

---

### 2. ✅ 零和游戏误差 (-0.5BB) (已修复)

**问题**:
```
Total profit sum: -0.50BB (should be ~0)  ← 错误
```

**根本原因**: 与问题1相同 - betting round提前结束导致部分投入没有被正确计算。

**修复**: commit d5e126e - 修复betting round逻辑后，零和游戏恢复正常

**验证**:
```
Total profit sum: 0.00BB (should be ~0)  ✅
```

---

### 3. ✅ All-in后跳过玩家行动 (已修复)

**问题**: 当玩家all-in后，其他玩家没有被要求行动就直接进入下一条街。

**修复**: commit c8f2631

**详情**: 见 `poker_env/betting_round.py` 的修复注释

---

### 4. ✅ 边池显示混乱 (已修复)

**问题**: 简单场景也显示复杂的边池计算信息。

**修复**: commit d0b5ed5 - 只在真正有多个边池时才显示详细信息

---

### 5. ✅ Verbose输出缺少Hand编号 (已修复)

**问题**: Verbose模式下看不到是第几手牌。

**修复**: commit c8f2631 - 添加手牌编号和BTN信息
