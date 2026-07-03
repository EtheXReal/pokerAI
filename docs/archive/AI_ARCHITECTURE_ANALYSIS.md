# Poker AI 架构分析报告

## 执行摘要

本报告深入分析了pokerAI项目的真实执行代码路径，确认了以下关键发现：

### ✅ 真正执行的AI架构

**advisor_v2架构** 是当前唯一真正执行的AI系统，advisor(v1)已被架空。

### ⚠️ 多人场景支持状态

**结论：当前AI仅支持2人游戏，不支持3+人游戏**

---

## 一、真正执行的代码架构

### 1.1 执行入口

**测试文件（真正运行的）**：
```
tests/performance/2player_advisor2_test.py  ← 真实执行
tests/performance/2player_env_test.py       ← 使用poker_env环境
```

**核心AI类（真正执行的）**：
```python
# tests/performance/2player_advisor2_test.py: Line 83
class AdvisorV2Player:
    def __init__(self, name: str = "AdvisorV2"):
        self.range_engine = RangeEngine()           # advisor_v2
        self.equity_engine = EquityEngine()         # advisor_v2
        self.board_analyzer = BoardAnalyzer()       # advisor_v2
        self.gto_strategy = GTOStrategy()           # advisor_v2
        self.integrator = DecisionIntegrator(...)   # advisor_v2
```

### 1.2 完整决策链（真实执行）

```
用户请求
  ↓
2player_advisor2_test.py (运行测试)
  ↓
AdvisorV2Player.decide() (Line 100-147)
  ↓
DecisionIntegrator.decide() (advisor_v2/integration/decision_integrator.py: Line 69)
  ↓
[并行执行4个模块]
  ├─→ RangeEngine.get_ideal_range() (分析range)
  ├─→ EquityEngine.calculate_equity() (计算equity，翻后)
  ├─→ BoardAnalyzer.analyze() (分析board，翻后)
  └─→ RangeEngine.analyze_range_interaction() (range优势，翻后)
  ↓
GTOStrategy.decide() (advisor_v2/strategy/gto_strategy.py: Line 65)
  ├─→ _decide_preflop() (翻前)
  └─→ _decide_postflop() (翻后)
  ↓
DecisionIntegrator.select_action() (GTO随机采样)
  ↓
返回 (action, amount)
```

### 1.3 关键代码位置

| 组件 | 文件路径 | 行数 | 职责 |
|------|---------|-----|------|
| AdvisorV2Player | `tests/performance/2player_advisor2_test.py` | 83-165 | AI玩家入口 |
| DecisionIntegrator | `advisor_v2/integration/decision_integrator.py` | 33-276 | 决策编排器 |
| GTOStrategy | `advisor_v2/strategy/gto_strategy.py` | 30-500+ | GTO策略核心 |
| RangeEngine | `advisor_v2/analysis/range_engine.py` | 23-400+ | Range分析 |
| EquityEngine | `advisor_v2/analysis/equity_engine.py` | 全文 | Equity计算 |
| BoardAnalyzer | `advisor_v2/analysis/board_analyzer.py` | 全文 | Board分析 |

---

## 二、被架空的代码（不执行）

### 2.1 advisor (v1) - 完全架空

**位置**：`advisor/strategy_engine/advisor.py`

**状态**：❌ 未被任何测试使用

**原因**：
1. advisor的致命缺陷：基于hand_strength做决策，导致A5o在BTN fold（hand_strength=0.47）
2. advisor_v2修复：基于range percentile做决策，A5o在BTN raise（percentile=0.65）

**证据**：
```python
# advisor/strategy_engine/advisor.py 从未被导入
# 所有测试都使用advisor_v2组件：
from advisor_v2.integration.decision_integrator import DecisionIntegrator
from advisor_v2.analysis.range_engine import RangeEngine
from advisor_v2.strategy.gto_strategy import GTOStrategy
```

### 2.2 其他架空代码

- `advisor/strategy_engine/gto_baseline.py` - 未使用
- `advisor/strategy_engine/hand_strength.py` - 未使用
- `advisor/strategy_engine/exploits.py` - 未使用
- `advisor/opponent_modeling/` - 所有文件未使用（预留给Phase 2）

---

## 三、算法逻辑链详解

### 3.1 翻前决策（Preflop）

