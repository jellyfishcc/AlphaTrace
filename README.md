# TraceLab（盈迹）

财务变化驱动的上市公司业绩归因与证据验证智能体。仓库名保留 **AlphaTrace**，Python 包和本地工程目录为 `tracelab` / `TraceLab`；现有 `alphatrace-display-v1` 契约不改名。

以格力电器 2024—2025 年为真实案例，研究“净利润下降，经营活动现金流量净额增长”的方向分化。Python 提供确定性财务计算与来源核验；React 展示既有结果和真实 Agent 历史工具调用。**完整经营解释与自主调查闭环仍未通过真实端到端验收。**

## 交付同学先读（2026-10-18）

1. [初赛交付与演示交接](docs/delivery-2026-10-18.md)：准备哪些文件、如何启动、可展示什么、人工检查事项。
2. [视频演示操作与验收](docs/frontend-video-demo.md)：5 分钟路线、资料选择弹窗、真实与规划边界。
3. [开发进度](docs/progress.md)：按日期保留历史；最新条目置顶。
4. [前端运行说明](frontend/README.md)：安装、启动、构建、展示包缺失处理。

本次文档核对的代码 HEAD 为 `9e1ef76`。以下为当前状态，不以历史阶段文档中的旧页面名或旧测试数量替代。

## 当前能够真实展示的能力

| 能力 | 当前成果 | 限定范围 |
|---|---|---|
| 财务计算与核验 | Decimal 金额、两期变化、利润层级桥接、现金流直接法勾稽 | 保留空白与未闭合项；会计贡献不等于经营因果 |
| 真实数据展示 | 44 项财务记录、61 条可追溯年报来源 | 只展示已有白名单结果，不在浏览器重算金额 |
| PDF 结构化提取 | 格力指定合并利润表，5 指标 × 2 年共 10 条，历史实跑全部 matched | 原生文字 PDF；预设表格/科目/页码，无 OCR、无任意 PDF 通用解析 |
| 结构化研报纠错 | 构造陈述“增长35.0832亿元”被核查为方向错误，实际下降 | 单条结构化陈述；不是已发表研报，不支持任意全文理解 |
| 真实 Agent 工具调用 | 最新历史为 search → get → error，3 轮、2 次工具调用、3 次请求 | 最终仍为 validation_failed / incomplete_response，没有有效 explain 或合理 stop |
| 前端业务流程 | 开场 → 选择研究资料 → 载入已核验案例 → 业绩分析 → Agent 调查 → 核验报告与证据 | 离线结果回放；无在线上传分析、实时模型调用或审核写回 |

资料选择弹窗读取展示包中实际关联的文件名，目前只有 `格力2025年年度报告.pdf` 和已有两期结构化财务数据；**独立 2024 年报没有在展示包中关联**，不显示成已准备文件。点击载入会重新 fetch JSON 并校验，不会重新解析 PDF 或执行 Python。

开场直接使用后端同比：净利润 **-10.84%**、经营现金流 **57.93%**。净利润与归母净利润分别展示；金额、证据页码、桥接残差和 Agent 失败状态没有为演示改写。

## 启动当前演示

前端工具版本见 `frontend/.mise.toml`：Node.js 22、pnpm 10.34.3。已有依赖时可跳过安装；已有 8443 服务时直接访问，不要重复启动。

```powershell
cd D:\Projects\TraceLab\frontend
pnpm install --frozen-lockfile
pnpm dev
```

访问 <http://localhost:8443/>，点击“选择研究资料”，选中格力案例，再点“载入已核验案例”。关闭按钮、Esc 或“返回介绍页”可退出弹窗；左侧品牌可返回开场。三个主导航保持不变。

**新克隆不会带真实展示包。** `frontend/public/data/` 和 `outputs/` 均被 Git 忽略。需要通过获准的交接渠道准备已有白名单 `gree-display.json`，或在具备完整本地资料的机器执行导出。不要把原始 PDF、内部附件、完整模型日志复制到 public。完整导出命令及资料依赖见[交付清单](docs/delivery-2026-10-18.md)。缺失或校验失败会阻止真实案例载入；模拟案例必须显式选择。

前端不需要 Python Web 服务或 API Key。浏览器结构校验不等于重新认证原始 PDF，也不是数字签名；展示包应来自可信导出流程。

## 验证记录与命令

