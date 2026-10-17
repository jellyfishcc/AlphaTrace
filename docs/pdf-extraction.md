# 原生文字 PDF 财务表格提取 MVP

2026-10-18，属于现有第一模块的受限提取入口，不新增开发阶段。基线 HEAD：`b039d87f932bd1a7cfa5cbac9c56138956ed2289`；开始时工作区干净。未改 Agent、财务公式、来源规则或可信事实，未调用模型，未 commit/push。

## 输入与处理边界

旧 `stage2` / `final_release` / `final_revision` 以人工整理 Excel 底稿为财务金额输入，PDF 用于原文和金额核对。`source_io` 提供底稿读取，`source_contract` 提供本地 PDF 哈希、摘录、页码和事实绑定核验。本入口补充独立的 PDF 金额来源，不把旧底稿称为自动提取结果。

`tracelab/pdf_extract.py` 内的人工配置仅包含公司、合并利润表标题、PDF 第 88 页、印刷第 87 页、年度范围与五个科目映射，没有目标金额。实际读取 `inventory.json` 的 2025 PDF 文件名和哈希，只从快照 `inputs/` 定位文件，不访问 inventory 中历史微信路径。

流程：原始 PDF 字节 SHA256 校验 → pypdf 文字层 → 标题/表尾/编制单位/人民币单位/年度表头/印刷页核验 → 锚定完整科目名 → 读取两个原始金额字符串 → 根据表头年份映射 → Decimal 换算到元 → 保存 JSON/CSV → 之后才加载旧可信事实进行比较。

科目、两列或单位无法确定时保留 missing 与原因；无占位符的单列金额无法判断落在哪年，整行两年均不输出金额。显式 `—`/`–`/`-` 空白不填零。支持负号、括号负数、千分位及小数；不猜测换行、跨页和任意其他版式。净利润和归母净利润按完整科目分开匹配。

## 输出和独立核验

- `extracted_financial.json` / `.csv`：每个科目每年一条记录，`value` 与兼容字段 `metric_value` 为精确元金额字符串；保留 `standard_metric` / `statement_scope` 等现有字段别名。
- `extraction_audit.json`：原始页文本、目标行、行号、原始金额字符串、文件/页文本/行 SHA256、人工科目映射、失败原因、比较前提取文件哈希。
- `comparison.json`：逐项提取值和可信值、真实来源编号、matched/mismatch/missing/unverifiable。
- `report.md`：可阅读的结果与核验表。

比较复用 `final_release.load_agent_payload` 和只读 `LocalFacts`，现有加载器先重新核验快照、PDF 与事实注册。再核对公司、期间、合并口径、币种、元单位、证据中的文件哈希/两种页码/目标原文行和 Decimal 金额。任何差异保留双方原值；未经验证的来源不能标 matched。2024 列是 2025 年报列示的比较值，合并范围不一定恒定。此为同一披露源与已有可信数据的一致性检查，不是外部审计或 PDF 发行方真实性认证。

输出在 `.gitignore` 已忽略的 `outputs/pdf_extract/`，没有复制原始附件至源码。审计中含本地 PDF 原文，发布源码时不要手动强制加入 outputs。

## 可重复运行

仓库根目录，Python 3.10+，依赖沿用 `requirements.txt` 中 `pypdf==6.10.0`：

```powershell
python -m pip install -r requirements.txt
python -X utf8 -m tracelab.pdf_extract --stage2-run outputs/final_revision/20261017T093152-d80de1cefa
python -X utf8 -m unittest discover -s tests -p test_pdf_extract.py -v
python -X utf8 -m unittest discover -s tests -v
```

`--stage2-run` 沿用既有命名，但本入口需要支持 `load_agent_payload` 的最终版/修订版快照。除 PDF 与 inventory 外，完整比较需要原有 normalized/metrics/source_checks、来源证据及 release_hashes 等快照文件。缺少这些文件不冒充 matched；若 PDF 可读取，提取结果仍保留，比较标 unverifiable。缺少 PDF 时保存失败审计，退出码 1。全十条提取且匹配返回 0，部分失败返回 1。

本机真实输入：`outputs/final_revision/20261017T093152-d80de1cefa/inputs/格力2025年年度报告.pdf`，219 页，SHA256 `eda18a6d7382410f3096ffa764b99c8740287c665b20ee2377abb99c34414054`。已实际渲染检查第 88 页并确认印刷页码 87；文字层可直接读取。

本机最终代码成功运行目录：`outputs/pdf_extract/20261017T195532-0c947edc10/`（目录时间为 UTC，北京时间 10 月 18 日）；此前成功目录 `20261017T195218-ea35df36fe` 也保留。真实终端结果：

```json
{"extracted_fields":10,"matched":10,"mismatch":0,"missing":0,"unverifiable":0,"failed_fields":0}
```

|科目|2024（元）|2025（元）|PDF/印刷页|结果|
|---|---:|---:|---|---|
|营业利润|36988437925.60|34681293552.28|88/87|两年 matched|
|利润总额|36895995848.30|34644658951.12|88/87|两年 matched|
|净利润|32371069287.35|28862746016.16|88/87|两年 matched|
|所得税费用|4524926560.95|5781912934.96|88/87|两年 matched|
|归属于母公司股东的净利润|32184570372.28|29003103411.66|88/87|两年 matched|

上表是本次执行结果，绝不是提取程序的输入配置。第一次运行提取十条成功，但比较器把字符串印刷页码与整数直接比较，十条均为 unverifiable；该失败目录 `20261017T195007-e2dd69e1ad` 保留。修复仅在新模块中规范化页码比较，没有放宽旧来源规则。

## 测试与展示边界

公开 fixture `tests/fixtures/pdf_income_synthetic.txt` 明确标注合成金额。测试还用 pypdf 在临时目录创建含中文原生文字层的合成 PDF，验证真正的 PDF 读取路径；不需要格力私有附件。另有本机真实 PDF 和可信来源的集成测试，缺少快照才跳过。

定向测试覆盖年份调换、精确小数/负数/单位换算、空白、歧义、重复行、来源、金额差异、口径差异、篡改事实与不支持版式。初次构造合成 PDF 时遗漏字体子字典，测试报错；补全合成样本后通过，未修改真实 PDF。

最终验证：新增定向测试 **21 通过、0 失败、0 跳过**（11.332 秒）；全量 Python 测试 **204 通过、0 失败、0 跳过**（95.075 秒）。日志分别在 `outputs/pdf_extract_inspection/targeted-tests.log`、`outputs/pdf_extract_inspection/full-tests-final.log`。本机使用 Python 3.12.14 和 pypdf 6.10.0；若系统 Python 未安装依赖，需先按上述 requirements 安装。沙箱临时目录权限受限时，将 PowerShell 的 `$env:TEMP` 与 `$env:TMP` 指向仓库内已创建的 `tmp/` 再运行测试。最后一次真实 CLI 返回 0，十条全部匹配；比较前后的提取 JSON SHA256 一致。

展示顺序：打开原始 PDF 第 88 页 → 执行 CLI → 查看提取 JSON/CSV → 查看 comparison 与 report → 展示项目已有的后续财务分析。新数据不自动写回分析快照；后续分析仍使用既有核验事实。本轮只证明这张表五个科目的可复现提取与一致性，不宣称通用 PDF 准确率或 Agent 自主成功。
