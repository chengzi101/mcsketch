---
name: mcsketch
description: Identify a user-provided food sketch, match a McDonald's menu, and repair a meal within budget using the McSketch core and official read-only MCP tools. Use for sketch-to-meal or McSketch budget requests.
---

# 麦麦画餐师

在项目根目录执行 `python scripts/skill_cli.py ACTION --input request.json`，或使用同名 `/api/ACTION`。网页和此入口共享 `backend.service`、`vision`、`matching` 和 `optimizer`。无需复制算法。

## 执行

1. 读取用户 PNG，通过 `recognize` 传入 `{"image":"data:image/png;base64,..."}`。最多 3 MB、16–2048 像素。模型返回 Top-3 与 uncertain；评分不是准确率。status=manual 时明确说明模型不可用，不生成伪候选。
2. 请用户确认或纠正视觉类别：burger / fries / icecream / drink / nuggets / coffee。首版一张画只处理一种食物，多种食物逐张确认。
3. 没有 Token 时使用 mode=demo、store_id=demo-studio，所有价格和营养标为合成样例。Live 从后端 MCD_MCP_TOKEN 读取凭据，绝不向用户索要明文 Token 放进请求或日志。
4. Live 先 `live/tools` 读取实际官方 inputSchema，用 `live/call` 传 `{"tool":"query-nearby-stores","arguments":{...}}` 查询附近门店。仅使用服务返回的必需参数、门店和商品 ID。官方公开 README 不含完整参数/返回 schema，不能凭工具名猜参数。自动映射未配置时依照 [MCP_INTEGRATION.md](../MCP_INTEGRATION.md) 完成映射，或明确报告未就绪。
5. `stores` → `menu` → `match`。后两者传 mode、store_id，match 追加 category。详情用 `detail`，营养缺失时输出 null；不要推断忌口或拼接不可靠营养行。
6. 组建 `items:[{"id":"服务返回ID","qty":1}]`。最多 6 份、12 种。向 `repair` 提交整数 `budget_cents`，可选 `locked_ids`（硬保留）、`favorite_ids`（软偏好）、`avoid`（milk/beef/chicken/gluten/caffeine）、`max_kcal`（整数或 null）。
7. 返回 A 最少修改、B 价格优先、C 偏好优先。不可行时说明原因，不通过删除整类需求制造低价。不同策略可输出相同结果。
8. Live 最终金额只能来自 calculate-price；Demo 金额不能称为官方核价。购物车、门店、模式变化后旧报价失效；超过 120 秒重新 quote。采用方案后重新核价。

## 依赖与错误

官方远程 MCP：`https://mcp.mcd.cn`，Streamable HTTP，Bearer 鉴权，官方 Python SDK 1.x。只允许 query-nearby-stores、query-meals、query-meal-detail、list-nutrition-foods、calculate-price。绝不创建订单、支付、领取权益。

401 提示检查后端 Token；429、超时、暂时连接错误由客户端最多重试一次。schema 不符停止 Live 自动流程；可以询问是否切换明确标注的 Demo。不要把 Live 失败静默替换成 Demo 结果。

## 输出

保留 API 的结构化结果：mode/source、store_id、确认类别、商品 ID 与份数、original_quote、三种 plans（feasible、修改、理由、delta_cents、quote.official、within_budget）、缺失数据与验证限制。MCP 原始响应可能含个人信息，不保存为公开示例。

演示输入见 [examples/repair-request.json](../examples/repair-request.json)。视觉、运行和联调限制见 [README.md](../README.md)。
