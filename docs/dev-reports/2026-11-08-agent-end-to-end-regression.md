# 第五阶段：历史真实调查失败样本离线端到端验收

日期：2026-11-08。结论：**离线端到端验收通过（保留两项已知费用价格日期测试问题，全量不是全绿）**。本结论仅针对本报告明确覆盖的工程链路，不代表真实Qwen能够稳定完成调查，也不是新真实调用授权。

## 1. 实际基线与修改范围

分支main，HEAD d7fb943。开始时Prompt为已修改状态，第四阶段测试test_qwen_output_contract.py和报告未跟踪，全部原样保留。两个PDF已由d7fb943跟踪，与6760f7f相比该提交仅新增PDF；不回退到附件旧基线。普通执行沙箱仍初始化失败，本轮经执行审批使用本地命令，未改权限。

本轮仅新增tests/test_agent_end_to_end_regression.py（3项跨模块/多文件审计测试）及本报告；隔离工件位于tmp。没有更改业务代码、Prompt、Schema、财务公式、Validator、证据或费用日期；未读取密钥、未真实联网/API调用、未commit/push。

已读取五份指定报告，结合当前agent_live、investigation、agent、evidence_progress、qwen_decider、analysis_contract、stage3、semantic_boundary、source_contract及Prompt和测试确认：范围内五任务规划入口、任务进度、有限决策提示、前置准入、语义边界及第四阶段指令均存在。真实入口prepare_scoped_investigation接入由既有第一阶段Mock入口测试验证；本次实际端到端链路为GOAL+限定历史payload→当前规划器→QwenDecider/ReplayTransport→Agent工具→前置检查→Validator→审计输出。没有调用真实入口的生产Transport或复用历史授权。

## 2. 指定历史样本完整性

唯一目录为outputs/agent_acceptance/20261102-authorized-3409dac866。10个必需文件均实际存在并解析，execution_binding.json在授权根目录，不在investigation子目录。以下为实际路径及SHA-256；开始和结束哈希一致。

|实际路径（全部存在）|SHA-256|
|---|---|
|D:/Projects/TraceLab/outputs/agent_acceptance/20261102-authorized-3409dac866/live/20261102T143227-e1ab7ac1f3/investigation/input.json|46b72ad2713438b720e468fb4b4478c4ca0f6f43f50a83d30c1785cac13c8c07|
|D:/Projects/TraceLab/outputs/agent_acceptance/20261102-authorized-3409dac866/live/20261102T143227-e1ab7ac1f3/investigation/analysis.json|fd17f08aa6b081ab3c68eb4bca8b7afd2a586ed0579fdae13d32eadb26fdec35|
|D:/Projects/TraceLab/outputs/agent_acceptance/20261102-authorized-3409dac866/live/20261102T143227-e1ab7ac1f3/investigation/checks.json|d2662908c57cd6f81f3cf4c7874bed65e136cb9899e6cab3948f49fc6ecde29f|
|D:/Projects/TraceLab/outputs/agent_acceptance/20261102-authorized-3409dac866/live/20261102T143227-e1ab7ac1f3/investigation/events.jsonl|7d748ab78cbb6240caee2259fa68a474880b455af43cb10ac49f2a1ce8263044|
|D:/Projects/TraceLab/outputs/agent_acceptance/20261102-authorized-3409dac866/live/20261102T143227-e1ab7ac1f3/investigation/result.json|6ab8ecbffbede426490442b0abcfdce35a3406087f1ac99d7808768ebde99141|
|D:/Projects/TraceLab/outputs/agent_acceptance/20261102-authorized-3409dac866/live/20261102T143227-e1ab7ac1f3/investigation/plan.json|8df726f63654a96742475a8f34c56c577472110d8102fd4188dce7a4abc4b87d|
|D:/Projects/TraceLab/outputs/agent_acceptance/20261102-authorized-3409dac866/execution_binding.json|1b953387fe3e726ae534dd5d766ebb668bd268b6375e813d3884847c676d77c9|
|D:/Projects/TraceLab/outputs/agent_acceptance/20261102-authorized-3409dac866/live/20261102T143227-e1ab7ac1f3/investigation/decisions/01.json|95397485c4d2cfcbb8e306061508b4365b8a31f861f980434c3b1eb98f9c3cb9|
|D:/Projects/TraceLab/outputs/agent_acceptance/20261102-authorized-3409dac866/live/20261102T143227-e1ab7ac1f3/investigation/decisions/02.json|53f3f7e255eb63c20d579bf890bbe245938695c5611bb2b373c92e4b3965249b|
|D:/Projects/TraceLab/outputs/agent_acceptance/20261102-authorized-3409dac866/live/20261102T143227-e1ab7ac1f3/investigation/decisions/03.json|5ce56628fcde7e352e4951afd4033a679cf81aa006dde3183215da9106459074|

