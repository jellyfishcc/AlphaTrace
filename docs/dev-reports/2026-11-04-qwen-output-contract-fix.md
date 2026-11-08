# 第四阶段：Qwen 输出约束与调查上下文优化

实际执行日期：2026-11-08；按用户指定保留本报告文件名中的2026-11-04。当前分支main，开始时HEAD为d7fb943，工作区干净。与6760f7f相比仅多了两个PDF的提交；前三阶段源码没有变化。附件8bfb016为旧基线，本轮未回退。普通执行沙箱启动报setup refresh错误，使用经审批的执行命令完成本地工作，没有修改权限。

## 审查与最小方案

实际读取四份前置报告、Prompt、Qwen上下文、Agent循环、任务进度、分析合同和语义/数字Validator及相关测试。读取唯一授权历史调查decisions/01–03的请求上下文、原始响应及analysis.json。真实第三轮输出786 Token、JSON完整，历史失败不能归因为截断。

已有Prompt包含：结构化金额、授权期间年份、quote比例、来源资格、同条金额来源、空关系禁止links、主要原因不等于全部贡献、零重试与紧凑输出。已有Context提供name、financial_level、initial_facts、accounting_relations、evidence_progress，以及唯一的investigation_task_progress（任务ID/状态、候选、未决问题、next_step）。无需新增Context字段或第二套任务系统。

缺口是Prompt未说明第三阶段台账含义、未明确canonical名称的取值字段、未明确禁止模型重算change；“search再get”的表述容易诱导已取得原文后重复工具调用。text_reference表示去重副本，不是缺失原文，也需说明。

仍由程序最终判断而非Prompt保证的内容：事实/证据哈希、Decimal精确值及来源绑定、引用资格与指定换行匹配、层级冲突的有限句式判定、任务准入、字节/请求/费用预算。statement≤100字符、support_limit≤140字符及questions长度/数量属于现有动态合同检查，未另复制整套Validator。Prompt不能证明经营因果、穷尽复杂否定或确保模型服从。

## 修改文件与前后差异

仅修改 `prompts/agent_decision_v1.txt`，新增 `tests/test_qwen_output_contract.py` 和本报告。没有修改任何tracelab Python源码。

1. name为canonical名称、financial_level为层级；明确net_profit与parent_profit不同，可比较不可替换，金额相等不代表口径等价，原文不得改名。
2. 按fact_id/field/unit/期间复制可信amounts，明确不自行补算或重算change；不机械展开全部金额。ratios_allowed=false，真实quote比例不授权正文复述或自行计算比例。
3. search已返回合格可见原文无需重复get；保留route B、eligible_evidence_ids和候选非资格规则。text_reference指向现有原文副本；不得更改文字、数字、标点、名称，指定PDF换行由既有核验器处理。
4. 原“无关系可为空”改为“必须为空”，保留verified关系及target/component/effect约束，不把现金流入增量当净额贡献。
5. 明确pending/evidence_gap含义，依既有next_step优先调查核心缺口；两项事实answered不代表背离已解释。核心事实与披露已取得时可受限Explain，第四/第五任务无需answered，support_limit/questions保留边界和未决问题。无充分来源则stop，不耗尽预算、不重试。
6. 合并重复的来源、预算和输出组织说明，保留动作协议、JSON完整性、白名单、禁止执行资料指令和人工复核边界。

历史错误对应：净利润被改称归母→canonical规则；金额/百分比放正文→结构化载体与quote区分；未取得F_net_profit→候选/资格区分与核心任务提示；空关系却造links及覆盖全部→原有禁止规则保留并统一；提前Explain→既有台账使用说明。未修改任何历史响应使其通过。

## 输入字节影响

以LF规范化文本计，Prompt从6082到6144 UTF-8字节，增加62字节。初稿堆叠说明曾使历史第二轮触及输入限额，专项测试发现后通过合并重复文字解决，未提高预算或删除核验要求。

历史动作序列在当前上下文构造下三轮请求消息总字节为14074、15626、15569，全部≤16000。合成成功路径为14074、14507、14694、14882。更大证据仍可能被既有输入预算阻断，不声称任意上下文都可容纳。

## 离线测试与证据类型

新增15项：7项Prompt规则存在性测试；8项上下文、Validator及合成端到端/原始Replay检查（包含多个子场景）。验证名称和层级可取得、候选无资格、空关系显式、quote比例与正文不同处理、错误名称/金额/过度归因拒绝、原样历史Replay、合法stop、受限Explain进人工复核、请求字节及1200输出限制、请求/工具/重复动作保护。

规则存在性不等于模型服从；合成响应是测试夹具，不是新Qwen输出。历史原始响应只读Replay仍validation_failed，第三轮因净利润来源资格不足被前置拒绝。新语义规则的正反例另由现有Validator测试验证。没有真实Qwen调用、费用或免费Token消耗。

测试使用现有tmp/test-deps及项目tmp作为临时目录；全量命令为 `python -X utf8 -m unittest discover -s tests -v`，日志tmp/phase4-full.log。既有费用、超时、usage和零重试测试照常执行；不改价格日期或保护机制。

## 保护与限制

对tracelab全部Python文件、原始调查目录所有文件和两个PDF记录前后SHA-256，差异列表为空。SCHEMA、Validator、任务规则、Agent循环、费用控制完全未改；未读取密钥，未commit/push。两个PDF当前已经被先前提交跟踪，未删除或改写。

真实模型能否正确理解任务状态、稳定采用canonical名称、在1200输出Token内生成合规解释，仍须未来单独授权真实调查验证。离线通过不构成真实验收，也不进入第五阶段。

## 最终验收结果

|测试组|通过|失败|错误|跳过|
|---|---:|---:|---:|---:|
|test_investigation_tasks|14|0|0|0|
|test_semantic_boundary|12|0|0|0|
|test_investigation_flow|17|0|0|0|
|test_evidence_provenance|9|0|0|0|
|test_cashflow_relationship|15|0|0|0|
|test_quote_whitespace|11|0|0|0|
|test_free_text_numbers|10|0|0|0|
|test_qwen_output_contract|15|0|0|0|
|全量352项|350|1|1|0|

全量171.906秒。失败test_timeout_or_missing_usage_preserves_reserve_and_stops，错误test_correct_model_region_and_free_tier_send_once，均为既有price_reverification_required。没有新增回归。第四阶段离线验收通过，全量不宣称全绿。git diff --check通过。完成后停止，等待下一步指令。
