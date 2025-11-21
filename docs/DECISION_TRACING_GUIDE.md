# AI决策溯源系统使用指南

## 概述

AI决策溯源系统（Decision Tracing System）帮助你深入了解AI决策的完整逻辑链条，包括：
- 每个模块调用的输入输出
- 每个决策步骤的推理逻辑
- 每个步骤的执行时间
- 完整的决策链条可视化

## 快速开始

### 启用追踪

在运行测试时添加 `--trace` 参数：

```bash
# 正常测试（无追踪）
python tests/performance/2player_env_random_test.py --hands 10 --verbose

# 启用决策追踪
python tests/performance/2player_env_random_test.py --hands 5 --verbose --trace

# 只追踪1手牌（调试时推荐）
python tests/performance/2player_env_random_test.py --hands 1 --trace
```

### 输出示例

```
====================================================================================================
🔍 AI决策溯源 - Hand #0 - flop
====================================================================================================

【游戏状态】
  手牌: 4d6d
  公共牌: 2hTh8s
  位置: BTN/SB
  底池: 2.00BB
  面对下注: 0.00BB
  筹码: 99.00BB

【决策链条】共 9 步

  步骤 1: GameState转换
    模块: tests/performance/2player_env_random_test.py
    函数: AdvisorV2Player.decide()
    耗时: 0.00ms
    💡 推理: 将poker_env的GameState转换为advisor格式

  步骤 2: Range分析
    模块: advisor_v2/integration/decision_integrator.py
    函数: _analyze_ranges()
    耗时: 0.54ms
    输出:
      - hero_range_size: 278
      - villain_range_size: 418
      - range_advantage: -0.067
    💡 推理: 分析Hero和Villain的GTO range，以及range interaction

  步骤 3: Equity计算
    模块: advisor_v2/integration/decision_integrator.py
    函数: _calculate_equity()
    耗时: 45.32ms
    输出:
      - point_equity: 0.42
      - equity_distribution: {'crushing': 0.05, 'strong': 0.15, ...}
    💡 推理: 蒙特卡洛模拟计算Hero手牌对抗Villain range的equity

  ...

【最终决策】
  动作: bet
  金额: 1.50BB
  总耗时: 52.15ms

【性能分析】
  最慢步骤:
    1. Equity计算: 45.32ms (86.9%)
    2. Board分析: 3.21ms (6.2%)
    3. Range分析: 0.54ms (1.0%)
```

## 决策链条详解

完整的AI决策包含以下步骤（翻后为例）：

### Phase 1: GameState准备
1. **GameState转换** - poker_env格式 → advisor格式

### Phase 2: Analysis阶段
2. **Range分析** - 分析Hero和Villain的GTO range
   - 输出：hero_range, villain_range, range_advantage
   - 耗时：~0.5ms

3. **Equity计算** (翻后) - 蒙特卡洛模拟
   - 输出：point_equity, equity_distribution
   - 耗时：~40-50ms（最慢）

4. **Board分析** (翻后) - 分析公共牌texture
   - 输出：texture (dry/wet), draw_heavy, equity_realization
   - 耗时：~3ms

### Phase 3: Strategy决策
5. **构建Strategy Context** - 整合所有analysis结果

6. **Hand Percentile估算** (翻前) - 估算手牌在range中的位置
   - 输出：percentile (0-1)

7. **GTO策略决策** - 核心决策逻辑
   - 翻前：基于percentile vs threshold
   - 翻后：基于equity + range advantage + board texture
   - 输出：action_distribution, sizing_distribution, reasoning

8. **翻前/翻后决策** - 具体的决策子逻辑
   - 翻前Open / 翻前Facing Raise
   - 翻后Initiative / 翻后Facing Bet

### Phase 4: Action选择
9. **Action采样** - 从GTO混合策略中随机选择
   - 输出：selected_action, amount (pot fraction)

### Phase 5: 金额转换
10. **金额计算** - 将pot fraction转换为实际BB
    - 检查stack限制
    - all-in检查
    - 规范化到整数BB

## 如何分析决策

### 1. 看推理逻辑 (💡 推理)

