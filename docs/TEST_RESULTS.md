# 实测记录

日期：2026-10-24（北京时间）。全部结论针对本次本地版本，不代表线上或真实物理触屏验证。有效 Token 认证记录见 [真实联调报告](LIVE_INTEGRATION_REPORT.md)。

## 自动测试

| 检查 | 实际结果 |
|---|---|
| Python pytest | 109 项通过，0 失败 |
| 前端 Node 画板与基础状态测试 | 7 项通过，0 失败 |
| TypeScript 检查与 Vite 构建 | 通过 |
| pip check | No broken requirements found |
| Skill CLI repair | 成功返回原单 4800 分及三种方案 2900/2500/2900 分 |
| 参赛声明与官方原始字节对比 | 完全一致 |
| 发布包隔离解压（复用现有 Python 依赖） | 首页 200、13 项 Demo 菜单、三种修复 2900/2500/2900 分，来源标记正确 |

命令见 README。测试覆盖六类匹配、预算不足、软偏好和硬锁定、忌口无解、未知热量排除、整数金额/无效金额、图片大小/空白/格式、非法数量/商品/JSON 类型、同源限制、缺 Token 和禁止订单工具。

MCP 测试包括：官方 SDK ClientSession 与本地 FastMCP 的 Streamable HTTP initialize → tools/list → tools/call 往返；JSON Schema 校验；structuredContent 与文本 JSON 解析；业务错误；嵌套 HTTP 401/429/503 与超时分类；官方总额字段映射和字段漂移；优化器按 Mock 非线性优惠核价选择方案，任何候选核价失败都不能返回伪最优结果。**这些是 Mock，不是麦当劳认证服务。**

开发过程中发现并修复过 Vite/esbuild 配置加载的沙箱目录访问失败、Mock MCP 服务器 Host/端口校验导致的 421，以及浏览器已有文字选区引发原生拖拽、画笔中途 pointercancel 的问题。画板现阻止 pointerdown 默认行为并禁用画板选区，补充了连续路径和撤销回归测试；浏览器复测连续线条正常。最终结果以最后一次完整命令输出为准，没有把失败重试计为通过。

## 真实模型推理

本轮扩展验收：23 张预先定义线稿（18 张食物、4 张非食物、1 张空白），同一 PNG API 真实调用 CLIP.forward 22 次。食物 Top-1 17/18；4 张非食物均提示不确定；空白图 400。失败样本 coffee-cluttered.png 被识别为饮料 0.86705，咖啡 0.13066，且未触发不确定提示。未针对这组图调阈值。完整逐图记录见 [vision-audit.json](../artifacts/vision-audit.json)，测试图与清单见 examples/audit-sketches/。以下七图结果保留为先前开发检查，不能替代本轮结果。

模型：openai/clip-vit-base-patch32；默认 revision `3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268`。本机 CPU 推理；PyTorch 2.14.1+cpu、Transformers 4.57.6。六类加四个干扰文本，评分不是准确率。

| 作者样本 | Top-1 食物类 | 评分 | 需要确认 |
|---|---|---:|---|
| burger.png | 汉堡 | 0.99943 | 否（仍须人工确认后匹配） |
| fries.png | 薯条 | 0.95726 | 否 |
| icecream.png | 冰淇淋 | 0.99878 | 否 |
| drink.png | 饮料 | 0.99863 | 否 |
| nuggets.png | 鸡块 | 0.42931 | 是 |
| coffee.png | 咖啡 | 0.80977 | 否 |
| unknown.png（房屋） | 食物 Top-1 汉堡仅 0.00257 | 0.00257 | 是，干扰类更高 |

六张食物样本 Top-1 命中 6/6，只能说明这六张开发线稿可识别。它们不是独立随机数据集，不能宣称产品准确率 100%。原始 Top-3 和单次计时保存于 [vision-evaluation.json](../artifacts/vision-evaluation.json)。首次联网下载和加载曾用约 143 秒；缓存复测加载约 9 秒，后续该批样本每张约 0.1 秒；这些只是本机观测，非性能保证。

