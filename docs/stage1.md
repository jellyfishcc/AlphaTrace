# 10月15日第一阶段：结构化输入和基础计算

## 已检查的现状及范围

原仓库仅有 README 和 .gitignore，无现成 Python 包、依赖清单、Excel 入口或计算实现。
已读取用户提供的 `D:/Downloads/tracelab项目理解_v2.zip` 中的
`tracelab项目理解.md`，尤其是结构化数据、确定性计算、接口及待金融组确认事项。
压缩包还含三张说明图片，没有代码和真实案例数据；本阶段未修改或解压覆盖原始资料。
未找到单独的 `tracelab_tech.md`。

沿用 Python 确定性计算方向。当前需求用标准库 csv、json、decimal、unittest 即可，
无需安装 pandas、Pydantic 或 Excel 库。以后需要时再接入，不更改当前金额精度约定。
本阶段交付是可运行的 Python 数据入口，CSV 是数据交换文件，不是 Excel 工作簿。

唯一计算公式：**项目差额 = 本期金额 - 基期金额**。
费用增加也按原始符号相减，不擅自改成负贡献。不求和、不拼接利润桥接，
不计算增长率、贡献率，不实现异常分类、证据等级、前端或模型调用。

## 文件结构

```text
tracelab/               Python 包及命令行入口
templates/              金融组填写的空白 CSV + JSON 模板
examples/simulated/     明确标注的纯模拟输入和预期差额
tests/                  标准库 unittest 测试
docs/stage1.md          本说明
data/raw/<case>/        用户自行放置真实数据（Git 已忽略）
outputs/stage1/<run>/   每次运行独立输出（Git 已忽略）
```

## 金融组填写方法

先把两个模板复制到自己的案例目录，不修改模拟样例。CSV 使用 UTF-8（允许 BOM），
保留英文表头；每行对应一个可比较项目。项目集合由金融组决定，程序没有内置科目列表。

| CSV 字段 | 填写内容 |
|---|---|
| item_id | 自定稳定且唯一的项目标识；不要用两个标识重复输入同一项目 |
| item_name | 项目名称；相同名称需核对重复或明确细分名称 |
| base_amount / current_amount | 两期原始金额，按原始符号录入；确为零填 0，缺失留空 |
| base_unit / current_unit | 分别填写原始单位，如元、万元；两期必须一致才能计算 |
| base_definition / current_definition | 分别填写该项目定义/统计口径，如对应的完整报表科目名称及范围；不要把不同项目定义写成相同值 |
| base_source / current_source | 两期出处：原始文件名、PDF页码/表内位置或来源URL及定位；重述值注明版本 |

两期单位不同会阻止该行计算，不自动换算。不同项目可使用不同单位，
差额沿用该行单位，程序不会对跨行单位做假定，也不会跨行求和。
`base_definition/current_definition` 是每个项目自身的定义；JSON 的 `profit_basis`
是本次分析目标的利润口径，二者不可替代。包含净利润行时，其定义应由金融组确认与分析目标一致。

JSON 元数据：

| 字段 | 要求 |
|---|---|
| dataset_id | 本次案例/数据版本标识 |
| data_kind | 真实数据填 real，模拟数据填 simulated |
| comparability_confirmed | 未确认用 null；金融组核对期间、项目定义、范围与重述版本可比后才填 true |
| base / current | 分别填写下述两期信息，不能只写一份默认值 |
| company | 两期公司/主体名称，须一致 |
| period_start / period_end | 明确报告期起止，YYYY-MM-DD；非发布日期 |
| currency | 币种编码，如 CNY；两期须一致，不自动换汇 |
| statement_scope | 报表范围，由金融组填写；两期须一致 |
| profit_basis | 净利润或归母净利润等实际确认的口径，两期须一致 |
| data_version | 来源版本，例如原始披露/追溯调整后的比较数及文件版本说明 |

同名公司、同样的描述或填写 true 都不代表程序验证了事实。
程序只进行文本一致性和格式检查，不推测同义科目、检查报表真实性或证实重述可比性。
项目缺失、未知和占位词会记录为待确认；不能将“未知”改成一个猜测值以绕过检查。
未穷举所有自然语言占位词，金融组仍须复核填报真实性。

