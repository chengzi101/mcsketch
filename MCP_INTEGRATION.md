# 麦当劳 MCP 接入与实测

核对日期：2026-10-24。已用有效 Token 完成官方认证、tools/list、五个只读工具及三方案再次核价。见 [真实报告](docs/LIVE_INTEGRATION_REPORT.md) 和 [脱敏机器记录](artifacts/mcp-live-audit.json)。验证范围是本次到店取餐与默认规格。

## 协议与凭据

[官方文档](https://github.com/M-China/mcd-mcp-server)指定 https://mcp.mcd.cn、Streamable HTTP 和 Bearer 认证。实现使用官方 mcp Python SDK：streamable_http_client → ClientSession.initialize → list_tools → JSON Schema 校验 → call_tool，HTTP/SSE、会话及协议协商由 SDK 完成。

根目录 .env 设置 MCD_MCP_TOKEN，重启后端。backend/app.py 使用项目绝对路径 load_dotenv(ROOT / '.env')，已有进程环境变量优先。状态接口仅返回是否非空，不返回值。缺 Token 阻止 Live，Demo 仍可用。不要开启 HTTP 请求头调试日志。Token 不进入前端、公开记录或发布包。

## 实际工具和映射

只允许以下五个工具。每次调用前读取真实 tools/list 并校验 inputSchema；最多十页，未读取完整则停止。不调用下单、支付、积分兑换或权益领取工具。

| 工具 | 本次实际参数 | 实际响应 |
|---|---|---|
| query-nearby-stores | beType=1、searchType=2、city、keyword | data 数组；storeCode、storeName、address |
| query-meals | storeCode 字符串、orderType=1、beType=1 | data.meals 是按 SKU 索引的字典；name、currentPrice |
| query-meal-detail | 上述场景参数及 code 字符串 | data.code、name、rounds、modification、supportModify |
| list-nutrition-foods | 空对象 {} | data 是平面 TOON 表字符串 |
| calculate-price | storeCode、orderType=1、beType=1、items | data.price 是整数分 |

附近门店 Schema 必填 beType/searchType；searchType=2 的 city/keyword 还来自官方语义要求。菜单和详情的场景参数不可省略。核价顶层 Schema 必填场景参数，合法餐单还需要 items；每项是 productCode、quantity，而非内部 id/qty。到店取餐不传 beCode。完整实际 Schema 仅保存在本地 private/，公开报告不保留定位和账号响应。

所有业务响应先验证 success=true 再读 data。当前适配见 [official.py](backend/mcp_client/official.py)，没有内嵌真实门店、账号或商品 ID。

- 菜单字典 key 保留为 SKU；currentPrice 是元字符串，经 Decimal 转整数分，仅作参考价。真实应付取自 calculate-price 的 data.price，不用原价、优惠额或菜单单价之和冒充。
- rounds 仅提交 isDefault=1 且 quantity>0 的选择，使用实际 round id、子项 code/quantity 及 selectedKey/unselectedKey。缺默认选择或已选键值时停止，不猜规格。
- 实测菜单“薯条”的详情是“中薯条”，可乐的默认子项是“可乐小杯”。营养用实际详情名或唯一默认子项名精确匹配 productName；不能唯一确定时保持未知，不模糊拼接套餐营养。
- 本次 TOON 表头为 productName、nutritionDescription、energyKj、energyKcal、protein、fat、carbohydrate、sodium、calcium。严格校验行数、列数和引号，仅支持观察到的平面逗号表格；结构变化报 schema_drift。
- 营养缺失显示“—”；热量硬上限排除未知值；未核实过敏原不能视为忌口安全。
- 多件套、分享餐、会员加购不作单种食物的替代候选。详情/营养缓存 60 秒；菜单、可售结果和报价不缓存。

## 复现

1. 配置 Token 并重启，在「连接官方 MCP」读取真实 schema。
2. 输入“城市 位置关键词”（空格分隔），查询门店。真实菜单成功读取后才启用 Live；无需另建 live-bindings.json。
3. 确认类别、选择餐品，点详情查营养；加入购物车并核价。设置预算/偏好并修复，采用后重新核价再导出 PNG。
4. CLI 复测：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/verify_live.py --schema-output private/mcp-schemas.json
.\.venv\Scripts\python.exe -X utf8 scripts/verify_live.py --requests private/live-acceptance.json
```

第一条只验认证/schema，退出码 2 表示未执行完整业务，不代表认证失败。第二条参数字段为内部 address、category、items:[{id,qty}]、budget_cents、locked_ids、favorite_ids、avoid、max_kcal，实际商品 ID 必须来自当前真实菜单，见 [提交步骤](docs/CONTEST_SUBMISSION.md)。仅 authenticated_business_chain=true 表示本次完整验收通过。公开记录只含阶段、计数、金额、状态。

可选自定义 live-bindings.json 仍按 [Schema](docs/live-bindings.schema.json)校验。这是本地配置，不是官方 MCP 配置；支持 $store_id、$product_id、$product_name、$items、$address，数组支持 {"$map":"items","template":{"code":"$item.id","quantity":"$item.qty"}}。路径、单位和 success_path/success_value 必须来自实际响应，tool 必须与操作对应。自定义映射不自动获得内置 TOON/默认规格适配，需要独立验证。

## 约束与错误边界

Live 每槽位搜索原品和最多两个同类低参考价替代品，每个候选逐组官方核价，不声称全菜单最优。最多 6 份、枚举上限 100,000、不同核价组合上限 36，搜索总预算 100 秒。超时、超量、任一候选核价失败都停止，不返回部分搜索伪装的最优解。硬锁定/忌口/热量冲突可无解。

401/403 立即失败；429、连接异常、超时、502/503 最多重试一次。HTTP 超时 25 秒、单次会话 35 秒；不回显底层异常与凭据。空结果保留为空；结构漂移、缺 ID/名称、重复 SKU、业务失败或不可解析金额拒绝使用。本次未主动制造生产限流或 Token 失效，这些分支由 Mock 验证。

Live 不静默回退 Demo；失败后可明确切回 Demo，换模式/门店清空购物车与旧报价。Demo 为样例、official=false；Live 金额来自官方、official=true。报价指纹绑定模式/门店/餐单，120 秒失效。

[完整比赛规则](https://github.com/M-China/mcd-developer-innovation-challenge/blob/main/activityGuidelines.md)要求真实 MCP 和公开源码；本次已完成上述只读使用。未使用 WorkBuddy，不提供虚构上下文证明。上传和本人报名见 CONTEST_SUBMISSION.md。
