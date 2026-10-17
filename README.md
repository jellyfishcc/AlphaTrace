# AlphaTrace（项目目录 TraceLab）

面向上市公司净利润变化归因的财务调查项目。Python 负责确定性计算与核验，模型负责阅读披露、提出解释和调查问题，金融组负责复核经营因果。

当前主案例为格力 2024—2025 年，调查“净利润下降、经营活动现金流量净额增长”的走势分化。利润分析依次区分营业利润、利润总额、净利润、少数股东损益与归母净利润。

## 当前进度（2026-10-17）

- 已完成结构化输入、Decimal 计算、利润层级核验和现金流直接法分项核对。
- 已接入百炼北京 `qwen-plus`，实现完整和聚焦两种分析模式、单次调用日志及严格输出检查。最近一次独立真实分析仍为 `validation_failed`，不能把接口连通视为分析验收通过。
- 已实现第四阶段 A：有轮数和工具上限的本地模拟调查，支持证据列表、检索和原文读取。决策仍是预设 Mock，尚未验证真实模型自主调查。
- 已接收金融组最终版资料：31 项指标中 29 项一致、2 项修正旧输入尾差；已列示有金额项目的营业利润桥接、成本八项、利润层级衔接和现金流三项勾稽复算闭合。
- 新增 14 段可追溯年报证据；两项年度列冲突、两项 Word 展示差异和五处来源定位差异已在修订版核验解决，历史记录保留。空白仍不填零。
- 已完成第四阶段 B-1：按原始年报来源核验证据，新增只读财务事实查询；修订版验收后45个事实可查询，缺失项目继续隔离。
- 已完成第四阶段 B-2A：Qwen 决策适配、外发白名单、逐轮预算及失败保护，使用假传输验证；尚未运行真实模型端到端调查。
- 已完成修订版增量验收与第四阶段 B-2B 预检：原9条附件冲突已解决，真实调查仍待单独授权。
- 本地全部 **153 项测试通过，0 跳过**，模拟调查结果为待人工复核。原始资料需要人工整理，各阶段仍由命令启动；没有前端，也不是全自动系统。

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
| 第四阶段 B-2B | 修订资料验收及真实调查预检，未真实调用 | [增量验收与预检](docs/stage4b2b.md) |
| 后续真实端到端调查 | 尚未执行，需单独授权 | 以 B-2A 的范围和预算为起点 |

[开发进度](docs/progress.md)保留历史记录，以最新条目为准。提示词版本 V3 是第三阶段内部的版本号，不是新的项目阶段。

## 本地运行与验证

第一阶段仅依赖 Python 标准库；年报读取及后续核验需要 [requirements-stage2.txt](requirements-stage2.txt) 中的依赖。使用 Python 3.10+，从仓库根目录运行：

```powershell
python -m pip install -r requirements-stage2.txt
python -X utf8 -m tracelab --input examples/simulated/financial.csv --metadata examples/simulated/metadata.json
python -X utf8 -m unittest discover -s tests -v
```

模拟输入不代表真实财务验收。金融组输入模板为 [CSV 模板](templates/financial.csv)和[元数据模板](templates/metadata.json)。每次运行生成独立目录，不覆盖历史结果。

在当前开发机器上，最终版快照的离线模拟调查可运行：

```powershell
python -X utf8 -m tracelab.agent --stage2-run outputs/final_release/20261017T001129-fb6ba35805 --final-evidence
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

下一步是在单独授权后验证真实端到端调查，适配器已完成离线测试。金融组仍需复核经营解释是否超出原文支持范围。原始元计算、空白处理、同比边界和已确认利润层级规则不再重复作为待确认项。

模型不得修改 Python 已确认金额，不得把本期受限资金调节额当作现金流同比贡献，也不得仅凭现金流增长推断盈利质量改善。新的真实 API 调用须单独明确范围与授权。

API 密钥仅保存在本地环境变量，不提交到版本库。原始财报、金融组内部附件、完整运行记录及生成结果默认不纳入 Git；仓库中的脱敏失败样本仅用于离线回归测试。
