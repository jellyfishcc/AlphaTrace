# 前端首次离线数据集成

> 历史记录：本文描述首次离线集成，当时的页面名称、未连接功能及测试数量仅对应该次验收。后续已接入 PDF/纠错/桥接/冲突，并完成独立开场和资料选择交互。当前操作与交付以[10月18日交接清单](delivery-2026-10-18.md)及[视频说明](frontend-video-demo.md)为准。

2026-10-18。保留队友提供的 React + TypeScript + Vite 页面和主要交互；没有新 API 服务，没有运行 Qwen，没有修改会计引擎、来源规则或 Agent。

## 实际输入与数据流

本轮开始 HEAD 为 `ce2a6f5`，已有后端修改均已在该提交中；`frontend/` 是用户提供的未跟踪目录。已读取 frontend/AGENTS.md、CLAUDE.md、types、adapter、example、App 与 Vite 配置。原适配器仅加载元信息，金额、证据和轨迹均为空；页面另有写死的示例金额、模拟标记和冲突统计。本轮修正了真实案例分支，示例保留且明确标识。

真实财务快照：`outputs/final_revision/20261017T093152-d80de1cefa`。
真实调查：`outputs/agent_live/20261017T151343-d0d3b954f5`。

离线流程：

1. `final_release.load_agent_payload` 重新验证财务快照、PDF 与来源绑定；`LocalFacts` 限定可用事实。
2. `display_export` 从 metrics/cash_metrics 取原始字符串，与可信事实用 Decimal 比较，保留已有同比字符串，不重新计算。
3. 重新核对历史 result/manifest/input/events/source_audit 文件哈希，以及调查所用财务快照、输入事实、返回证据与最终事件对应关系。
4. 只投影允许展示的财务字段、公开年报摘录和工具行动摘要，导出 `alphatrace-display-v1`。完整请求、响应片段、配置、授权信息、附件、内部底稿、路径不导出；危险文本检查失败则拒绝输出，不静默修改财务原文。
5. React 只 fetch `public/data/gree-display.json`，由既有 adapter 入口校验结构再映射为 CaseRecord。金额字符串直接渲染，不经过 JavaScript Number。缺失保持未提供。

实际导出 30 项 metrics 记录、14 项现金流分项，共 44 项；61 条公开来源证据。仅导出既有可信事实与金额输出的交集，不声称覆盖全部事实。`operating_cashflow` 保持 metrics.json 的原始分组，现金流分项在“经营现金流”页签展示。

真实调查显示 search（E07_28、F_net_profit）、get（F_operating_cashflow）、第三轮 error（incomplete_response）；3 轮、2 次工具调用、3 次真实请求。最终仍是 validation_failed。第三轮不是有效 explain 或 stop，不展示截断候选解释，也不把来源核验通过包装成 Agent 通过。

## 运行

本机已放置 `frontend/public/data/gree-display.json`。保持现有 `pnpm dev`，打开 http://localhost:8443/；不必启动 Python 服务。

重新生成时，从仓库根目录执行（Python 环境需安装 requirements.txt）：

```powershell
$displayRun = Get-Date -Format 'yyyyMMddTHHmmssfff'
$displayFile = "outputs/frontend_display/$displayRun/gree-display.json"
python -X utf8 -m tracelab.display_export --stage2-run outputs/final_revision/20261017T093152-d80de1cefa --agent-run outputs/agent_live/20261017T151343-d0d3b954f5 --output $displayFile
if ($LASTEXITCODE -eq 0) {
  New-Item -ItemType Directory -Force frontend/public/data | Out-Null
  Copy-Item -LiteralPath $displayFile -Destination frontend/public/data/gree-display.json
}
```

导出器拒绝覆盖已有目标文件；每次导出保留独立文件，前端 public 路径仅为当前展示副本。没有快照或校验失败则不输出真实包，也不会转换为模拟金额。页面自动加载失败会明确提示，剩余示例保留“非真实运行”标签。导入按钮仅接受单个 `*-display.json`；不要选择原始日志或附件。前端结构检查不是来源认证或数字签名，应仅加载本机导出器产生的可信包。

```powershell
cd frontend
pnpm dev
pnpm typecheck
pnpm test
pnpm build
```

本机测试使用随 Codex 提供的 Python 3.12.14，系统 Python 如缺 pypdf 需先安装既有依赖。受限沙箱执行 pnpm 时曾出现 node_modules realpath EPERM；使用正常本机权限后类型检查与构建均通过，没有改依赖版本或关闭类型检查。

## 浏览器验收

1. 默认选择格力真实调查，核对“真实模型历史记录”和 validation_failed。
2. “财务拆解”查看基期、本期、变化额；右栏查看原始元金额。经营现金流分项切换对应页签。
3. “原因与证据”选择 F_net_profit：印刷 87 / PDF 88，原文包含 28,862,746,016.16 和 32,371,069,287.35。目录证据可独立查看，不意味着 Agent 已读取全部 61 条。
4. “查看调查轨迹”展开 search/get/error，确认 incomplete_response、3/2/3 用量。
5. 切换 RUN-DEMO-042，显示华岭电器（示例），证据与解释同步切换；切回真实案例后没有示例解释与冲突内容。
6. “核验与交付”明确列出 Agent 失败；冲突详情未接入，不虚构检查数量。

验证结果保存在 `outputs/frontend_integration/`：Python 定向 11 通过，前端适配测试 9 通过（均 0 失败、0 跳过）；Python 全量 215 通过、0 失败、0 跳过。真实数据集成测试逐项核对 44 项金额与 61 条原文和页码；浏览器 DOM 额外读取 132 个金额单元格，与导出字符串逐字一致，无差异。已实际检查真实/模拟切换、证据选择与失败轨迹。

## 安全与未连接功能

`public/data/`、dist、node_modules、outputs 均忽略，不自动提交。Vite 只允许 frontend 文件范围，默认绑定 127.0.0.1；验证展示包 HTTP 200，越界访问后端快照 HTTP 403。原始 PDF/Excel/Word 和完整模型日志不进入浏览器。构建产物会包含允许展示的 JSON；后续如发布 dist 仍应人工审查实际公开范围。

本轮未接入桥接影响/残差树、冲突明细、PDF 提取专页、在线调查、审核写回、PDF/Word 导出或数据库。模型闭环仍未通过。展示包目前明确限定已审计、最终失败的真实 Qwen 记录；其他终态或其他旧版日志格式会拒绝加载，不推测兼容。未启动任何新的模型调查，没有自动 commit/push。
