# McSketch 参赛交付验收

日期：2026-10-24（北京时间）。在现有项目上验证与修复，没有从零重建。

**结论：本地 Demo、真实 CLIP 和有效 Token 下五个只读 MCP 工具及预算修复再次核价均已验证。GitHub 发布与本人报名尚未执行。最新证据见 [真实联调报告](LIVE_INTEGRATION_REPORT.md)。**

## 1. 已实现与验证

真实 Canvas 输入 → PNG → CLIP Top-3 → 人工确认/纠正 → 类别匹配 → 加入购物车 → 预算约束搜索 → 三种方案 → 采用与重新报价 → PNG 分享预览。本轮浏览器重新手绘汉堡，Top-1 汉堡评分 0.987；Demo 48 元原单得到 29/25/29 元方案，采用 B 后重新核价 25 元。金额均标注样例，未作为官方价格。

购物车/约束变化使旧报价失效。预算、硬锁定、软偏好、忌口、热量、缺失营养和空匹配有自动测试。三种目标可以选中同一最优方案；不会为制造差异破坏硬约束。

无匹配状态另在 5176 端口的独立空 Demo 菜单夹具中通过浏览器实测，显示“当前门店没有匹配餐品，可换一种类别”；该截图是测试夹具，不是某个真实官方门店。夹具服务与标签页已关闭。

## 2. 真实 MCP

官方地址与认证格式已对照文档：Streamable HTTP、https://mcp.mcd.cn、Bearer 环境变量。五个工具名均可在官方 README 找到。使用官方 mcp 1.30.0 SDK；initialize/list_tools/call_tool 与本地 FastMCP 协议往返通过。本次已认证读取真实参数并根据返回字段完成内置适配，详见 LIVE_INTEGRATION_REPORT.md。

本次 .env 成功加载，值仅在后端使用。真实 tools/list 与五个允许工具调用成功，5 家门店、126 条菜单、160 行营养表。原单官方 ¥48.50，预算 ¥47，三方案重新核价 ¥40/¥38/¥46.50，authenticated_business_chain=true。此前 missing_token 为历史阻塞，已解除；未调用任何交易工具。

新增的确定性故障测试覆盖 401/403 不重试，429/503/超时最多重试一次，清理凭据信息；空列表保持为空，不回填 Demo。数据映射遇到空 ID、空名称、重复 ID、非数组、业务失败或错误的报价工具时拒绝使用数据。所有外部调用都经过五工具允许列表；未创建订单或支付。

## 3. 计算机视觉真实性与失败

固定原始模型 revision；推理调用的是 CLIPModel.forward。扩展脚本从 /api/recognize 传入真实 PNG，经过同一 read_png 和 CLIPProcessor 预处理，记录输入 SHA-256 与实际 forward 调用数。

23 张预先定义的测试图：六类各 simple/clean/cluttered 三档共 18 张食物图、4 张非食物图、1 张空白图。真实 forward 共 **22 次**；空白图在预处理阶段返回 400，没有模型调用。食物 Top-1 **17/18**；4 张非食物都提示不确定。

失败案例：coffee-cluttered.png 预测饮料 **0.86705**、咖啡 **0.13066**，且 uncertain=false。说明现有阈值不能可靠检测所有误判；页面仍要求用户确认所有候选。鸡块 clean/cluttered 虽 Top-1 正确，但提示不确定。没有通过删除失败样本或针对该样本调参“改善”结果。

这是作者生成的确定性线稿集，含同源变体，不是独立准确率基准。完整结果和每张输入见 artifacts/vision-audit.json、examples/audit-sketches/。此前 7 张简单样本的 6/6 只作历史开发检查。

## 4. 自动测试与修复

本轮完整执行：**pytest 109 项通过，0 失败；前端 7 项通过，0 失败；TypeScript 和 Vite 构建通过。**

修复内容：

- 忽略 .pnpm-store、各环境文件、本地 Live 映射、private 及私钥文件；防止误忽略公开 JSON schema。
- 发布文件从目录扫取改为显式审阅清单，额外加入目录的本地 JSON/资源不再自动入包。
- 前端按服务端 created_at + TTL 判定有效期，网络耗时不再给旧报价续命；后端拒绝最后一次核价结束时已超搜索期限的结果。
- 类别/门店异步请求增加顺序控制，过时返回不覆盖当前菜单；菜单加载中不允许基于旧目录选餐。
- MCP 弹窗内增加真实可见错误，避免 toast 位于对话框背后。
- 本地参数适配支持数组逐项映射，并校验业务成功条件，仍不虚构官方参数名。
- 导出下载链接使用 PNG Blob URL，预览仍展示生成的原图。

早先 data URL 的点击下载事件未取得凭据；改用 PNG Blob 链接后，通过浏览器 downloadMedia 对页面同一下载链接执行下载，已得到下载目录中的 mcsketch-meal.png，并逐字节确认与当前预览相同（47,276 字节）。副本见 acceptance-downloaded.png。下载文件已验证，但早先 click/waitForEvent 通知问题不等于被验证修复。物理触屏、GitHub CI 和公网部署仍未测试；有效 Token 到店取餐默认规格已实测。本轮浏览器尺寸覆盖未生效，未把 1280 像素截图标作新的 320 像素测试；此前 390 像素记录保留为历史实测。

## 5. 人工步骤

按照 [CONTEST_SUBMISSION.md](CONTEST_SUBMISSION.md)：当前真实联调已通过，接下来审阅脱敏结果 → 发布个人 Public 仓库 → 本人核实声明与资格 → 按官方格式提交报名 Issue。需要复测时使用内置真实响应适配和 verify_live.py。

## 6. GitHub 准备

要求的四个文件、源码、依赖、运行说明、Skill、真实截图、分步演示 GIF 均存在。官方声明保持原文；发布扫描与字节比对由 scripts/audit_release.py 重复执行，结果见 artifacts/release-audit.json。正式上传、实际 GitHub 仓库状态和报名成功通知仍需人工完成；当前并未初始化或推送仓库。

发布清单以 scripts/release-manifest.json 和 release-audit.json 最新数量为准；原 114 文件为历史快照，当前新增真实响应适配、回归测试和联调报告。此前，凭据签名扫描无发现，16 项 Git 忽略/公开保留检查符合预期。ZIP 已在临时隔离目录解压，使用现有 Python 依赖环境验证首页 200、13 项 Demo 菜单、三种修复金额 2900/2500/2900 分及 official=false。没有把这一项描述为在全新电脑完成依赖安装。

截图：docs/screenshots/acceptance-workflow.png、acceptance-export.png；acceptance-meal.png 是当前页面实际生成的分享卡。详细操作与限制同时保留于 TEST_RESULTS.md。

## 7. 报名内容

报名截止为北京时间 2026-10-25 23:59；报名正文的项目名称、项目地址、简介及可复制模板见 CONTEST_SUBMISSION.md。比赛要求真实使用 MCP，Demo 和 Mock 不能替代；以[官方完整规则](https://github.com/M-China/mcd-developer-innovation-challenge/blob/main/activityGuidelines.md)为准。
