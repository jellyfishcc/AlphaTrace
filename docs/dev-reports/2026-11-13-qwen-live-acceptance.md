# 2026-11-13 修复后首次真实 Qwen 调查验收

结论：**未达到真实自动验收标准**。唯一一轮真实调查已结束，1次模型请求、0次工具调用、0次重试。首轮模型跳过检索尝试长Explain，输出达到1200 Token后截断。原始status=validation_failed，termination_category=system_or_decision_error，errors=[incomplete_response]。不是证据不足主动停止、不是整次预算耗尽，也不是后置Validator拒绝。本轮不继续调用、不修复代码。

## 1. 授权、版本及前置检查

北京时间2026-11-13约14:29—14:32完成检查；真实请求记录时间2026-11-13T06:32:00Z（北京14:32）。main，HEAD 27a9a4b81c47a3407537278e9ffcb5ae4519db89，已包含五阶段修复。开始已有未提交价格维护：tracelab/cost_budget.py、tests/test_cost_budget.py、tests/test_free_tier.py，共享时钟tests/price_clock.py及维护报告；另有旧预检报告与output下无关用户材料，均保留。未修改代码、Prompt、Schema、测试、预算、价格日期或既有日志，未暂存/commit/push。

本次用户明确授权一轮完整调查，最多5请求、4工具。新授权ID为gree-acceptance-20261113-84214a1632ba，未复用历史ID。新工件根目录：

`D:/Projects/TraceLab/outputs/agent_acceptance/20261113-authorized-9234f80f61/`

根目录execution_binding.json在发送前排他创建的新目录中保存：本次用户授权、北京时间、业务目标、Git HEAD/工作区状态、全部源码/测试/Prompt哈希、原历史工件哈希、输入digest、来源审计、模型/Endpoint/预算及本次用户控制台确认。实际入口另外通过claim_once独占创建live/authorizations/gree-acceptance-20261113-84214a1632ba.json。运行ID为20261113T063200-e1d5e7a2bd。该授权已用于本次失败调查，不得再次使用。

Prompt SHA-256：490c738cf2c7951c1e862fd17839b67cf8866d60e87e570709d0cbbebf92ea20。