| 范围 | 最近已有实际记录 | 说明 |
|---|---|---|
| 前端 | 32 通过、0 失败、0 跳过；typecheck/build 通过 | 资料选择交互完成后的验收，见视频文档 |
| Python | 222 通过、0 失败、0 跳过 | 第二轮结果集成时的全量记录，见[集成验收](docs/frontend-results-integration.md)；后续前端及本次文档更新未重跑 Python |
| 浏览器 | 三页流程、资料选择载入/关闭、来源返回、模拟隔离通过 | 实测 1280×720；1920×1080 仍需录屏机器复查 |

```powershell
# frontend 目录，另开终端执行，pnpm dev 会持续占用当前终端
pnpm typecheck
pnpm test
pnpm build
```

以下 Python 命令从仓库根目录执行。Python 3.10+，真实 PDF 功能需要 requirements 中的依赖。无原始资料也可执行公开模拟示例；模拟结果不是格力实测成果。

```powershell
python -m pip install -r requirements.txt
python -X utf8 -m tracelab --input examples/simulated/financial.csv --metadata examples/simulated/metadata.json
python -X utf8 -m tracelab.report_check --simulated-demo
python -X utf8 -m unittest discover -s tests -v
```

真实资料集成测试依赖本地快照；缺少资料的跳过不能写成真实案例通过。历史源码隔离验收的通过数和跳过口径见[10 月 17 日记录](docs/delivery-2026-10-17.md)，不是当前代码的干净环境全量验收。

具备原始 PDF 与完整修订快照时，可重复运行已有离线功能（不调用模型、不覆盖历史结果）：

```powershell
python -X utf8 -m tracelab.pdf_extract --stage2-run outputs/final_revision/20261017T093152-d80de1cefa
python -X utf8 -m tracelab.report_check --stage2-run outputs/final_revision/20261017T093152-d80de1cefa --claim examples/report_check/gree_direction_error.json
python -X utf8 -m tracelab.agent --stage2-run outputs/final_revision/20261017T093152-d80de1cefa --final-evidence
```

最后一条是本地 Mock 调查，不是真实模型。详见 [PDF 说明](docs/pdf-extraction.md)、[纠错说明](examples/report_check/README.md)、[Mock 调查说明](docs/agent-local-mock.md)。

## Agent 当前状态与历史证据

- 首次真实调查：四次 fact_get 后重复查询被阻断，没有进入 search/get，最终失败。[保留原记录](docs/stage4b2b-live-result.md)。
- 随后完成事实上下文、重复查询及证据预算修复；Replay 的 explain / insufficient 两条路径通过离线检查，不能当作真实模型成功。[修复与保留待办](docs/agent-pending.md)。
- 修复后经另一次明确授权的真实调查：search 返回 E07_28、F_net_profit；get 读取 F_operating_cashflow；第三轮响应截断，最终 validation_failed / incomplete_response。[最新真实验收](docs/agent-live-acceptance-20261017T151343.md)。

第四阶段未全部完成，Agent 仍是核心目标。前端虚线“经营解释生成与证据校验”是尚未完成的产品能力，不是已执行成功的第三步。任何新的真实 API 调用都需要独立授权；交付和录屏不需要重新运行调查，也不能复用旧授权。

## 工程文档与提交边界

- 计算与输入：[第一阶段](docs/stage1.md)、[第二阶段](docs/stage2.md)、[CSV 模板](templates/financial.csv)、[元数据模板](templates/metadata.json)。
- 来源修订：[最终资料交接（历史）](docs/final-materials-handoff.md)、[修订版预检](docs/stage4b2b.md)。当前修订版原 9 项冲突已解决，历史差异不当作当前未解决问题。
- 模型与调查：[第三阶段](docs/stage3.md)、[B-1](docs/stage4b1.md)、[B-2A](docs/stage4b2a.md)。这些编号沿用既有项目记录，没有新增阶段。
- 前后端数据契约：[首次集成（历史）](docs/frontend-offline-integration.md)、[结果集成](docs/frontend-results-integration.md)、[当前视频操作](docs/frontend-video-demo.md)。

API Key、原始财报、内部附件、完整请求响应、历史运行目录不纳入源码提交。dist 构建会携带 public 中的白名单 JSON，发布前需人工确认公开范围；本项目当前没有自动部署或在线分析服务。不得把金额一致性核验表述为独立审计，不得仅凭现金流增长判断盈利质量改善或经营因果成立。
