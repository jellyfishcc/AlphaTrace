# 2026-11-03 Agent证据链与Explain前置检查

## 结论与范围
采用路线B：本轮search/get审计是引用资格的必要条件；目录、初始事实和证据ID不授予原文引用资格。新增核心事实来源覆盖和解释提交前置检查，未放宽原Validator。未调用真实模型、未读取Key、未修改原始日志和模型输出，未commit/push。

## 原始调查逐轮核查
实际读取指定目录input.json、plan.json、events.jsonl、decisions/01—03.json、analysis.json、checks.json、result.json，并解析每轮request.messages。

| F_net_profit状态 | 第一轮请求 | 第二轮请求 | 第三轮请求 |
|---|---|---|---|
| 系统Prompt包含该ID/原文 | 否/否 | 否/否 | 否/否 |
| 用户消息证据目录包含ID/元信息 | 是 | 是 | 是 |
| initial_facts包含净利润可信金额与该ID | 是 | 是 | 是 |
| initial_facts.retrieved_source_quotes含该原文 | 否（空） | 否（空） | 否（空） |
| queried_evidence含该原文 | 否 | 否 | 否 |
| 本轮search/get审计已取得 | 否 | 否 | 否 |

所以不能说F_net_profit不存在，也不能说其ID完全未进入上下文；确切结论是**授权包和每轮模型目录中存在，模型未获得其原文且没有本轮工具检索资格**。
第一次search通过metric_id=operating_cashflow先过滤related_facts，返回五条现金流相关证据，无F_net_profit。第二次get仅读取E07_28。第三次模型自行引用F_net_profit，触发过滤后Validator的“引用不存在的证据”。这个错误指检查载荷中没有该证据，不表示原授权输入不存在。

## 实际代码路径与根因
agent_live.main直接构造signals=[authorized_goal]、investigation_tasks=[]，没有调用investigation.prepare_investigation生成任务；空任务并非工具或模型清空。investigation.py本身能从计算信号生成问题，但该真实入口未接入。agent.investigate从tasks提取questions，所以真实上下文questions也为空。
qwen_decider.context将目录与initial_facts金额提供给模型，原文只从已search/get集合挑选；net_profit的retrieved_source_quotes一直为空。第一轮只查operating_cashflow是模型动作，代码并没有强制这个metric_id。
旧progress只要read_ids非空就设置next_step=explain_or_stop，并没有“两个核心指标均覆盖”门槛。check_action检查Schema、外发白名单等，但不检查核心来源覆盖。agent.investigate在explain时才将payload.evidence过滤为seen；stage3.validate随后按该子集查找引用、核对原文、金额、口径等。analysis_contract继续检查关系/长度，source_contract检查原文哈希来源；report_check是独立结构化报告核验路径，并非此次Agent引用资格入口。本轮不修改这些Validator。
额外发现E07_28.related_facts包含net_profit，但原文只有现金流变动披露。因此不能仅凭related_facts标签或“读过任意证据”算作净利润核心事实已覆盖。

## 集合规则（路线B）
- authorized_evidence_ids：授权载荷中可访问的证据目录。
- provided_evidence_ids：独立初始提供的原文；本协议未提供此入口，恒为空，不将initial_facts金额误标为原文。
- discovered_evidence_ids：本轮search返回的ID。
- retrieved_evidence_ids：本轮search返回原文或get取得的ID并集。现有search确实返回文本，故无需额外强制每个命中再get；get可直接按授权目录ID读取。
- visible_evidence_ids：本轮请求实际携带的queried_evidence文本及initial_facts.retrieved_source_quotes；它与完整检索账本不同，历史详情裁剪不会伪造或抹去检索审计。
- eligible_evidence_ids：retrieved与授权范围及verified_evidence来源校验的交集。
- cited_evidence_ids：候选analysis实际引用的ID。必须属于eligible，随后仍需通过原Validator逐字、页码来源、金额和口径等全部检查。

原文初始提供即直接获引用资格的路线A不适用。本轮不会为满足测试而增加这条权限；“符合provided规则的初始证据可引用”条件在当前协议不可成立。已测试初始事实来源不被伪装为provided或retrieved。工具取得的原文后来出现在initial_facts.retrieved_source_quotes时，其来源仍是工具获取，而非初始提供。