实际读取价格维护报告和第五阶段端到端报告，重新沿现有agent_live.prepare及QwenDecider检查。生产VERIFIED_DATE=2026-11-13，与实际北京日一致。重新查阅[阿里云官方qwen-plus页面](https://help.aliyun.com/zh/model-studio/qwen-plus)：北京非思考原价三档仍为每百万输入/输出0.8/2、2.4/20、4.8/48元，输入边界128000、256000、1000000；最大输入997952，功能等同qwen-plus-2025-12-01。与代码相符，没有更新生产记录或关闭保护。

配置：qwen-plus；华北2北京；Endpoint为https://ws-6sp1nti4y4d07vun.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions；enable_thinking=false、stream=false、JSON输出。进程Key变量名存在，预检只检查名称/注册表元数据；实际唯一请求由原有bailian.configuration按既有环境变量机制取得Key，没有人工读取、输出或存档密钥值。

用户已在控制台确认：本人账户/默认业务空间ws-6sp1nti4y4d07vun、当前Key归属、用完即停已开启、947.82K/1M、剩余63天；不是API身份或开关验证。现有入口authorization.json仍携带FREE_TIER的11月2日静态快照；它不是当前余额，本次新确认单独保存在execution_binding.json，不篡改历史常量。

## 2. 数据与调用预算

实际重载outputs/final_revision/20261017T093152-d80de1cefa，既有prepare核对来源、45项可信事实、9项已解决冲突；61项release_hashes与历史绑定一致。project收窄后input与11月2日授权输入完全相同，未扩大数据范围。旧preflight.json及export_scope.json仅作为prepare要求的来源/范围约束并重新实算核对，不作为本次授权，也没有重复运行其中的Replay。

事实白名单：net_profit、operating_cashflow、cash_2、cash_6。

证据白名单：F_net_profit、F_operating_cashflow、F_FINAL_cash_2、F_FINAL_cash_6、E07_28、E18。

未外发完整PDF或内部Word/Excel。首轮输入14074字节，小于16000。保留5请求、4工具、1200输出Token、60000累计usage目标、90秒超时、零重试、30元辅助预算。原价容量上界单次4.8477696元、五次24.238848元；不依赖免费额度和缓存折扣。60000是usage目标，不宣称精确事前Token硬上限。价格、配置、上下文大小及费用预留均通过；没有blocked_cost_input_bound或其他阻断后绕过。

## 3. 实际执行与逐轮决策

使用唯一命令python -X utf8 -m tracelab.agent_live，传入既有stage2-run/preflight/scope、--execute-real、新authorization-id、--confirm-free-tier-workspace和新的live目录。实际使用QwenDecider、LiveBailianTransport、当前规划器和Agent，不是Mock/Replay，不另建模型调用脚本，没有连通性探针。

|轮次|发送/响应|模型返回内容|实际执行|
|---|---|---|---|
|1|HTTP 200，finish_reason=length；输入3358、输出1200 Token，耗时27.713秒|文本开头action=explain；包含两条金额事实、一条披露解释，写到第四条hypothesis时中断|incomplete_response，在JSON解析/动作核验前停止；没有有效action，没有工具调用|

request_id：8171e5ae-7c6f-906a-9b3d-75f0579e3bc4。HTTP 200仅表示响应到达，不是Agent验收成功。后续没有第2轮请求；未人工补全JSON、未修改模型文本。

## 4. 任务覆盖与模型实际可见内容

plan.json确实有5类任务：net_profit_fact、operating_cashflow_fact、cashflow_disclosure、profit_cashflow_divergence、remaining_evidence_gaps。最终全部pending，complete=false，planning_gap=false，所有未决问题保留于task_progress.json和result.json。

从decisions/01.json的实际request反解析可见：investigation_task_progress.next_step=investigate_or_stop，五任务pending，候选为E07_28/F_net_profit/F_operating_cashflow；missing_core_metric_ids包含两个核心指标；provided/discovered/retrieved/eligible/visible证据集合均为空。queried_evidence=[]，四项initial_facts的retrieved_source_quotes均为空。accounting_relations=[]明确传递。

模型看到了可信金额、事实名称、候选目录及任务缺口，没有看到任何合格引用原文。净利润、经营现金流和E07_28均未本轮检索。Search/Get次数都是0，retrieval_audit=[]。不能将input中的授权证据当作模型已检索证据。

## 5. Explain、Validator与失败归因

已证实的直接原因：服务finish_reason=length，输出1200 Token，JSON在第四条statement中断。QwenDecider.decide先检查完整性，因此没有执行check_action、explain_precheck或stage3.validate。analysis.json、checks.json、evidence_precheck.json均未产生，不能伪造这些阶段的结果。

事后只读核对原始响应发现模型没有遵循现有指令：

- 首轮跳过search/get，尽管请求中明确给出来源缺口与investigate_or_stop。
- 重复在statement和amounts中展开四指标base/current/change；输出三条完整claim并开始第四条，与Prompt优先简短结论和1200总预算要求不符。
- F_net_profit拟引用“归属于上市公司股东的净利润”，实际原文是“五、净利润（净亏损以‘-’号填列）”对应项目。不能用相同金额将口径替换。
- E07_28拟引用涉及“销售回款增加及收到的政府补助增加”，原始证据为销售商品和提供劳务收到的现金增加、收到其他与经营活动有关的现金增加；没有这段政府补助披露。模型是从不可见原文的目录/金额推造了引文。
- 完整可见claim中的accounting_links均为空，没有观察到历史那种非空关系；但输出整体不完整且Validator未执行，不能记为会计关系验收通过。部分边界语言保留“未量化贡献”，其他“完整勾稽与披露效力”等表述无本轮来源支持，也未被程序评判。

以上是审查者对保留文本及输入的比对，不是伪造的checks。程序准确拒绝了截断响应，没有把不合规结果放行。现有证据支持“本次模型未遵守已传递规则”，不支持认定任务缺失或上下文未传递是新程序缺陷，也不足以从一次失败证明某一Prompt句子是唯一原因。结构化输出当前仅约束JSON模式，并不能强迫模型先工具调查或保证文本在预算内完成。

最小后续建议（本轮不实施）：以本次原始请求/响应增加离线回归，专项分析首轮action约束和冗余金额生成；评估如何在不扩大数据/预算、不放宽核验的前提下更可靠地约束当前阶段可选动作及紧凑输出。不能仅加Token上限或自动重试，新的开发或真实调查须另行授权。

## 6. 终止与费用

原始结果：simulation=false，llm_called=true，status=validation_failed，termination_category=system_or_decision_error，stop_reason=invalid_decision_or_tool_error，errors=[incomplete_response]。这是模型决策响应不完整，不是Validator规则通过或业务合理stop，也不是五次请求/累计Token预算耗尽。evidence_gap=null保持原样；来源缺失及全部未完成任务实际存在evidence_progress、task_evidence_gaps和unresolved_task_ids中，不把响应错误改写为证据不足。

实际usage：3358输入+1200输出=4558 Token，缓存命中0。调用前预留4.8477696元，usage原价核算：(3358×0.8+1200×2)/1000000=0.0050864元。cost_control.accounted_cny记录此值，status=usage_priced_not_invoice；顶层cost=null/cost_status=unknown仍表示服务商实际账单未知，未篡改。免费额度实际扣减与实际人民币扣费未查询，不能宣称实际扣款0元，也不能把预留当作已扣费。

## 7. 与11月2日对照

实际读取旧result/checks，确认旧3请求、2工具、10932 Token及11条错误；旧资料前后哈希未变。

|检查项目|11月2日旧运行|本轮真实运行|
|---|---|---|
|调查任务|空|五类生成，全部pending|
|检索F_net_profit|否|否，首轮即截断|
|检索现金流证据|是|否|
|模型请求|3|1|
|工具调用|2|0|
|Explain完整|是，786输出Token|否，首轮1200输出Token截断|
|净利润口径|错误|响应可见引文仍混淆为上市公司股东口径；未进入Validator|
|引用资格|不合格|未检索，eligible为空；未进入Validator|
|会计关系|不合格|可见完整claims为空links；整体未验收|
|支持边界|过度归因|可见部分有限定但有推造披露，整体未验收|
|最终状态|validation_failed|validation_failed / system_or_decision_error|
|Token|10932|4558|
|费用|未知|usage原价0.0050864元，账单未知|

## 8. 实际工件与完整性

运行目录：`outputs/agent_acceptance/20261113-authorized-9234f80f61/live/20261113T063200-e1d5e7a2bd/`。

已保存authorization.json、source_audit.json、code_hashes.json；investigation下保存plan.json、input.json、task_progress.json、events.jsonl、decisions/01.json、result.json、manifest.json。根目录另有execution_binding.json、preflight_summary.json、console.log、completion_audit.json、audit_files_sha256.json。decision保存脱敏请求、模型原始最终响应文本、usage、request ID、费用账本及传输诊断；未保存Authorization Header或Key。敏感凭证模式扫描无命中，不表示进行了密钥内容比对。

完成审计确认：所有受保护源码/Prompt/测试及11月2日历史文件SHA-256未改变；本轮input digest与执行绑定一致；task_progress与result相同；只有1份新一次性授权和1份真实决策。原始输出未修补，未执行阶段文件不存在。前一维护轮全量360测试通过属于离线成绩，本轮没有拿它代替真实成功。

最终：**真实自动验收未通过，人工金融复核未进入。安全停止完成。** 本次唯一授权已使用，不发起第二轮，不自动重试、不修改代码，不commit/push，等待下一步指令。
