# TraceLab（盈迹）前端

React 19 + TypeScript + Vite 的离线结果展示。Python真实结果 → 白名单 JSON → 适配器校验 → 页面渲染。无需 Python Web 服务、API Key 或真实模型请求。

交付同学先读[当前交接清单](../docs/delivery-2026-10-18.md)，完整产品能力见[根 README](../README.md)。历史包名 `figma-make-app`、仓库 AlphaTrace 和 `alphatrace-display-v1` 保持兼容，不是页面对外品牌。

## 启动与检查

工具版本见 `.mise.toml`：Node.js 22、pnpm 10.34.3。在本目录执行：

```powershell
pnpm install --frozen-lockfile
pnpm dev
```

访问 <http://localhost:8443/>。已有开发服务时直接复用，不重复启动。另开终端运行检查：

```powershell
pnpm typecheck
pnpm test
pnpm build
```

最近实测：32项测试通过、0失败、0跳过，类型检查与生产构建通过（2026-10-18资料选择任务）。本文档更新未重跑这些命令。浏览器实测1280×720；录屏1920×1080需本机复查。

## 演示数据准备

必须有可信导出器生成的 `public/data/gree-display.json`。它被 Git 忽略，干净克隆需单独准备或在具备原始材料的机器重新导出，完整命令见[交接清单](../docs/delivery-2026-10-18.md)。仅把白名单包放入 public，不要复制 outputs、原始PDF或内部附件。

当前包有44项财务记录、61条来源、3条真实Agent动作摘要，以及PDF、纠错、桥接和冲突可选模块。金额直接保留后端字符串；未经检索的来源不会伪装成Agent读取记录。结构校验不是来源数字签名。

展示包缺失或不合规时，真实案例不可载入；可以明确选择交互模拟案例，不能将其用作格力真实成果。旧包缺少 modules 时显示缺失，不从模拟案例补值。

## 点击路线

开场 → **选择研究资料** → 选中格力2024—2025案例 → **载入已核验案例** → 业绩分析 → Agent调查 → 核验报告与证据。

- 点击载入会重新 fetch JSON（no-store），校验结构、案例/运行/资料版本和来源文件关联。失败留在弹窗显示提示。
- 弹窗支持关闭按钮、Esc、返回介绍页；关闭后迟到请求不会触发跳转。
- 资料文件名来自包内 evidence，当前只有 `格力2025年年度报告.pdf`；独立2024年报未在包中关联。不上传或读取原始PDF。
- 左侧品牌返回开场，主导航仍只有三个页面。PDF提取与结构化纠错从业绩分析的辅助区进入。
- 真实历史为search/get/error，最终validation_failed / incomplete_response保留在审计详情；虚线经营解释区域为未完成规划。

详细讲解路线见[视频演示文档](../docs/frontend-video-demo.md)。

## 维护入口

| 文件 | 用途 |
|---|---|
| src/App.tsx | 案例上下文、页面导航、展示包载入 |
| src/IntroPage.tsx、ResearchMaterialsDialog.tsx | 开场及资料选择弹窗 |
| src/ResearchTask.tsx、FinancialHighlights.tsx | 财务摘要、会计贡献 |
| src/AgentInvestigation.tsx、AnalysisReport.tsx | 历史调查及阶段性报告 |
| src/OfflineResults.tsx | PDF、纠错、桥接、核验摘要 |
| src/data/adapter.ts、workflow.ts | 白名单契约校验、导航与案例绑定 |
| src/index.css | 既有品牌、布局和弹窗样式 |
| tests/ | 适配器、组件和业务路线离线测试 |

不通过页面调用Qwen，不新增在线解析进度，不修改后端金额或失败状态。`dist/` 会复制 public 中的展示包；构建通过不等于公开发布获准，交付/部署前仍需确认文件范围。