历史输入、原plan、request、response及result未修改。当前代码是d7fb943加第四阶段未提交Prompt，不是历史运行版本；历史执行绑定记录保留在上表文件中。Replay只取原始response.messages文本、finish_reason和原usage构造ReplayTransport协议封装，不重写动作或分析。测试逐轮比较新决策审计action及可见response.messages与历史记录一致。

## 3. 验收A：历史原样Replay

当前规划器生成五任务，不复制历史空tasks。执行原search→get→explain，3次模拟模型请求、2次工具调用；第一次search返回5条证据，F_net_profit仍没有本轮资格。任务状态为pending、answered、answered、evidence_gap、evidence_gap。净利润仍待查，经营现金流与年报披露已取得，但背离不自动回答。

结果validation_failed / explain_precheck_rejected；evidence_gap.ineligible_citation_ids包含F_net_profit，原Explain不能进入成功状态。task_progress.json与result中的台账一致，未决任务及问题保留。历史第三轮确为完整JSON、786输出Token，旧checks有11条错误，失败不是截断。

当前Replay在前置检查结束，故没有checks.json或analysis.json：这是未执行后置Validator的实际路径，不伪造检查文件。原始模型分析仍完整保存在decisions/03.json及decision事件；原历史analysis.json原样保存。不能为了输出旧11条错误而绕过前置。

另在tmp/phase5-independent-validator-diagnostic.json保存独立诊断，明确diagnostic_only/not_agent_replay；给Validator全部授权证据仅用于独立定位，不授予Agent检索资格。得到17条错误，包含引文、金额来源/指标、口径冲突、支持范围、自由数字、长度及会计关系；E07_28指定换行不再误报。这不是完整Agent Replay结果。

## 4. 验收B：合成合法路径

测试标签synthetic-limited-success，响应明确为合成：search(metric_id=net_profit)→search(metric_id=operating_cashflow)→get(E07_28)→受限explain。额外get使最终上下文直接显示披露原文；没有强制五次工具调用或扩大授权。

4次模拟请求、3次工具调用，实际取得两核心事实及披露来源。前置ready=true；原完整Validator errors=[]，结果pending_human_review / human_review_required，manual_review非空。任务状态为answered、answered、answered、evidence_gap、evidence_gap；questions及task_evidence_gaps保留，complete不被当作经营问题已解决。accounting_relations仍为空，未补造桥接。合成Explain只表达待验证关联及事实支持边界，不声称背离已完整解释。

## 5. 验收C：关键拒绝边界

以下由独立运行的既有专项与新增跨模块测试共同覆盖，不新增平行Validator：

|反例/边界|具体断言或预期|
|---|---|
|授权内未检索、提前Explain|ineligible_citation_ids及missing_core_metric_ids；explain_precheck_rejected|
|净利润误称归母、金额相等冒充等价|metric_scope_conflict；正确否定/对比不产生该错误|
|引文数字、标点、名称或实质文字修改|quote_matches=false或引文与原文不一致；指定E07_28软换行通过；不能全局删空白|
|cash_2/cash_6错误归属净额|金额未关联该条财务项目、金额缺少原始来源|
|空关系、错误component/effect、跨层合成|会计关系未获核验支持或方向不一致，不允许自行构造|
|正文金额/比例|字段级自由文本含未结构化数字；真实quote比例原样保留；ratios_allowed仍false|
|主要系夸大为全部净额贡献|support_scope_overreach；不能覆盖/缺乏证据等否定不误拒；复杂因果留manual_review|
|Validator拒绝|新增invalid-quote审计：前置通过，checks错误与result.errors一致，validation_failed/validator_rejected；evidence_gap不伪装校验错误|
|预算/最后请求正常提交|budget_exhausted与human_review_required不同，未完成任务可追踪|
|重复与越权工具|repeated_action、unauthorized_fact/evidence等明确拒绝；不多发后续请求|
|非法JSON/模型异常|system_or_decision_error及具体错误；不伪装合理证据不足|
|请求/工具/Token/费用与零重试|原预算及费用专项照常；5请求/4工具/1200输出/60000 usage目标/90秒/30元辅助保护不变，价格日期保护仍阻断过期配置|