## 先前 Demo 浏览器检查（历史记录）

配置 Token 之前曾执行完整流程并保存 acceptance-workflow.png / acceptance-export.png；最终对话框中缺 Token 错误清楚可见，可切回 Demo。无匹配提示在独立空 Demo 菜单夹具中检查，acceptance-empty-menu.png 不代表真实官方门店。深色模式与帮助弹窗也已打开检查。导出改为 Blob 链接后，通过浏览器 downloadMedia 从同一下载链接实际取得下载目录文件，47,276 字节，与预览逐字节一致，副本见 acceptance-downloaded.png。早先点击下载事件未返回凭据的问题仍作为历史记录，不等同于当前 PNG 文件生成/下载失败。

实际使用本地网页 Canvas 拖动绘图，没有把预制图片灌入画板：

- 手画汉堡 → 真实模型 Top-1 汉堡，首次画作评分 0.929，修复连续拖拽后复画评分 0.986 → 确认后出现三个菜单候选 → 加入购物车。文字拖拽造成的断线图也曾触发低分不确定提示，未当作高分成功样本。
- 用黄色和红色画薯条 → 真实模型 Top-1 薯条 0.989 → 确认并加入购物车。真实导出保存在 examples/sketches/browser-fries.png。
- 橡皮擦使导出 PNG 改变；撤销后导出 PNG 与擦除前的 base64 字节完全相同。
- 空白画板提示、画笔颜色切换、清空、人工纠正、Demo 菜单与购物车均检查。
- 双层堡 + 大薯条 + 中杯饮料合计 ¥48；预算 ¥30，得到 A ¥29、B ¥25、C ¥29。采用 B 后购物车三项变更且重新报价 ¥25。
- 改数量后显示旧报价已失效；分享卡需新报价才能生成。
- 分享卡和画作显示真实 PNG 预览，下载链接带 download 文件名。初版 data URL 的 download 事件等待超时；本轮 Blob 链接通过 browser downloadMedia 实际落盘并与预览一致，文件产物已验证。未把早先事件超时隐去。
- 未配置 Token 时有明确提示，可切回 Demo 继续；Live 失败不自动混入样例金额。
- 390×844 移动模拟、桌面默认 948 像素宽均检查；文档 scrollWidth 不大于 viewport，无横向溢出。未在物理触屏设备上实测。

截图位于 docs/screenshots：desktop.png、repair.png、fries.png、mobile.png、share-preview.png；meal-share.png 是页面生成的分享卡。demo.gif 由真实截图按时间顺序合成，属于分步演示，不是连续录屏。

## 本轮真实 MCP

五个工具与三方案再次核价均通过；最后脚本原单 ¥48.50，预算 ¥47，三方案 ¥40/¥38/¥46.50。浏览器另用三件真实单品：原单 ¥47.50、预算 ¥40，三方案 ¥40/¥38/¥40，采用 B 后官方复核 ¥38，PNG 实际下载与预览一致。明确切回 Demo 清空餐单和报价，浏览器无 warning/error。完整边界见 [真实报告](LIVE_INTEGRATION_REPORT.md)。新增前端回归验证旧报价到期不会丢弃同一餐单的新请求。

## 尚未验证

有效 Token 下 tools/list 和五个工具、默认规格官方核价及三方案再次核价已于本次实测通过，见 LIVE_INTEGRATION_REPORT.md。此前匿名 403、缺 Token 提示属于历史验证。生产限流、Token 真实过期、配送、预约、优惠券、自定义加价规格与多门店覆盖未实测；故障处理由确定性 Mock 验证，不能写成生产故障已实测。

未做 GitHub 发布、报名、支付、下单、云端托管、跨用户鉴权、独立数据集准确率或负载测试。未使用 WorkBuddy，不生成其上下文证明。

官方原版 CONTEST_DECLARATION.md SHA-256：
`cd28101bcb29cc8fb24b372fe91ce6b42c4a1487a54e01f7ade0c8c6a84241b7`
