# PDF 软换行与引文一致性专项修复

日期：2026-11-04（Asia/Shanghai）。项目 D:/Projects/TraceLab。仅离线修复，未调用模型、未重试、未 commit/push。

## 根因与实际路径

实际读取 20261102-authorized-3409dac866/live/20261102T143227-e1ab7ac1f3/investigation 下 input.json、analysis.json、checks.json、events.jsonl。E07_28 原文为“收到其他与经营活动有关\n的现金增加所致。”；历史模型对应引文仅删除该 LF，其他字符完全相同。原文 LF 的零起始字符位置为58。

重新读取快照 outputs/final_revision/20261017T093152-d80de1cefa/inputs/格力2025年年度报告.pdf，PDF第29页提取文本包含完整原证据；PDF SHA-256 与历史来源凭据一致：eda18a6d7382410f3096ffa764b99c8740287c665b20ee2377abb99c34414054。该位置位于同一句话“有关的现金”内部，为本轮确认的排版换行。

stage3.validate 原先使用 quote in evidence.text：一处检查所有引文，另一处是第二项修复中的金额来源合格引用检查。两处现在调用同一函数。evidence_progress.explain_precheck 负责检索资格和核心来源覆盖，不比较引文文字，不需修改。source_contract.bind_sources 仍严格验证摘录包含于 PDF 提取原文；verified_evidence 仍校验原证据摘要。analysis_contract.check_contract 不比较引文正文，继续验证会计关系等业务约束。未发现这些路径已有软换行规范化可直接复用。

## 修改文件

- tracelab/source_contract.py：新增 quote_matches 和受审查软换行位置表。
- tracelab/stage3.py：两处引文比较统一调用 quote_matches，其余金额与关系规则不变。
- tests/test_quote_whitespace.py：新增11项离线测试。
- 本报告。

未修改 Prompt、SCHEMA_V2、Agent策略、第一项实现与测试、第二项关系/金额规则、财务计算、原始证据或历史输出。工作区原有未提交修改全部保留。本轮只是将第二项来源检查中的文本比较调用统一，并不改其资格标准。

## 规则与安全边界

先保留原有非空原文子串精确匹配。精确匹配失败时，只有通过 verified_evidence 且 PDF文件摘要、完整证据对象摘要同时命中本地审查记录，才可在临时匹配字符串中删除指定 LF。完整证据摘要为23740042da6ac43c77f154c4c582baf8a84f0ad8c353bf350995ecbc60e3b8b3，包含 ID、来源页码、原文等元数据；不能将其他 ID 或另一个 PDF 套用此例外。

目前仅登记 E07_28 第58字符。没有通用中文间换行删除、strip全部空白、空格折叠、标点转换、数字重排、模糊相似度或语义匹配。未知换行、不同证据版本及无法判断的段落边界保持严格匹配。函数不改写 evidence.text、quote、事实或任何审计日志。其他已精确匹配的引文仍走原路径；来源可信度及检索资格依旧由既有检查独立保证，不能把文本匹配当作来源授权。

## 历史验收与测试

真实原始响应及 usage 由既有 Replay 帮助函数逐字读取，未伪造新模型输出。测试用的错数字、错项目名等变体仅是离线反例。

新增11项覆盖：已确认软换行；完全一致；数字/项目名称/标点/增删实质文字（子测试）；禁止删除所有空白；未知换行严格拒绝；错误证据ID；证据摘要失配；其他PDF摘要；历史其他错误保留；原始Replay继续失败；未经检索继续拒绝。

- 引文专项：11通过、0失败、0错误、0跳过。
- 第一项证据链：9通过、0失败、0错误、0跳过。
- 第二项现金流关系：15通过、0失败、0错误、0跳过。
- 全量：284项，282通过、1失败、1错误、0跳过，77.676秒。失败为 test_timeout_or_missing_usage_preserves_reserve_and_stops，错误为 test_correct_model_region_and_free_tier_send_once，均由既有 price_reverification_required 引起；未发现本轮新增回归。专项离线验收通过，全量未全绿。

历史 analysis 经 validate 后，“结论2引文与原文不一致”消失，但金额未关联、金额原始来源不足、未核验会计关系、自由文本数字等错误仍存在。原样 Agent Replay 仍因第一项证据资格前置检查失败，不能宣称整份分析验收通过。

运行命令为 python -X utf8 -m unittest discover -s tests -v；测试子进程 TMP/TEMP 指向项目 tmp，PYTHONPATH 使用已有 tmp/test-deps。未安装依赖、未改 API 环境变量。完整输出保存 tmp/quote-full-tests.log。git diff --check 无差异格式错误（Git提示 source_contract.py 将来可能转换行尾，不影响结果）。

## 限制与结论

这是一项保守的已核验排版例外，不是自动识别所有 PDF 软换行的系统。新证据/新版本需重新检查原 PDF 和具体位置后登记，未知情况不自动放行。金额、年份、百分比、项目名称和标点仍须精确一致。原有两项价格日期问题不在本轮范围，费用保护未修改。

单项引文匹配修复不意味着真实 Agent 整体成功，也不替代金融组人工复核。本轮结束后停止，不开启真实调用。
