# Poker Environment - 通用德州扑克环境

这是一个通用的德州扑克游戏环境，支持2-10人游戏。

## 设计目标

1. **环境与测试分离**: 游戏逻辑独立于具体的测试代码
2. **通用的行动顺序**: 支持2人到多人游戏
3. **可扩展**: 易于添加新的玩家实现
4. **符合德州扑克规则**: 完整的4个街道决策，正确的all-in逻辑

## 特性

- ✅ 支持2-10人游戏
- ✅ 完整的4个街道（Preflop, Flop, Turn, River）
- ✅ 正确的行动顺序（符合德州扑克规则）
- ✅ All-in逻辑
- ✅ **完整的边池（Side Pot）支持** - 多人all-in时自动计算和分配
- ✅ 玩家抽象接口（易于接入不同AI）
- ✅ 详细的行动记录
- ✅ 完整的游戏结果（包括盈亏）

## 架构

```
poker_env/
├── __init__.py          # 模块入口
├── poker_game.py        # 核心游戏引擎
├── betting_round.py     # Betting round逻辑
├── player.py            # 玩家基类和接口
├── side_pot.py          # 边池计算和分配 ⭐ NEW
└── utils.py             # 工具函数（座位、位置等）
```

## 核心类

### 1. PokerGame
核心游戏引擎，管理整手牌的流程。

```python
from poker_env import PokerGame, GameConfig, Player

# 创建玩家
players = [player1, player2, ...]

# 创建配置
config = GameConfig(
    num_players=2,
    starting_stack=100.0,
    small_blind=0.5,
    big_blind=1.0,
    verbose=True
)

# 创建游戏
game = PokerGame(players, config)

# 玩一手牌
result = game.play_hand(hand_num=0, btn_seat=0, seed=42)
```

### 2. Player (抽象基类)
所有玩家实现都必须继承这个类。

```python
from poker_env import Player, PlayerAction, GameState

class MyPlayer(Player):
    def __init__(self, name: str, seat: int, stack: float):
        super().__init__(name, seat, stack)
        # 初始化你的AI组件

    def decide(self, game_state: GameState) -> PlayerAction:
        # 实现决策逻辑
        return PlayerAction('call', 0.0)
```

### 3. GameState
传递给玩家的游戏状态信息。

```python
@dataclass
class GameState:
    street: str              # 'preflop', 'flop', 'turn', 'river'
    player: Player          # 当前决策的玩家
    position: str           # 位置名称 (BTN, SB, BB, etc.)
    hand: Hand              # 玩家手牌
    board: Board            # 公共牌
    pot: float              # 底池大小
    effective_stack: float  # 最小有效筹码
    hero_stack: float       # 当前玩家筹码
    facing_bet: float       # 面对的下注金额
    to_call: float          # 需要call的金额
    min_raise: float        # 最小加注金额
    num_active_players: int # 还在游戏中的玩家数
    num_allin_players: int  # 已all-in的玩家数
    is_in_position: bool    # 是否在位置优势
```

### 4. PlayerAction
玩家的决策返回值。

```python
@dataclass
class PlayerAction:
    action: str  # 'fold', 'check', 'call', 'bet', 'raise'
    amount: float  # 对于bet/raise，是raise增量（不是raise to的总额）
```

## 行动顺序规则

### 德州扑克标准规则

**Preflop**:
- 从大盲左边第一个开始（UTG）
- 到大盲结束

**Flop/Turn/River**:
- 从庄家左边第一个开始（SB）
- 到庄家结束

### 2人游戏特殊情况

- BTN = SB（庄家同时是小盲）
- **Preflop**: SB (BTN)先行动，需要补齐大盲
- **Flop/Turn/River**: SB (BTN)先行动

### 实现细节

```python
# 获取行动顺序
from poker_env.utils import get_action_order, Street

# 2人游戏，BTN=0，Preflop
order = get_action_order(num_players=2, btn_seat=0, street=Street.PREFLOP)
# 返回: [0, 1]  (SB先动，然后BB)

# 6人游戏，BTN=0，Preflop
order = get_action_order(num_players=6, btn_seat=0, street=Street.PREFLOP)
# 返回: [3, 4, 5, 0, 1, 2]  (UTG到BB)

# 6人游戏，BTN=0，Flop
order = get_action_order(num_players=6, btn_seat=0, street=Street.FLOP)
# 返回: [1, 2, 3, 4, 5, 0]  (SB到BTN)
```

## 使用示例

### 示例1: 2人测试

见 [tests/performance/2player_env_test.py](../../tests/performance/2player_env_test.py)

### 示例2: 自定义玩家

```python
from poker_env import Player, PlayerAction, GameState
import random

class SimpleRandomPlayer(Player):
    """简单的随机玩家"""

    def decide(self, game_state: GameState) -> PlayerAction:
        if game_state.to_call <= 0.01:
            # 不面对下注
            if random.random() < 0.5:
                # 50%概率bet
                bet_size = game_state.pot * random.uniform(0.5, 1.0)
                return PlayerAction('bet', bet_size)
            else:
                return PlayerAction('check', 0.0)
        else:
            # 面对下注
            if random.random() < 0.3:
                return PlayerAction('fold', 0.0)
            elif random.random() < 0.7:
                return PlayerAction('call', 0.0)
            else:
                # Raise
                raise_size = game_state.facing_bet * random.uniform(2.0, 3.0)
                return PlayerAction('raise', raise_size)
```

## All-in逻辑

环境正确处理所有all-in场景：

1. **All-in后不再行动**: All-in的玩家在后续街道不会被要求决策
2. **跳过betting round**: 如果所有active玩家都all-in，跳过后续betting rounds
3. **Uncalled bet退回**: 当对手all-in且筹码不足call时，正确退回uncalled bet
4. **最小加注规则**: 允许all-in不足最小加注（符合德州扑克规则）