## 金额精度及阻断规则

- 从 CSV 字符串直接构造 Decimal，从不经过 float。
- 接受普通十进制数字及正负号，保留小数位，不做金额舍入。
- 单个金额最多128字符，用256位 Decimal 运算精度覆盖对齐和进位；这是技术输入限制，不是金额舍入规则。
- 不接受千分位、括号负数、百分号、科学计数法、NaN、Infinity 或公式。
  按原始数据确认后手动改为普通数字；缺失、破折号不能改成零。
- 全局元数据缺失/冲突、CSV 结构损坏时，整个数据集不计算。
- 单行金额、来源、单位或定义有问题时该行 `blocked`，`difference` 为空；
  其他无问题行仍可计算，但整次运行保持非成功状态。
- 重复标识或名称涉及的所有行均不计算，不静默去重或选取其中一行。
- `PENDING` 表示待金融组确认；`ERROR` 表示格式、缺失金额、重复或冲突。
  两者都会阻止受影响的计算；这是输入校验分类，不是业务风险等级。
- `calculated` 只表示输入检查允许执行相减，不能表述为真实数据已通过人工核验。

## 运行方式

在仓库根目录运行，Python 3.10+，无额外依赖安装步骤。

```powershell
# 模拟数据验证
python -X utf8 -m tracelab --input examples/simulated/financial.csv --metadata examples/simulated/metadata.json

# 真实数据（须先复制模板并由金融组填写，路径只是约定）
python -X utf8 -m tracelab --input data/raw/case01/financial.csv --metadata data/raw/case01/metadata.json

# 全部软件测试
python -X utf8 -m unittest discover -s tests -v
```

可用 `--output <目录>` 指定输出根目录。每次增加独立 run_id 子目录；命令会打印绝对路径。
退出码 0 表示输入校验通过并计算；1 表示错误或待确认；2 表示命令参数/输出文件操作失败。
输入不存在、JSON 无效等也会尽量输出问题清单，不把它们当成空数据的成功运行。

## 输出文件

| 文件 | 含义 |
|---|---|
| results.csv | 原始输入列、输入行号、数据类型、difference 和逐行状态 |
| results.json | 原始元数据与同样的结果，金额仍为字符串 |
| issues.csv / issues.json | 问题类型、代码、输入行号、字段及说明；全局问题行号为空 |
| inputs/financial.csv、inputs/metadata.json | 本次读取的原始字节快照 |
| manifest.json | 输入路径及 SHA-256、代码 SHA-256、Python/包版本、运行状态、公式和限制 |
| events.jsonl | 带 UTC 时间及 run_id 的读取、校验、计算、结束事件 |

CSV 结构错误的行会在问题清单中定位，无法解析的行不伪造结果。
有效行号指 CSV 物理行号；多行引用字段使用该记录结束处行号。
CSV 中金额是精确文本；用程序核对以 results.json 为准，避免 Excel 打开长数字时自动截断精度。
CSV 原文列保持输入内容；如需在电子表格程序中查看，应按文本导入，不执行来源文本中的公式。

日志不读取环境变量，也不包含模型密钥。当前没有 LLM 配置、Prompt 或调用。
manifest 明确 `human_reconciliation=not_performed` 和 `llm_called=false`。

## 第二阶段还需提供

1. 一家真实公司的两期数据及已填元数据；确认公司、比较期间、币种、报表范围、利润口径、单位和重述版本。
2. 金融组逐项人工差额及出处、核对人，以及核对精度/允许误差。当前模拟预期值只是软件测试，不是人工业务验收。
3. 若第二阶段要做利润桥接：金融组确认项目集合、完整公式、各项符号、缺项与未解释差额处理和勾稽容差。确认前仍只计算逐项差额。
4. 待经营证据分析阶段：同公司同期间的经营披露原文及页码、明确的分析问题；允许使用的模型/接口配置，密钥只在本地配置，不写入数据文件。

本次到第一阶段结束。以上材料准备好后再开展人工核对或单次经营证据分析，不自动进入下一阶段。
