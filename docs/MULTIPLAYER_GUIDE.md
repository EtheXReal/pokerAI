# 多人游戏使用指南

poker_env 已经完全支持 **2-10人** 德州扑克游戏！

## 🎯 快速开始

### 最简单的3人游戏

```python
from poker_env import PokerGame, GameConfig, Player, PlayerAction, GameState

# 1. 创建3个玩家（需要实现decide方法）
class YourPlayer(Player):
    def decide(self, game_state: GameState) -> PlayerAction:
        # 你的决策逻辑
        if game_state.to_call > 0:
            return PlayerAction('call', 0.0)
        else:
            return PlayerAction('check', 0.0)

players = [
    YourPlayer("Alice", 0, 100.0),
    YourPlayer("Bob", 1, 100.0),
    YourPlayer("Charlie", 2, 100.0),
]

# 2. 配置游戏
config = GameConfig(
    num_players=3,  # 3人游戏
    starting_stack=100.0,
    small_blind=0.5,
    big_blind=1.0,
    verbose=True
)

# 3. 创建游戏并开始
game = PokerGame(players, config)
result = game.play_hand(hand_num=1, btn_seat=0, seed=42)

print(f"Winner: {[players[s].name for s in result.winner_seats]}")
print(f"Pot: {result.pot}BB")
```

## 📋 支持的玩家数量

- **2人游戏**：经典heads-up模式
- **3-6人游戏**：最常见的牌桌配置
- **7-10人游戏**：完整牌桌

## 🎲 位置和盲注

### 2人游戏
```
Seat 0: BTN/SB (庄家同时是小盲)
Seat 1: BB (大盲)

Preflop行动顺序: BTN/SB → BB
Flop/Turn/River: BTN/SB → BB
```

### 3人游戏
```
Seat 0: BTN (庄家)
Seat 1: SB (小盲 0.5BB)
Seat 2: BB (大盲 1.0BB)

Preflop行动顺序: BTN → SB → BB
Flop/Turn/River: SB → BB → BTN
```

### 5人游戏
```
Seat 0: BTN (庄家)
Seat 1: SB (小盲 0.5BB)
Seat 2: BB (大盲 1.0BB)
Seat 3: UTG (Under The Gun)
Seat 4: MP (Middle Position)

Preflop行动顺序: UTG → MP → BTN → SB → BB
Flop/Turn/River: SB → BB → UTG → MP → BTN
```

### 6人游戏
```
BTN → SB → BB → UTG → MP → CO

位置名称：
- BTN: 庄家（最佳位置）
- CO: Cut Off（庄家右边）
- MP: Middle Position
- UTG: Under The Gun（最差位置，大盲左边第一个）
- BB: Big Blind
- SB: Small Blind
```

## 💰 边池 (Side Pot) 系统

当多人all-in且筹码不等时，会自动创建边池：

### 示例场景
```
3人游戏，翻前all-in：
- Player A: 30BB all-in
- Player B: 50BB all-in
- Player C: 100BB call

边池结构：
Main Pot: 90BB (30×3) - A, B, C都有资格
Side Pot 1: 40BB (20×2) - 只有B, C有资格
Side Pot 2: 50BB (50×1) - 只有C有资格
```

边池分配规则：
1. 每个边池独立评估获胜者
2. 只有投入≥该边池的玩家有资格
3. Fold的玩家无资格赢任何边池（但投入仍在pot中）
4. 同等牌力平分边池

## 📊 GameState 在多人游戏中的变化

```python
@dataclass
class GameState:
    street: str              # "preflop", "flop", "turn", "river"
    player: Player          # 当前行动的玩家
    position: str           # "BTN", "SB", "BB", "UTG", "MP", "CO"
    hand: Hand              # 玩家手牌
    board: Board            # 公共牌
    pot: float              # 底池大小
    effective_stack: float  # 有效筹码（所有active玩家中的最小值）
    hero_stack: float       # 自己的筹码
    facing_bet: float       # 面对的下注金额
    to_call: float          # 需要跟注的金额
    min_raise: float        # 最小加注到的金额
    num_active_players: int # ⭐ 当前active的玩家数（未fold）
    num_allin_players: int  # ⭐ all-in的玩家数
    is_in_position: bool    # 是否在位置上（是否是BTN）
```

