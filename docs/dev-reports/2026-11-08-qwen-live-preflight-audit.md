# 真实 Qwen 调查验收前置检查

实际检查日期：2026-11-13（Asia/Shanghai）。按请求保留文件名中的2026-11-08。最终结论：**BLOCKED**。本轮只做审查，未进行真实模型/API连通性请求，未读取密钥值，未更新生产价格日期、代码、测试、Prompt或历史资料，未commit/push。公开网页查询不涉及模型Endpoint。

## 1. Git与五阶段版本

main，HEAD `27a9a4b81c47a3407537278e9ffcb5ae4519db89`；第四阶段06720f7、第五阶段27a9a4b已在当前历史中。已跟踪工作区及暂存区没有改动；开始时output/yang、yang_sample、yang_v2及三个求职/就业材料zip未跟踪，与本次无关，未读取或修改内容。两个原PDF保持原状。

本地HEAD与origin/main引用比较为0/0；本轮未fetch或访问GitHub，因此只证明本地远端跟踪引用一致，不声称实时远端已核实，也没有假定最近Push成功。

读取六份指定审查/开发报告并结合当前源码核实：agent_live.main接prepare_scoped_investigation生成五类任务，agent.investigate复用任务状态与explain_precheck，stage3.validate接semantic_boundary，来源资格仍route B，会计关系仅导出授权且verified的直接关系，终态分类与任务审计保持。QwenDecider.PROMPT指向当前prompts/agent_decision_v1.txt，不使用历史请求Prompt。当前Prompt SHA-256：`490c738cf2c7951c1e862fd17839b67cf8866d60e87e570709d0cbbebf92ea20`。本轮全部tracelab源码和Prompt前后哈希相同，详情保存在tmp/nov13-preflight-evidence.json。

## 2. 模型配置：仅检查存在性与非密钥配置

真实入口显式model=qwen-plus，Transport配置也使用body中的这个模型，不是qwen-plus-latest。当前非密钥模型环境配置为空，默认仍qwen-plus。

DASHSCOPE_BASE_URL来自process，对应Endpoint：
`https://ws-6sp1nti4y4d07vun.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions`。
与cost_budget.ENDPOINT精确匹配，北京地域、URL中的Workspace均一致。密钥名称DASHSCOPE_API_KEY在进程环境存在，Windows用户Environment注册表有非空值元数据。只检查变量名与注册表长度/类型，未取得或输出密钥内容；未调用bailian.configuration读取实际Key。存在性不能证明密钥有效或所属Workspace，须用户在对应控制台重新确认；不能靠URL推断密钥归属。

Live必须显式authorized=True，默认CLI/Replay不使用真实传输；本轮只运行Mock/Replay。旧execution_binding或2026-11-02授权不产生本次授权。claim_once以排他创建记录阻止同一输出根下重复授权ID；调用者仍可能更换输出目录/ID，所以不是平台级权限控制。本轮没有生成任何新已批准授权记录。

## 3. 官方定价与日期关卡