费用测试的两个已知日期问题仍未通过，不能说所有费用场景全绿；测试没有改日期或关闭保护。Token目标沿用既有语义：达到累计usage目标后停止，不能据此承诺事前精确估计输入Token或独立绝对账单上限。

## 6. 验收D：跨文件审计

新增3项不只断言状态，还核对：plan中的5个任务ID与task_progress一致；台账与result完全一致；events最后结果与result一致；tool_result事件数等于tool_calls；retrieval_audit证据并集等于retrieved_evidence_ids；磁盘decision records与QwenDecider.records一致，记录数等于model_requests；逐次usage合计等于reported_total_tokens；input保持不变；未决任务、错误及终止分类符合各自路径。

simulation=true、llm_called=false、retries=0、actual_total_tokens=null、cost=null、cost_status=not_applicable_simulation。历史Replay携带历史usage总数10932，仅为模拟封装中的已知历史用量；合成成功/拒绝各480为测试夹具usage。均不是本轮真实Token消耗或服务商账单。候选仅规划提示，引用资格仍来自工具审计；已有专项核对两者分离。

以下为全量测试生成并保留的最新隔离工件（每次测试用独立目录，不覆盖历史）：

- historical-original：`D:\Projects\TraceLab\tmp\phase5-historical-original-vg8n7wi2`；validation_failed。
- synthetic-limited-success：`D:\Projects\TraceLab\tmp\phase5-synthetic-limited-success-3zh61h6k`；pending_human_review。
- synthetic-invalid-quote：`D:\Projects\TraceLab\tmp\phase5-synthetic-invalid-quote-93qnqrkc`；validation_failed。

每个目录有fixture.json标签及investigation下plan、input、events、decisions、task_progress、result；后置Validator实际执行的两条合成路径另有analysis和checks。工件索引tmp/phase5-artifact-index.jsonl，原始输入清单tmp/phase5-input-manifest.json。临时工件不提交。

## 7. 独立专项与全量结果

八组均分别执行unittest discover -p，日志tmp/phase5-<专项名>.log：

|专项|通过|失败|错误|跳过|
|---|---:|---:|---:|---:|
|第一阶段|14|0|0|0|
|第二阶段|12|0|0|0|
|第三阶段|17|0|0|0|
|第四阶段|15|0|0|0|
|历史证据链|9|0|0|0|
|历史现金流关系|15|0|0|0|
|历史引文|11|0|0|0|
|历史自由数字|10|0|0|0|
|既有专项合计|103|0|0|0|
|新增跨文件端到端|3|0|0|0|
|全量355项|353|1|1|0|

全量实际执行python -X utf8 -m unittest discover -s tests -v，耗时142.429秒，日志tmp/phase5-full.log。使用现有tmp/test-deps及项目tmp临时目录。失败test_timeout_or_missing_usage_preserves_reserve_and_stops，错误test_correct_model_region_and_free_tier_send_once，仍由price_reverification_required触发，与352项基线一致，无新增回归。不更改保护或预期制造全绿。

## 8. 结论与剩余限制

验收结论依据完整历史Replay、合成成功路径、Validator拒绝路径、多文件审计和安全回归，不仅是103项专项数量。限定范围的离线端到端验收通过；全量两个既有费用日期问题保留，真实调用仍须重新预检价格、快照、授权及预算。

未发现需要本轮修改业务逻辑的新缺陷。保留现有限制：任务规划仅面向已定义业务目标，背离解释不会因检索自动完成；语义检查有限，不能证明复杂经营因果；前置拒绝安全结束而不自动补救；历史样本是本地只读依赖，干净克隆需另行准备资料；模型真实遵从、稳定性及费用实际账单未验证。pending_human_review也不是金融组已批准。

对全部tracelab源码、Prompt、第四阶段测试/报告、历史目录及PDF的前后哈希检查差异为空。git diff --check通过。未改原始资料，未发真实API请求，未commit/push。第五阶段完成后停止，等待下一步指令。