```
输入：hand, position, pot_size, stack, facing_bet
  ↓
1. RangeEngine.get_ideal_range(position)
   → 获取GTO开池range（从preflop_ranges.json）
  ↓
2. 计算hand在range中的percentile
   → hand_percentile = get_hand_percentile(hand, gto_range)
  ↓
3. GTOStrategy._decide_preflop()
   3.1 如果 percentile >= 0.50:
       → action_dist = {'raise': 1.0}  # 100% raise
       → sizing = 2.5x BB

   3.2 如果 0.30 <= percentile < 0.50:
       → action_dist = {'raise': 0.20, 'call': 0.70, 'fold': 0.10}
       → 混合策略

   3.3 如果 percentile < 0.30:
       → action_dist = {'fold': 1.0}
  ↓
4. select_action(action_dist)
   → 按概率随机采样（GTO混合策略）
  ↓
输出：(action, amount)
```

**关键改进**：
- ✅ 不再基于hand_strength（绝对值）
- ✅ 基于range_percentile（相对位置）
- ✅ A5o在BTN的percentile=0.65 → raise（正确）

### 3.2 翻后决策（Postflop）

```
输入：hand, position, board, pot_size, stack, facing_bet
  ↓
1. EquityEngine.calculate_equity(hand, villain_range, board)
   → Monte Carlo模拟
   → 返回：point_equity, equity_distribution
  ↓
2. RangeEngine.analyze_range_interaction(hero_range, villain_range, board)
   → 计算nut_advantage, range_size
  ↓
3. BoardAnalyzer.analyze(board)
   → 分析纹理：dry/medium/wet
   → 计算equity_realization因子
  ↓
4. GTOStrategy._decide_postflop()

   4.1 如果 facing_bet:
       4.1.1 计算pot_odds = bet_to_call / (pot + bet_to_call)
       4.1.2 如果 equity > pot_odds * 1.1:
             → action_dist = {'raise': 0.3, 'call': 0.6, 'fold': 0.1}
       4.1.3 如果 equity > pot_odds:
             → action_dist = {'call': 0.8, 'fold': 0.2}
       4.1.4 否则:
             → action_dist = {'fold': 0.7, 'call': 0.3}  # 偶尔bluff catch

   4.2 如果 initiative (not facing_bet):
       4.2.1 如果 equity > 0.55 且 range_advantage > 0:
             → action_dist = {'bet': 0.8, 'check': 0.2}  # Value bet
             → sizing = 0.66 * pot (或根据board调整)
       4.2.2 如果 equity < 0.40 且 bluff_opportunity:
             → action_dist = {'bet': 0.3, 'check': 0.7}  # Bluff
       4.2.3 否则:
             → action_dist = {'check': 1.0}  # Showdown/pot control
  ↓
5. select_action(action_dist)
   → 按概率随机采样
  ↓
输出：(action, amount)
```

**关键因素**：
- ✅ Equity vs Range (不只是point equity)
- ✅ Range Advantage (nut advantage, range size)
- ✅ Board Texture (干燥度影响sizing和频率)
- ✅ 混合策略 (GTO需要randomization)

### 3.3 Sizing决策

```
翻前Sizing:
- Open raise: 2.5x BB (固定)
- 3-bet: 3x opponent's raise
- 4-bet: 2.5x opponent's 3-bet

翻后Sizing (动态):
- Dry board: 0.33 - 0.50 pot (小注控制pot)
- Medium board: 0.50 - 0.75 pot (标准sizing)
- Wet board: 0.75 - 1.00 pot (保护range)

Range Advantage调整:
- 有nut advantage: +20% sizing
- 无nut advantage: -10% sizing
```

---

## 四、多人场景支持分析

### 4.1 当前状态：❌ 不支持3+人游戏

**限制1：RangeEngine只有2人位置**

```python
# advisor_v2/analysis/range_engine.py
# preflop_ranges.json 只包含：
{
  "open_ranges": {
    "BTN": {...},  # 2人位置
    "BB": {...}    # 2人位置
  }
}

# 缺少3+人位置：
# - UTG (Under the Gun)
# - MP (Middle Position)
# - CO (Cut Off)
# - SB (Small Blind, 3+人游戏中SB≠BTN)
```

**证据**：
```python
# advisor_v2/analysis/range_engine.py: Line 144-164
def get_ideal_range(self, position: Position, action_history: list) -> Range:
    if not action_history:
        # 开池range
        cache_key = f'open_{position.name}'
        if cache_key in self.range_cache:
            return self.range_cache[cache_key]
        else:
            # BB不能开池，返回空Range
            return Range()  # 这里会出问题！
```