2026-11-13查询[阿里云官方qwen-plus模型页](https://help.aliyun.com/zh/model-studio/qwen-plus)。北京、非思考模式、实时调用，人民币元/百万Token：

|单次输入档位|输入|输出|普通缓存命中输入|
|---|---:|---:|---:|
|≤128k|0.8|2|0.16|
|128k～256k（左开）|2.4|20|0.48|
|256k～1m（左开）|4.8|48|0.96|

页面称qwen-plus功能等同qwen-plus-2025-12-01，非思考最大输入997952、最大输出32768，上下文1000000。代码单次输出进一步限制1200。页面另有思考、Batch及显式缓存价格，本次body禁用思考/stream，不启用Batch或缓存创建等附加功能；不得套用优惠价。CostLedger不抵扣缓存折扣，因此按原价保守计量。

网页价格与cost_budget.price一致；税务、账户资源包/折扣/最低消费及是否存在其他账户支出未由公开模型页证明，不假定含税或承诺账户账单绝对上限，须在控制台确认。

**生产硬阻塞**：cost_budget.VERIFIED_DATE='2026-11-02'；check_live_price使用北京时间日期严格相等判断，不是7日或30日有效期。2026-11-13调用该纯检查函数实际返回price_reverification_required。LiveBailianTransport.send在guarded_send预留及call_api之前执行此检查，当前无法发送。此次网页核实是审查证据，不自动修改生产记录。

## 4. Token与最坏费用：分开证明

真实入口BUDGET为5请求、4工具、1200输出、60000累计usage目标、90秒、16000输入字节。90秒是底层套接字操作超时，不保证整个调查总墙钟时限。零自动重试。

16,000字节不是可靠Tokenizer上界，代码size+256只是日志粗估，不用于证明真实输入Token。当前没有本次请求精确Tokenizer计数。但费用预留使用官方模型容量上界MODEL_INPUT_CEILING=997952，这个上界独立于字节估算，且本次公开资料仍支持此值。

按该容量上界、最高档、不计缓存优惠：

- 单次：997952 × 4.8 / 1000000 + 1200 × 48 / 1000000 = **4.8477696元**。
- 5次独立上界：**24.238848元**，低于30元。即使不借助60000目标，固定模型和已核实计费参数下也可给出此原价Token费用上界。
- 若实际总Token确实≤60000、总输出≤6000，条件费用上界为(54000×0.8+6000×2)/1000000=**0.0552元**。但现有usage_target不能事前保证60000，因此此小数不能作为安全预留依据。

容量上界证明依赖供应商执行公开模型限制及计费语义，不是平台账单担保；若模型别名/价格或额外计费规则变化，应重新核实。当前生产日期未满足，即使算术上限低于30元也不能READY。

历史blocked_cost_input_bound是旧费用阶段诊断，当前源码不再用此状态。strict_bound模式以997952+1200对60000检查会在发送前token_budget_exhausted；用户确认免费额度模式使用usage_target，达到累计60000后阻止下一次。一次响应可跨过剩余额度，程序记录actual_token_budget_exceeded并终止，不能伪称严格总Token上限。免费额度模式没有解决精确分词问题，而是改变了Token目标执行语义。

## 5. 30元辅助保护、异常和账户风险

CostLedger.reserve先校验模型容量/输出界、5请求次数、累计accounted+本次最大费用≤30，再发送；账本同时保留reserved和accounted。settle用服务usage及请求ID核算，输入/输出越界拒绝。usage缺失、超时或异常保留本次预留、置unknown，后续cost_unknown_stop。QwenDecider的failed_run_no_retry和usage检查阻止继续请求；没有自动重发失败请求的循环。403 AllocationQuota.FreeTierOnly被专门识别并停止。

账本为单次串行调查的内存对象，不是跨进程、跨Key或账户级消费额度。进程崩溃时服务端可能已计费而本地最终usage缺失；正常入口一次性授权阻止原调查重启重用，但不能证明账单已结算，也不能约束用户其他程序。本地日志不能当作供应商账单。

[官方免费额度规则](https://help.aliyun.com/zh/model-studio/new-free-quota)说明用完即停开启后额度耗尽返回403 AllocationQuota.FreeTierOnly；控制台余量有更新延迟。本项目FREE_TIER保存的是2026-11-02人工确认：总量1000000、当时剩余958750、2027-01-15到期、北京Workspace匹配、free_tier_only=True、api_verified=False。这不是2026-11-13账户状态，未通过API核实。需用户重新确认当前余量、到期时间、开关生效状态、密钥归属和计费方式；本轮不假定0元实际扣费。

## 6. 事实及资料快照

当前重新加载`outputs/final_revision/20261017T093152-d80de1cefa`，比对历史execution_binding.source_audit中的61项release_hashes：全部一致，source_audit相等，完整可信事实45项。使用既有project收窄后，payload与2026-11-02调查input.json完全相同；当前规划器生成5任务。

计划候选范围仍为：facts net_profit、operating_cashflow、cash_2、cash_6；evidence F_net_profit、F_operating_cashflow、F_FINAL_cash_2、F_FINAL_cash_6、E07_28、E18。这里仅确认范围可确定，没有授予本次外发权。未把完整PDF、Word/Excel内部附件加入外发输入。来源一致不表示经营解释已完成。

## 7. 完全离线测试及两个失败根因

运行现有12个模块共148项：103项四阶段/历史专项、3项跨文件端到端、13项cost_budget、11项free_tier、18项qwen_decider。146通过、1失败、1错误、0跳过，用时5.359秒。日志tmp/nov13-preflight-tests.log；统计tmp/nov13-preflight-tests.json。不是重跑全量355项，不将历史全量成绩当本轮结果。

测试外层封锁socket.socket/socket.create_connection与实际bailian.configuration；测试所需配置和HTTP函数使用既有局部Mock合成数据，未读取真实Key。第一阶段入口Mock测试打印starting_authorized_investigation只为模拟日志，不是真实调查。

- test_correct_model_region_and_free_tier_send_once：原希望到达Mock call_api一次，但当前日期不等于VERIFIED_DATE，在check_live_price即抛DecisionFailure，构成ERROR，尚未发送。
- test_timeout_or_missing_usage_preserves_reserve_and_stops：第一次本应模拟超时/usage缺失，实际被日期检查先挡住，未建立unknown账本；第二次期望cost_unknown，仍得price_reverification_required，构成FAIL。不是证明生产超时后会继续计费调用。

最小建议（未实施）：测试中以受控时钟固定到已定义的价格核验日验证模拟正常/超时分支，另独立测试不同日期一定阻断且发送次数为0。生产日期只能在真实价格及适用条件复核后，经单独授权更新；不得为测试全绿自动改为今天。

## 8. 硬性检查表

|项目|检查结果|证据或阻塞原因|
|---|---|---|
|Git与代码版本|PASS|27a9a4b含五阶段；本地跟踪引用0/0，未实时查询远端；无关未跟踪资料保留|
|Qwen模型与Endpoint|PASS|显式qwen-plus，北京固定Endpoint精确匹配|
|Workspace与地域|USER_CONFIRMATION|URL为预期Workspace及北京；Key实际归属仅有历史人工确认|
|API Key配置存在性|PASS|进程名称存在、用户注册表非空元数据；不验证有效性|
|官方价格已核实|PASS|2026-11-13官方公开北京价格及模型容量；账户折扣/税务不在此结论内|
|免费额度及有效期|USER_CONFIRMATION|只有2026-11-02人工快照，需当前控制台确认|
|输入Token及最坏费用上界|PASS|以官方模型容量给出原价5次≤24.238848元；不宣称60000是事前硬上限|
|30元内部费用保护|BLOCKED|预留/异常保护存在，但生产价格日期检查已过期，当前真实发送不准入|
|请求、工具、超时、零重试|PASS|现有入口5/4/1200/90秒及零重试保护；60000为usage目标|
|五阶段代码和Prompt|PASS|源码调用路径与当前Prompt/回归相符|
|调查事实及证据快照|PASS|61哈希一致，范围内payload与历史一致|
|离线安全测试|BLOCKED|146/148通过；两项既有日期问题仍未通过，不宣称全绿|
|本次真实调用用户授权|NOT_AUTHORIZED|没有新授权，历史一次性授权不复用|

## 9. 最小后续事项与停止结论

最终 **BLOCKED**，优先于账户确认事项。硬阻塞位置为cost_budget.check_live_price → LiveBailianTransport.send，条件today != VERIFIED_DATE。不能通过仅在报告中声明核实价格绕过实际代码关卡。

下一步需单独授权审查并更新可审计价格核验记录（含实际执行日、模式、容量和价格），并以受控时钟改进两个测试；重新确认账户免费额度、开关、Workspace和计费适用性，再对当前commit/Prompt/资料哈希及固定预算形成新的独立授权申请。若要求60000为发送前硬性总量，则还需另行解决可靠Tokenizer/上界问题，当前模式不满足该额外要求。

所有预检结果都不构成API调用授权。本轮完成报告后立即停止。
