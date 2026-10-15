# 第二阶段 格力真实案例接入与核对

复用 `stage1.run` 的 CSV 校验、Decimal 差额、输入快照和日志。
新增 `source_io.py` 读取 OOXML 原始值，`accounting.py` 执行明确会计公式，
`stage2.py` 作为本次附件格式的适配与核对入口。不是通用财报解析器。
第一阶段命令和原有测试保持兼容；无前端、联网获取、RAG 或 LLM 调用。

## 运行

第一阶段仍无第三方依赖；第二阶段 PDF 读取需 `pypdf==6.10.0`。
本次实际使用已内置 pypdf 的 Python 3.12.14；软件测试使用本机 Python 3.14.6。
普通环境可在自己的虚拟环境安装：

```powershell
python -m pip install -r requirements-stage2.txt
python -X utf8 -m tracelab.stage2 --source-dir "存放六个原始附件的目录"
python -X utf8 -m unittest discover -s tests -v
```

本机无需再次安装依赖，可直接执行：

```powershell
& 'C:\Users\65751\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -m tracelab.stage2 --source-dir 'D:\Downloads\Wechat Files\xwechat_files\wxid_tj9nsz4aymqs12_87a4\temp\RWTemp\2026-10\626a979aaa90ddffbe4f357680f0a341'
```

支持 `--output` 指定根目录，默认 `outputs/stage2/<唯一run_id>/`。
完整运行但尚有业务待确认项时退出码为0，manifest.status为
`completed_with_pending_confirmation`；这不是业务验收通过。
读取/结构失败时保存 failure.json 和事件记录并退出失败。
需要六个原始文件名与 `stage2.FILES` 一致；换版本或表头时应先复核适配映射。

## 输入来源与精度

- 主输入为 Excel “财务原始数据”B/C列原始人民币元；原始 XML 数值文本直接进入 Decimal，不经过 float。
- CSV 入口保持第一阶段十列契约。新 stock_code、来源印刷页/PDF页、evidence_id 等放入元数据和 financial_records.json，不破坏旧入口。
- 股票代码始终为字符串 `000651`。营业收入/营业总收入及净利润/归母净利润分开映射。
- 2025年报比较列与2024年报实际提取的相应项目交叉核对，所有金额及定位差异单独留存。
- 不改原始附件。每次运行保存六个附件快照、SHA-256、表格单元格及PDF/Word提取结果。
- 原金额的数字差异仍按原值计算并标记待确认，不静默覆盖为PDF数字。原始PDF为空白的金额不按Excel的0获得验证：该行阻断。
- 亿元显示采用 ROUND_HALF_UP，保留4位；同比仅在基期>0且本期>=0时计算，比例保存50位有效精度，百分数展示两位。
- 这些是展示规则，不是金融组勾稽容差。人工对比同时保存原始差异和双方展示舍入值，不能凭展示相同宣称精确相等。

## 桥接边界

用户确认的三个关系分别计算2024、2025和两期变化残差：

1. 利润总额 = 营业利润 + 营业外收入 - 营业外支出。
2. 净利润 = 利润总额 - 所得税费用。
3. 归母净利润 = 净利润 - 少数股东损益。

Excel原值是主结果；从PDF独立提取的原始披露值另存参考勾稽，不用来覆盖Excel。
残差定义为“披露目标值减带符号组成项之和”。`exact_zero_residual`仅表示精确为零，
`nonzero_residual`保留实际差值，不设通过阈值，`incomplete`表示缺失项。
所有业务验收状态均保留待金融组确认。

营业利润只做金融组给定八项总额的方向性核对，明确标为 selected_reported_aggregates_not_full_bridge。
营业总成本八个明细另做报表结构检查；营业总收入明细遇空白佣金收入时不补零。
不将总额与明细同时加入同一条桥接，不把不同层级方向性影响重复相加。
净敞口套期收益等空白项目的处理与全量映射尚未获最终确认，故不声称完成完整桥接。

## 输出索引

| 输出 | 用途 |
|---|---|
| inventory.json、inputs/、source_text/ | 原始来源、字节快照、哈希及提取中间数据 |
| normalized/financial.csv、metadata.json | 与第一阶段兼容的真实输入 |
| field_mapping.json、financial_records.json | 原名称到稳定标识、两期来源、金额、核验状态 |
| source_checks.json、segment_checks.json | 原始年报交叉核对及分产品金额核对 |
| metrics.csv / metrics.json | 两期金额、差额、同比、方向；阻断项保持空白 |
| directional_impacts.csv | 明确公式下分利润层级的带符号影响；非经营原因 |
| bridges.json、pdf_reference_bridges.json、bridge_checks.csv | 两种来源基准分别勾稽，保存实际残差及待验收状态 |
| human_comparison.csv / json | Excel、最新Word及早期Word参考结果的逐项对比 |
| conflicts.csv / json | 页码、金额/精度、口径及参考文字冲突；不改原资料 |
| evidence.json | E01—E06实际PDF原文、印刷页/PDF页、金融组摘要、关联问题及支持边界 |
| investigation_plan.json | 分层利润拆解顺序、实际方向信号及待执行调查问题；不是 Agent 执行结果 |
| pending_questions.md、summary.md | 金融组待确认事项和本次运行摘要 |
| manifest.json、events.jsonl、stage1/ | 状态、代码/输入哈希、执行日志及复用第一阶段的完整结果 |

证据摘录直接来自PDF文本层。E01—E03使用实际原文锚点，E04—E06保留相关完整页，
可通过印刷页、PDF页与原始快照复核。没有把Word摘要改写成引文，也没有做模型因果判断。
PDF文件可读取、页数及文本提取完整不等于已核验每一页的财务真实性。

## 已发现的待确认事项

- 利润表实际页码为2025印刷87/PDF88、2024印刷113/PDF113；金融组对应定位86、112需修订。
- 最新Word表4中四个利润层级的两年金额存在约100倍的数量级差异，保留原值和程序结果供确认。
- Excel当前手续费及佣金收入为0，PDF为空白；不自行认定空白=0。
- Excel营业外收入2024原始存储为72190967.81999999，PDF为72190967.82。
  主桥接保留由此产生的0.00000001元基期残差；单独PDF勾稽可验证其披露值关系。
- Excel桥接表D22、D24的变化参考与原始金额相减分别存在0.01元、0.05元差异，不能静默改写。
- Excel桥接表A30称存在差额，但E13为0；选定总额数学闭合仍不代表完整桥接已验收。
- PDF披露合并范围发生变动；当前是披露报表同比，不代表恒定主体范围的经营比较。
- 早期Word中若干末位差异、Excel比例存储尾差全部列入对比；不让旧版覆盖新版。

本阶段完成后停止。下一步可围绕已核实指标和原文准备单次证据分析，但需要金融组先确认
上述数据处理边界、具体证据问题和模型配置。完整桥接不能表述为已业务验收。

用户已确认格力演示采用“利润下降、经营现金流增长”，按营业利润、利润总额、净利润、
少数股东损益、归母净利润逐层分析。详细规则见 [分析与演示方向](analysis-direction.md)。