**问题**：
- 如果position=UTG，cache_key='open_UTG'，不在cache中 → 返回空Range
- 空Range会导致percentile计算错误 → AI无法决策

**限制2：对手建模假设2人**

```python
# advisor_v2/integration/decision_integrator.py: Line 177
def _estimate_villain_position(self, game_state: any) -> Position:
    # 2人游戏：如果hero是BTN，villain是BB；否则反之
    if game_state.position == 'BTN':
        return Position.BB
    else:
        return Position.BTN
```

**问题**：
- 3人游戏：hero=BTN, 那么villain是谁？SB还是BB？
- 当前代码只能处理1个villain，多人游戏有多个villain

**限制3：行动历史解析假设2人**

```python
# advisor_v2/analysis/range_engine.py: Line 169-191
def get_ideal_range(self, position: Position, action_history: list):
    # ...
    if len(action_history) == 1 and last_action.action == 'raise':
        # 假设只有1个opener
        opener_position = self._infer_opener_position(action_history, position)
        # ...
```

**问题**：
- 3人游戏：UTG open, BTN 3-bet, BB 4-bet
- action_history有3个raise，当前代码无法处理

**限制4：Equity计算假设2人**

```python
# advisor_v2/analysis/equity_engine.py
def calculate_equity(self, hero_hand: Hand, villain_range: Range, board: list):
    # Monte Carlo: hero vs 单个villain_range
    # ...
```

**问题**：
- 3人游戏：hero vs villain1_range vs villain2_range
- 需要multiway equity计算，不能只是1v1

### 4.2 修复多人支持需要的改动

#### 改动1：扩展preflop_ranges.json

```json
{
  "open_ranges": {
    "UTG": {"range": "77+,ATs+,KQs,AQo+", "frequency": 0.15},
    "MP": {"range": "66+,A9s+,KTs+,QTs+,JTs,AJo+", "frequency": 0.18},
    "CO": {"range": "55+,A2s+,K9s+,Q9s+,J9s+,T8s+,98s,A9o+,KTo+", "frequency": 0.25},
    "BTN": {"range": "22+,A2s+,K2s+,Q5s+,J7s+,T7s+,97s+,87s,76s,65s,A2o+,K5o+,Q8o+,J8o+", "frequency": 0.40},
    "SB": {"range": "22+,A2s+,K2s+,Q6s+,J7s+,T7s+,97s+,87s,76s,A5o+,K9o+,Q9o+", "frequency": 0.35},
    "BB": {"range": "", "frequency": 0.0}
  },
  "vs_open_3bet_ranges": {
    "BTN_vs_UTG": {...},
    "BTN_vs_MP": {...},
    "BTN_vs_CO": {...},
    "SB_vs_UTG": {...},
    "SB_vs_MP": {...},
    "SB_vs_CO": {...},
    "SB_vs_BTN": {...},
    "BB_vs_UTG": {...},
    "BB_vs_MP": {...},
    "BB_vs_CO": {...},
    "BB_vs_BTN": {...},
    "BB_vs_SB": {...}
  }
}
```

**工作量**：中等（需要GTO solver数据或使用标准range）

#### 改动2：RangeEngine支持多人位置

```python
# advisor_v2/analysis/range_engine.py
def get_ideal_range(self, position: Position, action_history: list,
                    num_players: int = 2) -> Range:  # 新增num_players参数
    """
    获取GTO理论范围（支持2-10人）

    Args:
        position: 位置 (BTN/SB/BB/UTG/MP/CO)
        action_history: 行动历史
        num_players: 玩家数量
    """
    # 根据num_players选择对应的range
    if num_players == 2:
        # 使用2人range
        ...
    else:
        # 使用多人range
        cache_key = f'open_{position.name}_{num_players}p'
        if cache_key in self.range_cache:
            return self.range_cache[cache_key]
        else:
            # 使用通用range作为fallback
            return self._get_default_range(position, num_players)
```

**工作量**：中等

#### 改动3：DecisionIntegrator支持多人

```python
# advisor_v2/integration/decision_integrator.py
def _analyze_ranges(self, game_state: any) -> tuple:
    # 不再假设只有1个villain
    # 需要获取所有对手的range并合并

    opponent_positions = self._get_all_opponent_positions(game_state)

    # 合并所有对手的range
    villain_ranges = []
    for opp_pos in opponent_positions:
        opp_range = self.range_engine.get_ideal_range(
            position=opp_pos,
            action_history=[],
            num_players=game_state.num_players
        )
        villain_ranges.append(opp_range)

    # 组合range（weighted by position）
    combined_villain_range = self._combine_ranges(villain_ranges)

    return hero_range, combined_villain_range, range_advantage
```

