# AlphaTrace（项目目录 TraceLab）

面向上市公司净利润变化归因的财务调查项目。Python 负责确定性计算与核验，模型负责阅读披露、提出解释和调查问题，金融组负责复核经营因果。

当前主案例为格力 2024—2025 年，调查“净利润下降、经营活动现金流量净额增长”的走势分化。利润分析依次区分营业利润、利润总额、净利润、少数股东损益与归母净利润。

## 当前进度（2026-10-17）

- 已完成结构化输入、Decimal 计算、利润层级核验和现金流直接法分项核对。
- 已接入百炼北京 `qwen-plus`，实现完整和聚焦两种分析模式、单次调用日志及严格输出检查。最近一次独立真实分析仍为 `validation_failed`，不能把接口连通视为分析验收通过。
- 已实现第四阶段 A：有轮数和工具上限的本地模拟调查，支持证据列表、检索和原文读取。此入口决策是预设 Mock；真实 Qwen 入口另见 B-2B。
- 已接收金融组最终版资料：31 项指标中 29 项一致、2 项修正旧输入尾差；已列示有金额项目的营业利润桥接、成本八项、利润层级衔接和现金流三项勾稽复算闭合。
- 新增 14 段可追溯年报证据；两项年度列冲突、两项 Word 展示差异和五处来源定位差异已在修订版核验解决，历史记录保留。空白仍不填零。
- 已完成第四阶段 B-1：按原始年报来源核验证据，新增只读财务事实查询；修订版验收后45个事实可查询，缺失项目继续隔离。
- 已完成第四阶段 B-2A：Qwen 决策适配、外发白名单、逐轮预算及失败保护，已通过假传输验证，另已进行一次真实模型调查，未通过端到端验收。
- 已完成修订版增量验收与第四阶段 B-2B 预检：原9条附件冲突已解决。随后一次真实调查已运行：5 次 HTTP 200、4 次工具调用，第五次重复查询被拒绝，结果 validation_failed；未检索证据、未提交 explain。见[真实记录](docs/stage4b2b-live-result.md)。
- 2026-10-17 最新 Agent 修改后完整测试 **183 项通过，0 失败，0 跳过**，模拟调查结果为待人工复核。原始资料需要人工整理，各阶段仍由命令启动；没有前端，也不是全自动系统。

## 按阶段阅读

| 阶段 | 内容与当前状态 | 文档 |
|---|---|---|
| 第一阶段 | CSV 输入、校验与两期变化计算，已完成 | [输入与基础计算](docs/stage1.md) |
| 第二阶段 | 真实财务数据、会计关系和来源核对，已实现 | [财务计算与核验](docs/stage2.md) |
| 第三阶段 | 模型证据分析，已接入但真实输出尚未通过验收 | [运行说明](docs/stage3.md) · [真实测试与交接](docs/stage3-test-handoff.md) |
| 第四阶段 A | 本地证据工具与模拟调查，已完成离线验证 | [模拟调查说明](docs/agent-local-mock.md) |
| 第四阶段 B 前置工作 | 最终资料核验与证据扩充，已完成；部分附件差异保留 | [最终资料与下一阶段交接](docs/final-materials-handoff.md) |
| 第四阶段 B-1 | 事实与证据接口升级，已完成离线验证 | [接口与测试交接](docs/stage4b1.md) |
| 第四阶段 B-2A | Qwen 决策适配，已完成离线验证 | [适配器与离线测试](docs/stage4b2a.md) |
| 第四阶段 B-2B | 修订资料验收、预检及一次真实调查；端到端验收失败 | [预检](docs/stage4b2b.md) · [真实失败记录](docs/stage4b2b-live-result.md) |
| 完整自主调查闭环 | 尚未通过；本轮暂缓优化，仍是核心目标 | [保留待办](docs/agent-pending.md) |
| 最小研报纠错 | 单条结构化陈述、离线确定性核查已实现 | [初赛交付说明](docs/delivery-2026-10-17.md) |

[开发进度](docs/progress.md)保留历史记录，以最新条目为准。提示词版本 V3 是第三阶段内部的版本号，不是新的项目阶段。

## 本地运行与验证

2026-10-18 前端离线集成：已有 `frontend/` React 页面通过白名单 JSON 展示真实财务金额、公开来源证据和历史 Agent 失败轨迹。运行 `cd frontend; pnpm dev` 后访问 `http://localhost:8443/`。需要先在本机生成展示包，完整命令与缺失状态说明见[前端离线数据集成](docs/frontend-offline-integration.md)。不启动 Python Web 服务，不调用模型；页面保留真实 `validation_failed`，示例与真实数据隔离。

2026-10-18 补充：第一模块已有受限的原生文字 PDF 合并利润表提取入口。实际从格力 2025 年报 PDF 第 88 页（印刷第 87 页）读取五个科目的两年金额，输出精确 JSON/CSV 与独立来源核验结果。金额不从旧底稿复制；不使用 LLM/OCR，不代表任意 PDF 通用解析。见[PDF 提取运行与边界](docs/pdf-extraction.md)。