## 修改方案与文件
- 新增tracelab/evidence_progress.py：统一集合、core覆盖、引用ID资格及claim涉及指标的来源覆盖。核心事实覆盖使用已核验fact.evidence_ids与eligible交集，而非宽泛related_facts。接受该事实绑定的任一合格来源，不强迫读取全部白名单。
- tracelab/agent_live.py：真实计划明确core_metric_ids=[net_profit,operating_cashflow]；仍不扩大任务或工具协议。
- tracelab/agent.py：每轮注入覆盖进度；模型提交explain后、进入完整validate之前写evidence_precheck.json。核心缺失、引用不合格或所提指标无事实来源时返回validation_failed并保存结构化evidence_gap及explain_blocked事件，绝不改称合理stop，不自动重试。最终结果保留覆盖审计。原无source_contract的旧Mock演示路径继续使用原Validator；真实Qwen载荷必须经过LocalFacts及来源核验，不能借此绕过新检查。
- tracelab/qwen_decider.py：基于授权事实/证据副本计算同一覆盖进度并传给模型；missing_core_metric_ids非空时提示现有search/get补齐，末轮提示stop_only。仅补齐来源不保证解释内容成立。
- prompts/agent_decision_v1.txt：明确目录/初始金额/工具原文的区别，缺核心证据先查、无法查则说明范围和缺口后stop。
- 新增tests/test_evidence_provenance.py：真实历史响应逐字Replay及明确标注的合成成功分支。

旧历史空tasks计划通过已知目标中的“净利润”和“经营现金流”识别双核心要求，当前live入口则使用显式字段。该兼容识别不是任意自然语言目标解析器；新业务目标应显式设置core_metric_ids。claim涉及cash_2/cash_6时也检查其事实来源是否已获取，但本轮不修复金额关联或accounting_links。

## 行为与测试
原始三轮模型响应文本、finish_reason和usage原样用于Replay，不修改历史analysis。新路径在第三轮precheck识别missing_core_metric_ids=[net_profit]、ineligible_citation_ids=[F_net_profit]并失败；记录evidence_gap，不补造stop。
合成分支在同样search/get后追加现有get(F_net_profit)，再提交简短待验证结论：4请求、3工具，通过完整validate到pending_human_review；这是明确人工构造的离线测试，不是修补真实输出或宣称Qwen成功。另测通过search(net_profit)取得来源也有效。
新增9项：逐轮可见性、原始Replay拒绝、补取核心后完整验证、search取得来源、遗漏现金流即使结论省略也阻断、未授权引用、合理stop保留范围/缺口、初始来源不伪装检索、哈希篡改拒绝。
测试命令python -X utf8 -m unittest discover -s tests -v；TEMP/TMP为工作区tmp，PYTHONPATH=tmp/test-deps。日志tmp/evidence-provenance-tests.log；最终数量见末尾。

## 限制与验收边界
核心证据覆盖是必要条件，不是经营因果充分性证明；引用文本是否支持结论仍需原Validator与人工复核。早交explain会失败停止，不替模型纠正或偷偷重试。缺证据时可在剩余5请求/4工具内由模型选择search/get，或合理stop；没有无限循环。当前模型预算与Token控制不变。
本轮未处理E07_28换行、现金分项金额关联、自由文本数字、会计关系、长度或因果判断。原始失败样本因此不会被包装为全面成功，真实模型是否遵循新进度提示仍未测试。新的代码/Prompt使历史预检绑定失效，后续真实执行需新的预检及明确授权。
原始审计目录全部文件与其audit_files_sha256.json匹配，历史样本未改动；既有未提交修改、两个PDF和此前报告均保留。

## 预检兼容修正及范围外测试问题
tracelab/agent_preflight.py的合成Replay改为search(net_profit)→get(F_operating_cashflow)→explain，相应模拟引用指向该已读取原文，仍是3请求、2工具。该轨迹补齐两个事实的绑定来源，不更改真实历史轨迹或Validator，也不修改原有测试断言。
第一次全量258项：255通过、2失败、1错误。一个失败来自旧预检模拟轨迹缺少现金流事实绑定原文，已修正；另两个是原test_free_tier中的正确配置发送、超时/缺usage用例遇到price_reverification_required，因为当前北京时间2026-11-03，而既有价格核实日期仍是2026-11-02。本轮不修改费用保护或范围外测试来隐藏它们。最终结果见下方。

## 最终测试与验收结论
执行完整指定命令，共258项：256通过、1失败、1错误、0跳过。新增9项证据专项测试全部通过，预检模拟来源覆盖兼容测试也通过。Ran 258 tests in 188.509s。剩余两项均为前述既有费用测试受跨日price_reverification_required影响，未放宽保护。**证据专项离线回归通过；全量测试未全部通过，不能宣称整体验收通过。**
最终日志：tmp/evidence-provenance-final-tests.log，SHA-256：`392cc6cced3278a5f5a599dfae91beb6360f7b2c09940ea515ee69cf28edee57`。git diff --check通过。本轮不继续修复范围外问题，不进行真实调用，等待下一步指令。