**工作量**：大（需要重新设计对手建模逻辑）

#### 改动4：EquityEngine支持multiway

```python
# advisor_v2/analysis/equity_engine.py
def calculate_equity(self, hero_hand: Hand, villain_ranges: List[Range],
                    board: list, num_players: int = 2) -> EquityInfo:
    """
    计算equity（支持multiway）

    Args:
        hero_hand: Hero的手牌
        villain_ranges: 所有对手的range列表
        board: 公共牌
        num_players: 玩家数量
    """
    if num_players == 2:
        # 使用现有的1v1算法
        return self._calculate_heads_up(hero_hand, villain_ranges[0], board)
    else:
        # 使用multiway算法
        return self._calculate_multiway(hero_hand, villain_ranges, board)
```

**工作量**：大（multiway equity计算复杂度高）

#### 改动5：GTOStrategy调整频率

```python
# advisor_v2/strategy/gto_strategy.py
def _decide_preflop(self, ctx: StrategyContext) -> StrategyDecision:
    # 根据num_players调整阈值
    if ctx.num_players == 2:
        raise_threshold = 0.50
    elif ctx.num_players <= 4:
        raise_threshold = 0.40  # 短桌更aggressive
    else:
        raise_threshold = 0.20  # 满桌更tight

    # ...
```

**工作量**：小

### 4.3 总工作量估算

| 改动 | 难度 | 工作量 | 优先级 |
|------|------|--------|--------|
| 扩展preflop_ranges.json | 中 | 2-3天 | P0 |
| RangeEngine支持多人 | 中 | 2-3天 | P0 |
| DecisionIntegrator支持多人 | 大 | 5-7天 | P0 |
| EquityEngine multiway | 大 | 7-10天 | P1 |
| GTOStrategy调整 | 小 | 1天 | P1 |
| 测试和验证 | 大 | 5-7天 | P0 |

**总计**：20-30天（全职开发）

---

## 五、poker_env与AI的集成

### 5.1 poker_env是否支持多人？

✅ **是的，poker_env完全支持2-10人游戏**

**证据**：
```python
# poker_env/poker_game.py: Line 73-74
if config.num_players < 2 or config.num_players > 10:
    raise ValueError(f"Number of players must be 2-10, got {config.num_players}")
```

**包含**：
- ✅ 正确的行动顺序（2人和多人）
- ✅ 盲注配置（2人和多人）
- ✅ 边池计算（多人all-in）
- ✅ Showdown逻辑（多人比牌）

**测试**：
```bash
python tests/performance/multiplayer_sidepot_test.py
# 3人和4人游戏测试全部通过 ✓
```

### 5.2 AI与poker_env的接口

```python
# poker_env/player.py
class Player(ABC):
    @abstractmethod
    def decide(self, game_state: GameState) -> PlayerAction:
        """
        做决策

        Args:
            game_state: 包含所有决策所需信息
                - street: 'preflop'/'flop'/'turn'/'river'
                - position: 位置
                - hand: Hero的手牌
                - board: 公共牌
                - pot: Pot大小
                - facing_bet: 面对的下注
                - num_active_players: 活跃玩家数 ← 关键！

        Returns:
            PlayerAction(action, amount)
        """
        pass
```

**关键**：`game_state.num_active_players` 已经包含在接口中！

### 5.3 适配AdvisorV2Player到多人

**当前接口（2player_advisor2_test.py）**：
```python
class AdvisorV2Player:
    def decide(self, street: str, position: str, hand: Hand, board: Board,
               pot_size: float, effective_stack: float, hero_stack: float,
               facing_bet: float, bet_to_call: float) -> Tuple[str, float]:
        # ...
```

**poker_env接口**：
```python
class AdvisorV2EnvPlayer(Player):  # 继承poker_env.Player
    def decide(self, game_state: GameState) -> PlayerAction:
        # 转换game_state到advisor_v2格式
        advisor_game_state = self._convert_game_state(game_state)

        # 调用advisor_v2决策
        trace = self.integrator.decide(advisor_game_state)
        selected_action = self.integrator.select_action(trace.gto_decision)

        return PlayerAction(selected_action.action, selected_action.amount)
```

**关键点**：
- poker_env已经支持多人
- advisor_v2不支持多人
- **需要修复advisor_v2，而不是poker_env**