### 多人策略考虑

在多人游戏中，决策需要考虑：

1. **位置更重要**
   - UTG（最差位置）需要更强的范围
   - BTN（最佳位置）可以更宽松

2. **有效筹码**
   ```python
   effective_stack = min(p.stack for p in active_players)
   ```
   - 你的决策应基于有效筹码
   - 即使你有100BB，如果对手只有20BB，有效筹码是20BB

3. **Active玩家数量**
   ```python
   num_active_players = len([p for p in players if p.is_active])
   ```
   - 玩家越多，获胜概率越低
   - 需要更强的手牌才能继续

4. **范围收窄**
   - UTG open range: ~15-20%
   - BTN open range: ~40-50%
   - 3人pot vs 5人pot需要完全不同的策略

## 🧪 测试示例

### 运行现有测试

```bash
# 3人和4人边池测试
python tests/performance/multiplayer_sidepot_test.py

# 5人游戏完整示例
python tests/performance/5player_example.py
```

### 创建自定义玩家

```python
class TightPlayer(Player):
    """紧凶玩家 - 只玩强牌"""
    def decide(self, game_state: GameState) -> PlayerAction:
        # 根据位置和玩家数量调整策略
        if game_state.num_active_players > 3:
            # 多人pot，更保守
            if game_state.to_call > game_state.pot * 0.5:
                return PlayerAction('fold', 0.0)

        # 位置不好时更谨慎
        if game_state.position in ['UTG', 'MP']:
            # 早位，需要强牌
            if game_state.facing_bet > 3.0:
                return PlayerAction('fold', 0.0)

        # 简单策略：call或check
        if game_state.to_call > 0:
            return PlayerAction('call', 0.0)
        else:
            return PlayerAction('check', 0.0)
```

## 📈 GameResult 结构

多人游戏的结果包含所有玩家的信息：

```python
@dataclass
class GameResult:
    hand_num: int
    btn_seat: int

    # 玩家手牌（按座位索引）
    player_hands: List[str]  # ["AhKh", "QsQd", "7c8c"]

    # 公共牌
    flop: List[str]
    turn: str
    river: str

    # 所有行动记录
    actions: List[ActionRecord]

    # 结果
    winner_seats: List[int]  # [0, 2] 表示seat 0和2获胜（可能平分）
    pot: float
    player_profits: List[float]  # 每个玩家的盈亏

    # Showdown信息
    showdown: bool
    hand_strengths: List[str]  # ["TWO_PAIR", "ONE_PAIR", "FOLDED"]
```

## 🎯 完整5人游戏示例

详见 `tests/performance/5player_example.py`

关键要点：
- 使用 `get_position_name(seat, btn_seat, num_players)` 获取位置名称
- BTN每手轮换：`btn_seat = (btn_seat + 1) % num_players`
- 根据盈亏更新筹码（锦标赛模式）或重置筹码（现金局模式）

## ⚠️ 注意事项

1. **座位索引必须连续**
   ```python
   # ✅ 正确
   players = [
       Player("A", 0, 100.0),
       Player("B", 1, 100.0),
       Player("C", 2, 100.0),
   ]

   # ❌ 错误 - 座位不连续
   players = [
       Player("A", 0, 100.0),
       Player("B", 2, 100.0),  # 缺少seat 1
       Player("C", 3, 100.0),
   ]
   ```

2. **BTN座位必须有效**
   ```python
   # btn_seat必须在 0 到 num_players-1 之间
   result = game.play_hand(hand_num=1, btn_seat=0)  # ✅
   result = game.play_hand(hand_num=1, btn_seat=5)  # ❌ 超出范围
   ```