```powershell
python -X utf8 -m tracelab.pdf_extract --stage2-run outputs/final_revision/20261017T093152-d80de1cefa
```

运行需要本地原始 PDF 和完整已验证快照；新克隆不含私有附件。输出到独立 `outputs/pdf_extract/<run_id>/`，不会覆盖快照或自动接入可信事实。无私有附件时仍可运行公开合成测试：`python -X utf8 -m unittest discover -s tests -p test_pdf_extract.py -v`（真实资料集成测试会明确跳过）。

第一阶段仅依赖 Python 标准库；年报读取及后续核验需要 [requirements-stage2.txt](requirements-stage2.txt) 中的依赖。使用 Python 3.10+，从仓库根目录运行：

```powershell
python -m pip install -r requirements.txt
python -X utf8 -m tracelab --input examples/simulated/financial.csv --metadata examples/simulated/metadata.json
python -X utf8 -m unittest discover -s tests -v
```

模拟输入不代表真实财务验收。金融组输入模板为 [CSV 模板](templates/financial.csv)和[元数据模板](templates/metadata.json)。每次运行生成独立目录，不覆盖历史结果。

在当前开发机器上，最终版快照的离线模拟调查可运行：

```powershell
python -X utf8 -m tracelab.agent --stage2-run outputs/final_revision/20261017T093152-d80de1cefa --final-evidence
```

此命令只运行本地 Mock，不发送 API 请求。新克隆不包含上述私有运行快照，需先按[最终版交接说明](docs/final-materials-handoff.md)接收本地附件；缺少快照时相关集成测试会明确跳过，不能据此声称真实资料核验通过。开发机器运行环境及临时目录权限处理也见该说明。

## 没有界面时，如何检查成果

| 要检查什么 | 查看位置 |
|---|---|
| 新旧金额是否一致 | `outputs/final_release/<运行编号>/comparison.csv` |
| 利润与现金流是否闭合 | 同目录 `bridges.json`、`cash_bridges.json` |
| 还存在哪些资料差异 | 同目录 `conflicts.json`、`pending_questions.md` |
| 新证据原文与页码 | 同目录 `verified_evidence.json` |
| 模拟调查执行了哪些行动 | `outputs/agent/<运行编号>/events.jsonl` |
| 调查状态及人工复核事项 | 同目录 `result.json`、`manifest.json` |
| 真实模型为何失败 | [第三阶段真实测试交接](docs/stage3-test-handoff.md)及其引用的本地运行目录 |

通用操作见[自查说明](docs/self-check.md)，最新快照和测试日志位置见[最终版交接说明](docs/final-materials-handoff.md)。`pending_human_review` 只代表基础检查通过，不能等同于经营因果得到证明。

## 下一步与边界

当前优先交付与验收，Agent 暂缓优化而非取消；第四阶段未全部完成。一次真实调查已失败，后续仍需完成自主调查与严格解释核验闭环。金融组仍需复核经营解释是否超出原文支持范围。原始元计算、空白处理、同比边界和已确认利润层级规则不再重复作为待确认项。

模型不得修改 Python 已确认金额，不得把本期受限资金调节额当作现金流同比贡献，也不得仅凭现金流增长推断盈利质量改善。新的真实 API 调用须单独明确范围与授权。

API 密钥仅保存在本地环境变量，不提交到版本库。原始财报、金融组内部附件、完整运行记录及生成结果默认不纳入 Git；仓库中的脱敏失败样本仅用于离线回归测试。

## 初赛复现与单条研报核查

新克隆可离线执行公开模拟示例（不代表真实财务结果，不调用 LLM）：

```powershell
python -X utf8 -m tracelab.report_check --simulated-demo
```

本机已有私有修订快照时，可运行格力方向错误示例：

```powershell
python -X utf8 -m tracelab.report_check --stage2-run outputs/final_revision/20261017T093152-d80de1cefa --claim examples/report_check/gree_direction_error.json
```

输出 `result.json` 和 `report.md`，本例为 `发现错误 / 方向错误`。示例陈述是人为构造的错误句，不是实际研报摘录。真实金额在运行时重新从通过来源核验的快照读取。来源不完整则输出“无法核实”，不会降级为模拟。只核查结构化字段，原文转写一致性仍需人工检查；不支持任意全文或自动因果判断。

上一轮初赛交付源码包的隔离测试实际通过146项（不含本轮新增Agent测试），失败0项；unittest报告5个跳过事件（4个测试类、1个测试方法，共27项依赖本地资料的方法未执行）。不能宣传为全量真实案例通过。完整的环境说明、缺失资料、测试记录及提交边界见[10月17日交付检查](docs/delivery-2026-10-17.md)。

第四阶段 Agent 最新离线进展：已补齐事实状态标识、证据预算保护及 search→get→explain/stop 两条Replay路径；真实自主调查仍未通过验收，见[定位与离线记录](docs/agent-pending.md)。