---

## 六、结论与建议

### 6.1 当前状态总结

| 组件 | 2人支持 | 多人支持 | 状态 |
|------|--------|---------|------|
| poker_env | ✅ | ✅ | 生产就绪 |
| advisor_v2/RangeEngine | ✅ | ❌ | 需要修复 |
| advisor_v2/DecisionIntegrator | ✅ | ❌ | 需要修复 |
| advisor_v2/EquityEngine | ✅ | ❌ | 需要修复 |
| advisor_v2/GTOStrategy | ✅ | ⚠️ | 需要调整 |
| advisor_v2/BoardAnalyzer | ✅ | ✅ | 无需修改 |

### 6.2 短期建议（如果只想测试多人环境）

**方案：使用SimpleRandomPlayer**

```python
# 创建3人游戏，AI vs 2个Random对手
from poker_env import PokerGame, GameConfig, Player, PlayerAction, GameState
import random

class SimpleRandomPlayer(Player):
    """简单随机玩家（不需要advisor_v2）"""
    def decide(self, game_state: GameState) -> PlayerAction:
        if game_state.to_call > 0:
            # 面对下注：70% call, 30% fold
            if random.random() < 0.7:
                return PlayerAction('call', 0.0)
            else:
                return PlayerAction('fold', 0.0)
        else:
            # 未面对下注：50% check, 50% bet
            if random.random() < 0.5:
                return PlayerAction('check', 0.0)
            else:
                bet_size = game_state.pot * 0.66
                return PlayerAction('bet', bet_size)

# 创建3人游戏
players = [
    SimpleRandomPlayer("Player1", 0, 100.0),
    SimpleRandomPlayer("Player2", 1, 100.0),
    SimpleRandomPlayer("Player3", 2, 100.0),
]

config = GameConfig(num_players=3, starting_stack=100.0)
game = PokerGame(players, config)

# 运行100手
for i in range(100):
    result = game.play_hand(hand_num=i, btn_seat=i%3)
    print(f"Hand {i}: Winners={result.winner_seats}, Pot={result.pot}")
```

**优点**：
- ✅ 可以立即测试3+人环境
- ✅ 验证poker_env的边池逻辑
- ✅ 不需要修改advisor_v2

**缺点**：
- ❌ 对手是随机的，没有策略
- ❌ 无法测试advisor_v2在多人游戏中的表现

### 6.3 长期建议（如果要让AI支持多人）

**必须完成的改动**（按优先级）：

1. **P0: 扩展preflop_ranges.json**
   - 添加UTG/MP/CO/SB/BB的开池range
   - 添加所有位置组合的3-bet/4-bet range
   - 工作量：2-3天

2. **P0: 修改RangeEngine**
   - 支持num_players参数
   - 处理多人位置
   - 工作量：2-3天

3. **P0: 修改DecisionIntegrator**
   - 支持多个villain
   - 合并多个对手range
   - 工作量：5-7天

4. **P1: 修改EquityEngine（可选）**
   - Multiway equity计算
   - 或者使用简化方法：合并所有对手range → 单个combined_range
   - 工作量：7-10天（完整multiway）或2-3天（简化方法）

5. **P1: 调整GTOStrategy**
   - 根据num_players调整频率和sizing
   - 工作量：1天

6. **P0: 集成测试**
   - 创建3人、4人、6人测试
   - 验证range、equity、决策都正确
   - 工作量：5-7天

**建议的开发顺序**：
```
Phase 1 (1周): P0改动 + 简化版equity
  → 可以运行3+人游戏，决策合理但不完美

Phase 2 (2周): 完整multiway equity + 调优
  → AI决策接近GTO水平

Phase 3 (1周): 压力测试 + bug修复
  → 生产就绪
```

### 6.4 最终回答用户的问题

**问题1：哪些代码真正执行？**
- ✅ advisor_v2 全套（RangeEngine, EquityEngine, BoardAnalyzer, GTOStrategy, DecisionIntegrator）
- ❌ advisor (v1) 已被架空

**问题2：AI如何处理多人场景？**
- ❌ 当前不支持
- ⚠️ RangeEngine只有2人位置range
- ⚠️ DecisionIntegrator假设1个villain
- ⚠️ EquityEngine只支持1v1

**问题3：AI是否可以适配多人场景？**
- ✅ 可以，但需要20-30天开发工作量
- ✅ poker_env已经准备好（支持2-10人）
- ⚠️ 需要扩展advisor_v2的核心模块