3. **筹码管理**
   - 游戏会在每手开始时重置所有玩家筹码为 `config.starting_stack`
   - 如果需要保持筹码变化（锦标赛模式），需要手动维护筹码

4. **零和游戏验证**
   ```python
   # 所有玩家盈亏之和应该为0
   total_profit = sum(result.player_profits)
   assert abs(total_profit) < 0.1  # 允许小数误差
   ```

## 🔧 调试技巧

### 启用详细输出
```python
config = GameConfig(
    num_players=5,
    verbose=True,  # 打印每个行动
    debug=True,    # 打印调试信息（行动顺序、筹码变化等）
)
```

### 查看边池计算
边池计算会自动打印（当 `verbose=True` 时）：
```
[SidePot] Calculating side pots:
[SidePot]   seat 0: 30.0BB (active)
[SidePot]   seat 1: 50.0BB (active)
[SidePot]   seat 2: 100.0BB (active)
[SidePot] Main Pot: 90.0BB, eligible=[0,1,2], cap=30.0BB
[SidePot] Side Pot 1: 40.0BB, eligible=[1,2], cap=50.0BB
[SidePot] Side Pot 2: 50.0BB, eligible=[2], cap=100.0BB
```

### 查看行动记录
```python
for action in result.actions:
    print(f"{action.street} - {action.player_name}: {action.action} "
          f"(pot after: {action.pot_after}BB)")
```

## 🚀 高级用法

### 锦标赛模式（筹码持续）
```python
# 初始化玩家筹码
player_stacks = [100.0] * 5

for hand_num in range(100):
    # 更新玩家筹码
    for i, player in enumerate(players):
        player.stack = player_stacks[i]

    # 玩一手牌
    result = game.play_hand(hand_num, btn_seat=hand_num % 5)

    # 更新筹码
    for i in range(5):
        player_stacks[i] += result.player_profits[i]

    # 淘汰筹码为0的玩家
    active_seats = [i for i in range(5) if player_stacks[i] > 0]
    if len(active_seats) == 1:
        print(f"Winner: {players[active_seats[0]].name}")
        break
```

### 自定义盲注结构
```python
config = GameConfig(
    num_players=6,
    starting_stack=200.0,
    small_blind=1.0,   # 1BB小盲
    big_blind=2.0,     # 2BB大盲
)
```

## 📚 相关文件

- 核心实现：`poker_env/poker_game.py`
- 下注逻辑：`poker_env/betting_round.py`
- 边池管理：`poker_env/side_pot.py`
- 工具函数：`poker_env/utils.py`（位置、行动顺序、盲注配置）
- 测试示例：
  - `tests/performance/multiplayer_sidepot_test.py` - 边池测试
  - `tests/performance/5player_example.py` - 5人游戏示例

## ❓ 常见问题

### Q: 如何修改行动顺序？
A: 行动顺序由 `get_action_order()` 自动计算，基于标准德州扑克规则，无需修改。

### Q: 边池是如何计算的？
A: 参见 `poker_env/side_pot.py` 中的详细算法和测试用例。

### Q: 支持Ante（前注）吗？
A: 当前版本不支持，只支持SB/BB盲注结构。

### Q: 可以中途加入/离开玩家吗？
A: 当前版本不支持动态加入/离开。每手牌的玩家数量是固定的。

### Q: 如何实现AI决策？
A: 参考 `tests/performance/2player_env_random_test.py` 中的 `AdvisorV2Player`，
   使用 advisor_v2 模块实现GTO策略。

## ✅ 总结

poker_env 的多人游戏功能已经完全实现并经过测试：

- ✅ 支持2-10人游戏
- ✅ 正确的位置和行动顺序
- ✅ 完整的边池计算和分配
- ✅ 零和游戏保证
- ✅ 详细的游戏状态和结果信息

开始使用吧！🎰