## Pot计算

所有pot计算都经过验证，符合德州扑克规则：

1. **盲注正确投入**: 2人游戏BTN投入SB，BB投入BB；多人游戏按座位顺序投入
2. **街道投入分离**: 每个街道的投入单独计算，不与总投入混淆
3. **边池处理**: All-in时正确处理边池逻辑（见下一节）
4. **Uncalled bet**: 正确处理未被call的下注

## 边池（Side Pot）⭐

完整的边池支持，处理多人all-in场景。详细文档见 [SIDEPOT_IMPLEMENTATION.md](SIDEPOT_IMPLEMENTATION.md)。

### 什么是边池？

当多个玩家all-in且stack大小不同时，会创建多个边池（pot）。每个玩家只能赢得他们有资格竞争的pot部分。

**示例**：
```
3人游戏：
- Player A: all-in 30BB
- Player B: all-in 50BB
- Player C: call 50BB

结果：
- Main Pot: 90BB (30×3), eligible=[A, B, C]
- Side Pot 1: 40BB (20×2), eligible=[B, C]
总计: 130BB

如果A赢：A获得90BB（Main Pot）
如果B赢：B获得130BB（Main Pot + Side Pot 1）
如果C赢：C获得130BB（Main Pot + Side Pot 1）
```

### 使用方法

边池计算是自动的，无需任何额外配置：

```python
from poker_env import PokerGame, GameConfig

game = PokerGame(players, config)
result = game.play_hand(hand_num=0, btn_seat=0)

# 边池信息会在verbose=True时自动打印
# result中包含正确的玩家盈亏
```

### 详细日志

设置`verbose=True`可以看到边池计算过程：

```
[SidePot] Calculating side pots:
[SidePot]   seat 0: 30.0BB (active)
[SidePot]   seat 1: 50.0BB (active)
[SidePot]   seat 2: 100.0BB (active)
[SidePot] Main Pot: 90.0BB, eligible=[0, 1, 2], cap=30.0BB
[SidePot] Side Pot 1: 40.0BB, eligible=[1, 2], cap=50.0BB
[SidePot] Side Pot 2: 50.0BB, eligible=[2], cap=100.0BB

[SidePot] Distributing pots:
[SidePot] Main Pot: 90.0BB, eligible=[0, 1, 2]
[SidePot]   Player_B wins 90.0BB
[SidePot] Side Pot 1: 40.0BB, eligible=[1, 2]
[SidePot]   Player_B wins 40.0BB
[SidePot] Side Pot 2: 50.0BB, eligible=[2]
[SidePot]   Player_C wins 50.0BB
```

### 测试

完整的测试套件：

```bash
# 单元测试
python poker_env/side_pot.py

# 集成测试（3-4人游戏）
python tests/performance/multiplayer_sidepot_test.py
```

全部测试通过 ✓

## 与原版测试对比

### 兼容性

新环境与原有的`2player_advisor2_test_FIXED.py`完全兼容：

```bash
# 原版测试（修复后）
python tests/performance/2player_advisor2_test_FIXED.py --hands 10 --seed 42

# 新环境测试
python tests/performance/2player_env_test.py --hands 10 --seed 42
```

两者应该产生相同的结果（因为使用相同的随机种子和决策逻辑）。

### 优势

1. **代码更清晰**: 环境逻辑与测试逻辑分离
2. **更易扩展**: 添加新玩家只需继承`Player`类
3. **支持多人**: 可以轻松扩展到3-10人游戏
4. **更易测试**: 每个组件都可以独立测试

## 扩展到多人游戏

### 示例: 3人游戏

```python
from poker_env import PokerGame, GameConfig, Player

# 创建3个玩家
player1 = MyAIPlayer("AI1", seat=0, stack=100.0)
player2 = MyAIPlayer("AI2", seat=1, stack=100.0)
player3 = MyAIPlayer("AI3", seat=2, stack=100.0)

players = [player1, player2, player3]

# 配置
config = GameConfig(
    num_players=3,
    starting_stack=100.0,
    small_blind=0.5,
    big_blind=1.0,
    verbose=True
)

# 运行游戏
game = PokerGame(players, config)
result = game.play_hand(hand_num=0, btn_seat=0, seed=42)

# BTN=0, SB=1, BB=2
# Preflop行动顺序: seat 0 (BTN) -> seat 1 (SB) -> seat 2 (BB)
# Flop/Turn/River: seat 1 (SB) -> seat 2 (BB) -> seat 0 (BTN)
```

## 调试

### Debug模式

```python
config = GameConfig(
    num_players=2,
    starting_stack=100.0,
    small_blind=0.5,
    big_blind=1.0,
    verbose=True,
    debug=True  # 开启debug模式
)

game = PokerGame(players, config)
result = game.play_hand(hand_num=0, btn_seat=0, seed=42)
```

Debug模式会输出详细的计算过程：
- 每个玩家的stack和invested
- Facing bet和to_call
- 决策信息
- Pot变化

### 单元测试

TODO: 添加单元测试覆盖所有核心功能

## 已知问题和TODO

- [x] 添加单元测试 - 部分完成（边池测试完成）
- [x] 支持边池（多人all-in）- ✅ 已完成
- [ ] 添加更多位置名称（EP, MP1, MP2等）
- [ ] 支持ante
- [ ] 性能优化
- [ ] 添加更多调试工具
- [ ] 完整的单元测试覆盖（betting_round, poker_game等）

## 贡献

欢迎提交PR改进这个环境！

## License

MIT
