# 正式参赛前的人工步骤

核对日期：2026-10-24（北京时间）。目前 **Live 认证业务验收已完成**，结果见 LIVE_INTEGRATION_REPORT.md；GitHub 发布和本人报名尚未执行。

## 1. 复现真实 MCP 验收

1. 在项目根目录执行 `Copy-Item .env.example .env`（仅首次；已有 .env 时不要覆盖），在本机编辑 `.env` 填写 `MCD_MCP_TOKEN`。Token 从[官方开放平台](https://open.mcd.cn/mcp)申请；不必发送到聊天或提交仓库。系统进程环境变量优先于 .env；修改后重启服务。
2. 运行 `python scripts/verify_live.py --schema-output private/mcp-schemas.json`，读取官方实际工具 schema。此时仅验证协议/schema，不会宣称业务链路通过。无 Token 会输出 blocked 并非零退出。
3. 默认使用本次真实响应验证的内置适配，不需要建立 live-bindings.json。仅当官方结构变化或使用自定义场景时，按 MCP_INTEGRATION.md 重新核对映射。原始响应仅保留在已忽略的 private/，发布记录不含定位和账号信息。
4. 在 private/live-acceptance.json 填写以下**McSketch 内部验收输入**，这些不是官方工具参数：

```json
{
  "address": "城市 位置关键词（空格分隔）",
  "category": "burger",
  "items": [{"id": "实际门店菜单返回的商品ID", "qty": 1}],
  "budget_cents": 3000,
  "locked_ids": [],
  "favorite_ids": [],
  "avoid": [],
  "max_kcal": null
}
```

5. 运行 `python scripts/verify_live.py --requests private/live-acceptance.json`。脚本依次验证门店、菜单、匹配、详情与营养、官方核价、优化及三种方案再次核价。营养缺失、没有方案或重新核价改变时，不会输出完整 passed。所有调用限于五个查询/核价工具，无下单、支付或权益领取。
6. 检查 artifacts/mcp-live-audit.json；只有 authenticated_business_chain=true 才表示该次认证业务链路完成。报告仅存阶段、数量、金额和状态，不含地址、Token、原始商品或账号响应。正式发布前再次核实报告是否适合公开。

## 2. 检查并发布 GitHub

当前目录未初始化 Git、未建立远程仓库，也没有执行上传或报名。建议使用名为 mcsketch 的个人 **Public** 仓库。

先执行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
cd frontend
pnpm test
pnpm build
cd ..
.\.venv\Scripts\python.exe -X utf8 scripts/audit_vision.py
.\.venv\Scripts\python.exe -X utf8 scripts/audit_release.py
.\.venv\Scripts\python.exe -X utf8 scripts/package_release.py
```

解压 artifacts/mcsketch.zip 后，以其中 mcsketch/ 内的文件作为仓库根目录，避免把上层目录一起上传。也可从当前源码目录按 .gitignore 提交；`git add` 后必须查看暂存文件清单。打包脚本只包含 scripts/release-manifest.json 审阅清单和构建入口引用的资源，新增交付文件需先加入清单。

应保留 README.md、CONTEST_DECLARATION.md、MCP_INTEGRATION.md、mcp-config.example.json、源码、依赖、运行与测试说明。声明已按官方原版字节比较，勿用编辑器自动改换行或正文。不要上传 .env*（.env.example 除外）、private/、live-bindings*.json、模型缓存、.venv、node_modules、.pnpm-store、日志、原始 MCP 数据。依赖签名扫描不等于能识别一切秘密，仍需查看最终文件清单。

未使用 WorkBuddy，不提供或声称存在 workbuddy.md，不申请需该证明的专项条件。

## 3. 报名

按[完整活动规则](https://github.com/M-China/mcd-developer-innovation-challenge/blob/main/activityGuidelines.md)，报名截止为北京时间 **2026-10-25 23:59**；仓库应保持公开，且项目须真实使用麦当劳 MCP。仓库创建时间须在规则规定区间内。参赛者本人核实资格、原创权利及声明。

进入[官方比赛仓库](https://github.com/M-China/mcd-developer-innovation-challenge)的 Issues，使用指定报名模板（如页面提供）或 README 标准格式。标题可填写：

```text
【参赛申请】McSketch —— 麦麦画餐师
```

本次真实 MCP 认证验收已完成，可使用下面简介；替换账号和真实地址，字段名与内容保持在同一行，项目地址使用普通 URL，不使用 Markdown 链接：

```text
【参赛申请】
项目名称：McSketch —— 麦麦画餐师
项目地址：https://github.com/你的GitHub账号/mcsketch
项目简介：画出你想吃的，AI 帮你找到它。项目通过真实 CLIP 推理识别手绘食物，结合麦当劳官方 MCP 查询门店菜单与营养数据，在预算、锁定和保留偏好约束下生成三种经官方核价的餐单修复方案（未知过敏原和营养不会视为满足硬约束）；同时提供明确标识的 Demo 体验与可复用 Skill。
```

提交后查看官方机器人是否回复成功；仅创建 Issue 不代表通过。失败时按官方反馈修正再报名。不要通过不正当方式操作 Star 或榜单。本文未代替参赛者提交 Issue、同意协议或保证资格通过。