每个步骤都有一个推理说明，例如：
```
💡 推理: 基于percentile 0.70 >= 0.7 → 3bet
💡 推理: 基于equity vs pot odds + range advantage做raise/call/fold决策
```

### 2. 看关键输出

重点关注这些关键指标：

**翻前：**
- `percentile`: 手牌在range中的位置（越高越强）
- `raise_threshold`: raise阈值（通常0.50）
- `action_distribution`: 决策混合比例

**翻后：**
- `point_equity`: 胜率
- `pot_odds`: 赔率
- `range_advantage`: range优势（正数=Hero优势）
- `board_texture`: 牌面类型（dry/wet）
- `equity_realization`: 实现率

### 3. 看性能瓶颈

【性能分析】部分列出最慢的3个步骤：
```
最慢步骤:
  1. Equity计算: 45.32ms (86.9%)     ← 最耗时
  2. Board分析: 3.21ms (6.2%)
  3. Range分析: 0.54ms (1.0%)
```

## 常见问题排查

### 问题1：AI fold了一手很强的牌

查看追踪日志：
1. 检查 **Hand Percentile估算** - percentile是否准确？
2. 检查 **Equity计算** - point_equity是否合理？
3. 检查 **GTO策略决策** - action_distribution和reasoning

### 问题2：AI下注size很奇怪

查看追踪日志：
1. 检查 **GTO策略决策** - sizing_distribution是什么？
2. 检查 **金额计算** - pot_multiplier如何转换为actual_amount？
3. 检查是否受stack限制影响

### 问题3：AI决策太慢

查看【性能分析】：
1. Equity计算通常最慢（~40-50ms）- 这是正常的
2. 如果其他步骤>10ms，可能有问题

## 集成到自己的代码

```python
from advisor_v2.debug.decision_tracer import DecisionTracer

# 创建追踪器
tracer = DecisionTracer(enabled=True)

# 传入DecisionIntegrator
integrator = DecisionIntegrator(
    range_engine=range_engine,
    equity_engine=equity_engine,
    board_analyzer=board_analyzer,
    strategy=gto_strategy,
    tracer=tracer  # 添加追踪器
)

# 使用
trace_log = tracer.start_trace(hand_num, game_state)
trace = integrator.decide(game_state)
tracer.finish_trace(action, amount)

# 输出
if tracer.is_enabled():
    print(trace_log.format_full(verbose=True))
```

## 文件结构

追踪系统的核心文件：

```
advisor_v2/
├── debug/
│   ├── __init__.py
│   └── decision_tracer.py          # 追踪器核心
├── integration/
│   └── decision_integrator.py      # 添加追踪点
└── strategy/
    └── gto_strategy.py              # 添加追踪点

tests/performance/
└── 2player_env_random_test.py      # 集成追踪器
```

## 追踪开关性能影响

- **启用追踪**：每手牌增加 ~0.2-0.5ms 开销（可忽略）
- **禁用追踪**：零开销（所有 `if tracer.is_enabled()` 都会被跳过）

## 扩展追踪

如果你想添加更多追踪点：

```python
# 在任何关键函数中
if self.tracer and self.tracer.is_enabled():
    self.tracer.step_begin()

# ... 你的代码 ...

if self.tracer and self.tracer.is_enabled():
    self.tracer.step_end(
        step_name="你的步骤名称",
        module="文件路径",
        function="函数名",
        inputs={"input_key": input_value},
        outputs={"output_key": output_value},
        reasoning="这一步做了什么"
    )
```

## 最佳实践

1. **调试时启用** - 用 `--hands 1 --trace` 查看单手牌的完整决策
2. **对比不同局面** - 比较不同hand/board下的决策差异
3. **性能分析** - 找出决策慢的原因
4. **理解GTO** - 通过推理逻辑学习GTO策略

## 总结

AI决策溯源系统让你能够：
- ✅ 看到AI"在想什么"
- ✅ 理解每个决策背后的逻辑
- ✅ 快速定位决策问题
- ✅ 学习GTO策略原理
- ✅ 优化决策性能

Happy tracing! 🔍
