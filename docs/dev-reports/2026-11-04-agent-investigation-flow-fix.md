# 第三阶段：Agent 调查流程与终止状态修复

日期：2026-11-04。分支 main，HEAD `8bfb016717a19dad358d4778cc29b82cc4987aad`。第一、第二阶段已有未提交修改完整保留。本轮未调用真实模型、未读取密钥、未联网、未 commit/push；两个原有 PDF 仍在 output/pdf。

## 1. 实际检查与根因

已读取根因审查、第一阶段任务合同、第二阶段语义边界三份报告及现有 agent、evidence_progress、qwen_decider 和专项测试。实际解析唯一授权调查目录 `outputs/agent_acceptance/20261102-authorized-3409dac866/live/20261102T143227-e1ab7ac1f3/investigation/` 的 input、analysis、checks、events、result、plan 和 decisions/01–03。

历史记录确为 search → get → explain，原 checks 有 11 条错误；result 为 validation_failed，但 stop_reason 为 explanation_submitted。原 plan 任务为空。当前第一阶段已生成并审计五类任务，然而任务进度尚未传给模型，也未影响 Explain 准入。旧前置检查仅判断核心来源和引用资格；终态 stop_reason 无法区分提交动作与校验结果。第一阶段结束审计仅看是否用满轮次/工具数，会将恰好在最后预算内成功提交的结果也标记为预算耗尽。

## 2. 本轮修改文件与函数

- `tracelab/evidence_progress.py`：扩展原 `explain_precheck` 的可选 task_progress 参数；新增 `task_decision`，从既有台账生成下一步提示，不改变五类任务生成及状态计算规则。
- `tracelab/agent.py`：`investigate` 每轮将现有任务台账转换为决策提示，传入原 Explain 前置检查；保留提交动作，新增终止分类及未解决任务审计；Validator 拒绝时使用 explanation_validation_failed，原错误保持；按实际预算终止原因给未完成任务标记预算耗尽。
- `tracelab/qwen_decider.py`：`context` 提供简短任务状态、未决问题、候选证据 ID 及下一步提示。原已回答问题不再重复发送；完全相同的证据原文仅保留 initial_facts.retrieved_source_quotes 一份，queried_evidence 明确引用该位置。未改变原文或资格。`decide` 仅压缩 JSON 分隔符排版，仍使用原请求字节检查。
- `tests/test_investigation_flow.py`：新增 17 项离线流程测试，成功响应明确为合成数据，历史响应只读原样 Replay。
- 本报告。

没有修改 Prompt、SCHEMA_V2、规划器、第一阶段状态评估器、语义 Validator、原财务/金额/引文规则、费用保护或历史调查文件。Git diff 中 agent/evidence_progress 还包含此前未提交的第一阶段代码，不能全部算作本轮新增。

## 3. 有限转换与 Explain 准入

|条件|下一步与结果|
|---|---|
|基础事实或披露待查，存在范围内候选来源，且有工具及后续决策预算|investigate_or_stop；允许在原循环内执行合法 search/get，再更新台账|
|两项事实与披露任务已回答|limited_explain_or_stop；不要求第四、第五类任务 answered|
|必要来源缺失且没有可继续的候选或预算|stop_with_evidence_gap 提示；合法 stop 保留实际缺口|
|提前 Explain，核心来源/披露缺失、规划为空、引用无资格或未记录未决问题|原 explain_precheck 拒绝，记录详细缺口并结束本次运行，不伪造证据或重试|
|前置通过|进入原完整 Validator，金额、引用、会计关系及语义规则照常执行|
|Validator 通过|pending_human_review；不等于金融业务结论获批|
|Validator 拒绝|validation_failed，保留具体 errors，终止分类 validator_rejected|

前置检查复用既有函数；对 v1 台账要求两项事实及披露三类基础任务 answered，第四、第五类允许 evidence_gap/pending。存在未解决任务时要求 analysis.questions 非空。完整缺口内容独立保存在 task_progress 与 task_evidence_gaps，模型没有权力覆盖任务状态。具体问题的自然语言对应及支持范围仍交原 Validator 和人工复核，不声称仅凭 questions 非空即证明语义充分。

