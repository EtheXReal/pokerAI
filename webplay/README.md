# 1v1 人机对战（本地网页）

与 pokerAI 的完整决策管线（分析 → GTO → exploit + 对手建模）单挑。

## 启动

```bash
python webplay/server.py            # 默认 http://127.0.0.1:8000
python webplay/server.py --port 9000
python webplay/server.py --no-exploit   # AI只用纯GTO，不针对你调整
```

浏览器打开地址即可。零第三方依赖（Python 标准库 + 单页 HTML）。

## 玩法

- 每手牌双方重置 100BB（盲注 0.5/1），按钮位轮换，页面顶部累计你的总盈亏与 BB/100
- 你的回合会出现动作按钮：Fold / Check / Call / Bet(½池·满池·自定义) / Raise to / All-in
- **AI 会实时对你建模**：随着手数增加，它会统计你的 VPIP/AF、给你分类
  （跟注站？疯狂型？），并按类型调整策略——打法忽变可以测试它的适应速度
- 每手结束后：
  - 顶部 AI 标签显示"它眼中的你"（分类 + VPIP/AF）
  - "AI 决策透视"面板展开可看它每条街的 GTO 动作分布、决策理由和 exploit 调整
  - 摊牌时公开 AI 手牌；AI 弃牌则不展示（和真实牌桌一样）

## 架构

```
webplay/server.py    stdlib http.server + JSON API
                     HumanPlayer.decide() 阻塞等待网页动作提交
                     AI = advisor.integration.poker_env_adapter.AdvisorEnvPlayer
webplay/index.html   单页界面，700ms 轮询 /api/state
```

API: `GET /api/state`、`POST /api/new_hand`、`POST /api/action {action, amount}`、`POST /api/reset`