---

## 附录A：快速验证脚本

### A.1 验证当前AI只支持2人

```bash
cd /path/to/pokerAI

# 尝试运行3人游戏（会失败或产生错误决策）
python -c "
from advisor_v2.analysis.range_engine import RangeEngine
from advisor.strategy_engine.gto_baseline import Position

engine = RangeEngine()

# 尝试获取UTG的range（3+人位置）
try:
    range = engine.get_ideal_range(Position.UTG, [])
    print(f'UTG range: {range.to_string()}')
except Exception as e:
    print(f'Error: {e}')
    print('UTG position not supported!')
"
```

### A.2 验证poker_env支持多人

```bash
# 运行多人测试
python tests/performance/multiplayer_sidepot_test.py

# 应该看到：
# Test 1: 3-player simple side pot scenario ✓
# Test 2: 4-player cascading all-in scenario ✓
# Test 3: 3-player with one fold scenario ✓
# Test 4: 3-player equal investment scenario ✓
# All integration tests passed! ✓
```

---

## 附录B：代码流程图

```
┌─────────────────────────────────────────────────────────────┐
│                    Poker AI 决策流程图                      │
└─────────────────────────────────────────────────────────────┘

                        用户启动测试
                              │
                              ▼
              ┌───────────────────────────────┐
              │ 2player_advisor2_test.py      │
              │ - 创建AdvisorV2Player         │
              │ - 初始化advisor_v2组件        │
              └───────────────┬───────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │ AdvisorV2Player.decide()      │
              │ - 接收game_state               │
              │ - 调用DecisionIntegrator      │
              └───────────────┬───────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │ DecisionIntegrator.decide()   │
              │ - 编排所有模块                 │
              └───────────────┬───────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │ RangeEngine │ │EquityEngine │ │BoardAnalyzer│
    │ - 分析range │ │ - 计算equity│ │ - 分析board │
    └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
           │               │               │
           └───────────────┼───────────────┘
                           │
                           ▼
              ┌───────────────────────────────┐
              │ GTOStrategy.decide()          │
              │ - 翻前: range percentile决策  │
              │ - 翻后: equity+range决策      │
              └───────────────┬───────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │ select_action()               │
              │ - GTO随机采样                 │
              │ - 返回(action, amount)        │
              └───────────────────────────────┘
```

---

## 附录C：关键数据流

### C.1 翻前数据流

```
Hand: AsKd, Position: BTN, Pot: 1.5BB, Stack: 100BB
  │
  ▼
RangeEngine.get_ideal_range(BTN)
  → Range: "22+,A2s+,K2s+,Q5s+,..." (40%开池频率)
  │
  ▼
get_hand_percentile(AsKd, BTN_range)
  → percentile: 0.95 (AsKd在BTN range中排名前5%)
  │
  ▼
GTOStrategy._decide_preflop()
  → 0.95 >= 0.50 (raise_threshold)
  → action_dist: {'raise': 1.0}
  → sizing: 2.5BB
  │
  ▼
select_action({'raise': 1.0})
  → action: 'raise', amount: 2.5BB
```

### C.2 翻后数据流

```
Hand: AsKd, Board: Kh7s3c, Position: BTN, Pot: 10BB, Stack: 95BB
  │
  ▼
EquityEngine.calculate_equity(AsKd, villain_range, [Kh7s3c])
  → point_equity: 0.78
  → equity_distribution: {crushing: 0.4, strong: 0.35, ahead: 0.25}
  │
  ▼
RangeEngine.analyze_range_interaction(hero_range, villain_range, board)
  → nut_advantage: +0.15 (hero有更多nuts)
  → range_size: hero=280 combos, villain=220 combos
  │
  ▼
BoardAnalyzer.analyze([Kh7s3c])
  → texture: 'dry' (rainbow, no straights)
  → equity_realization: 0.85
  │
  ▼
GTOStrategy._decide_postflop_initiative()
  → equity=0.78 > 0.55 (value_threshold)
  → range_advantage=+0.15 > 0
  → action_dist: {'bet': 0.8, 'check': 0.2}
  → sizing: 0.66 * 10BB = 6.6BB (基于dry board)
  │
  ▼
select_action({'bet': 0.8, 'check': 0.2})
  → random(0,1) = 0.35 < 0.8
  → action: 'bet', amount: 6.6BB
```

---

**报告完成时间**：2025-01-13
**作者**：Claude (Sonnet 4.5)
**版本**：1.0
