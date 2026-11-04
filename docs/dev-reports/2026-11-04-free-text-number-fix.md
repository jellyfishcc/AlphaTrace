# 自由文本数字与结构化事实一致性修复

2026-11-04，D:/Projects/TraceLab。保留原有未提交工作；未调用模型、未改历史输出、未 commit/push。

## 实际根因及历史字段

实际读取指定2026-11-02 investigation 的 input.json、analysis.json、checks.json、events.jsonl，以及 stage3.py、analysis_contract.py、qwen_decider.py、Prompt及相关测试。

stage3.validate 原来将 questions、claims.statement、claims.support_limit 汇总，用包含任意数字或中文金额的正则统一拒绝，没有区分授权期间与金额。citations.quote 不属于这段扫描，按原文匹配及来源规则另行核验。analysis_contract.configure 设置 ratios_allowed=false，check_contract 没有另行读取这个布尔值来许可比例；此前禁止正文比例实际依靠自由文本扫描，Schema也没有比例承载字段。本轮未改成true、未新增比例授权。

|历史位置|触发数字|
|---|---|
|claims[0].statement 年份|2025、2024（出现两次）|
|claims[0].statement 金额|28,862,746,016.16；32,371,069,287.35；46,383,114,754.02；29,369,250,570.66|
|claims[0].statement 差额|3,508,323,271.19；17,013,864,183.36|
|claims[0].statement 比例|57.93%|
|claims[1].statement 比例|57.93%|
|claims[1].support_limit 页码|28|

其他历史 support_limit、questions 没有触发数字。原文引述中的金额与57.93%不触发正文扫描，不应删除或改写。

原始第一条 amounts 只有 net_profit 和 operating_cashflow 的 base/current，未列 change。此前并不会从 base/current 自动补 change，也不会将正文差额自动与事实关联；统一扫描直接拒绝。两笔差额如需要作为数值事实表达，应复制输入中已经由Python核验的 change，且保留其符号、fact_id、期间、单位及来源，不能由模型或Validator临时补算。

## 核对后的最小方案

不改SCHEMA_V2：正文定性表达变化，金额主要载体仍为amounts。唯一新增数字例外是 payload.periods 内的四位ASCII年份，须紧跟“年”并满足明确边界。示例“2024年与2025年”“2024年—2025年”允许；裸年份、未经授权年份、页码、年份外形的金额、十进制/有符号数字不允许。“2024—2025年”需改成每端带年的明确形式。

金额即使已出现在amounts，仍不能重复放在自由文本中：当前协议没有安全的自然语言数字到指标/字段逐项绑定，按数字集合相等放行会误接受错指标。此限制维持原有合同，不新增模糊推断。准确金额与可读性通过结构化amounts配合定性正文实现，无需修改Schema。

比例只允许作为合格证据的真实quote出现。正文57.93%即使与原文一致仍拒绝，不允许模型自行计算、复述为自己的比例判断或贡献率。原始quote继续接受第三项的严格文本/已审核软换行规则。ratios_allowed=false保持不变；本轮也不实现true模式。

## 修改文件

- tracelab/stage3.py：提取 free_text_number_errors，按字段输出可审计错误位置；只豁免授权、明确标记的年份，继续拒绝其余数字、中文金额及百分之表述。未改前三项来源、金额、关系、引文核验代码。
- qwen_decider.py 已检查，最终没有本轮逻辑改动；复用已有事实 periods，避免重复上下文。
- prompts/agent_decision_v1.txt：澄清期间例外、正文/amounts分工、change复制已核验事实、原文比例不等于计算授权；此前三项规则保留。
- tests/test_free_text_numbers.py：新增10项测试。

没有修改analysis_contract.py、财务公式、原始数据、SCHEMA_V2、费用保护或前三项测试。

## 测试

新增10项专项全部通过（0失败/0错误/0跳过）：授权年份；伪装金额/错年份；自由金额及比例拒绝；正确base/current/change和来源通过；缺change不授权正文差额；篡改金额/字段/指标拒绝；原文比例保留及正文比例拒绝；历史原样Replay失败；比例合同维持false；questions/support_limit同样受检。

真实Replay原样读取既有响应，不修改原文；因缺失原检索资格仍被前置检查拒绝。直接Validator测试确认历史正文金额/比例仍拒绝；前三项核验没有被数字例外绕过。合成测试变体不代表新的真实Qwen输出。

最终全量：294项，292通过、1失败、1错误、0跳过，123.227秒。失败 test_timeout_or_missing_usage_preserves_reserve_and_stops、错误 test_correct_model_region_and_free_tier_send_once 均由既有 price_reverification_required 引起，费用保护未改。本轮无新增回归。

前三项独立回归：证据链9/9、现金流关系15/15、引文11/11全部通过（均0失败/错误/跳过）。新增数字专项10/10通过。git diff --check通过。本轮专项离线验收通过，全量不宣称全绿。

中间版本新增Prompt和数字上下文字段导致历史Replay输入字节预算耗尽，已撤回冗余上下文字段、压缩本轮Prompt改写；未提高预算、未修改前三项测试。最终第一项9项已再次全部通过。

运行 python -X utf8 -m unittest discover -s tests -v，测试子进程使用项目tmp及已有tmp/test-deps；最终日志为 tmp/free-number-final-tests.log。没有安装依赖或读取密钥。

## 限制

年份例外只确认期间属于输入范围，不自动证明句子中的经营因果或期间语义正确。金额字段错配继续按对应fact/field的Decimal值核验；没有结构化金额时不从文字猜数或计算差额。正文精确金额仍不支持自由复述，若未来需要此能力，应另行设计明确绑定合同。页码仍使用引用元数据，正文页码数字不新增例外。

本轮仅数字规则专项，历史完整分析仍有其他错误，不能称为真实调查通过。完成后停止。