没有添加 Explain 失败后的再请求路径。现有 QwenDecider 有 failed_run_no_retry 与动作保护，本轮采用用户允许的安全失败方案：正常工具序列可以继续调查；模型已经提前提交 Explain 时立即记录拒绝和缺口，不能在同次运行无限改写。提示不是替模型执行工具，更不保证模型必然服从。

## 4. 终止分类与兼容

新增 termination_category：human_review_required、insufficient_evidence、budget_exhausted、explain_precheck_rejected、validator_rejected、system_or_decision_error。新增 submission_action 区分提交动作；原 status/errors/manual_review/retrieval_audit 等字段保留。成功提交可保留旧 explanation_submitted 动作原因，但不能据此推断核验成功，需结合 status 与 termination_category。

明确的轮次、工具、请求、Token、输入字节预算及保留证据工具预算错误归入 budget_exhausted。工具、模型、结构错误使用 system_or_decision_error，绝不标为正常业务成功。Validator 错误不转换成 evidence_gap；任务的实际未解决问题单独保留。合法 stop 保留模型理由，无法证明它声称的每一个自然语言停止理由真实，需结合台账复核。

不再单凭计数达到上限标记预算失败：第五次请求成功提交的合成测试仍进入人工复核，未解决背离任务不被标为因预算失败。

## 5. 预算与上下文

沿用真实入口 5 请求、4 工具、1200 输出 Token、60000 累计 usage 目标、90 秒、零重试、30 元辅助保护及价格日期检查。未提高任何限额；实际 Token 目标的既有限制不变，不能承诺事前精确限制单次输入 Token。

开发测试曾发现新增任务摘要使历史第二轮超过原 16000 字节上限；通过同文去重、避免重复问题和 JSON 紧凑排版解决，未扩大输入预算。较长其他证据仍可能触发 input_budget_exhausted，此时发送前停止并记录预算分类。候选集合排除已具备资格的来源；既有重复动作、已有事实查询保护继续生效，不强制执行五次工具或绕过预算。

## 6. 离线验收

历史原始三轮响应原样 Replay：3 次模拟决策、2 次工具，仍为 validation_failed，explain_precheck_rejected；F_net_profit 缺失/引用无资格继续被拦截，不修补原始响应。此 Replay 不代表真实 Qwen 通过。受限解释合成路径经过完整 Validator，保留第四、第五类缺口及人工复核。

新增 17 项覆盖：提前 Explain 无重试、正常有限继续调查、净利润来源更新、双事实不等于背离解释、受限解释送 Validator、第四/第五类缺口不永久阻断、合法 stop 保留缺口、缺失 questions 拒绝、Validator 错误分类、预算停止、非法响应异常、重复工具拒绝、原始历史 Replay、空规划拒绝、无候选时停止提示、最后一请求成功不误标预算失败。

|测试组|通过|失败|错误|跳过|
|---|---:|---:|---:|---:|
|第三阶段新增|17|0|0|0|
|第一阶段|14|0|0|0|
|第二阶段|12|0|0|0|
|证据链专项|9|0|0|0|
|现金流关系专项|15|0|0|0|
|引文匹配专项|11|0|0|0|
|自由文本数字专项|10|0|0|0|
|全量|335|1|1|0|

最终运行 `python -X utf8 -m unittest discover -s tests -v`：337 项，141.353 秒。日志 `tmp/flow-full-final.log`。测试进程使用现有项目 tmp 作为 TMP/TEMP、tmp/test-deps 作为 PYTHONPATH，避免宿主临时目录权限和依赖问题。

既有失败：test_timeout_or_missing_usage_preserves_reserve_and_stops；既有错误：test_correct_model_region_and_free_tier_send_once，均由 price_reverification_required 引起。未改费用保护，无新增回归。git diff --check 通过。

## 7. 结论及限制

第三阶段离线验收通过；全量不是全绿。任务状态现在影响正常决策提示及 Explain 准入，并能区分提交、拒绝、预算、异常及人工复核。没有实现任意复杂经营解释的自动证明，也不自动将背离任务标成 answered。只支持第一阶段已有 v1 任务契约，旧计划保持原来源检查兼容。前置失败后安全结束，不自动补救重试；未知业务问题及新增来源不在本轮泛化。

报告保存后停止，不进入第四阶段，不进行真实调查，不提交或推送。
