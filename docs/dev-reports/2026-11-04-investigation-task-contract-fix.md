# 第一阶段：调查任务与证据契约

日期2026-11-04，基线8bfb016717a19dad358d4778cc29b82cc4987aad，main。开始前实际阅读 agent-root-cause-audit 报告并重读当前源码。原审查报告和output/两个PDF原样保留。本轮只修改内部任务契约、规划接入及任务审计，未调用模型/API、未读取Key、未commit/push。

## 根因与最小兼容方案

agent_live.main原来直接写authorized_goal及空investigation_tasks；investigate的matching or tasks只筛选已有条目，不生成任务。原规划器prepare_investigation能生成利润层级及背离问题，但直接导入它的全量profit_chain会包含本次未授权指标，reason还与authorized_goal不匹配。

采用内部task_contract_version=v1扩展计划对象，不改SCHEMA_V2。prepare_scoped_investigation先从LocalFacts取得已核验且已限定范围的事实，将已有change字段适配为原prepare_investigation所需metrics，复用其异常信号判定，不重新计算金额。只保留检测到的signal ID用于审计，随后生成当前净利润/经营现金流业务的五个必需任务。不复制全量profit_chain、不改变payload、不增加工具授权。

这是一项当前业务目标的范围内适配，不是通用自然语言任务规划器。原prepare_investigation及其原公式/问题生成逻辑不变。

## 修改文件和函数

- tracelab/investigation.py：新增prepare_scoped_investigation、select_tasks。
- tracelab/agent_live.py：真实执行路径改调用上述范围内规划入口，不再生成空任务。
- tracelab/evidence_progress.py：新增investigation_task_progress，复用原evidence_progress及LocalFacts；原核心覆盖及explain_precheck规则未改。
- tracelab/agent.py：使用select_tasks选择任务；v1计划每轮在内部state记录任务进度，结束后写task_progress.json并在result增加investigation_task_progress。原status、stop_reason、evidence_gap的生成与转换完全不变。
- tests/test_investigation_tasks.py：新增14项测试。

未修改qwen_decider、Prompt、stage3、source_contract、analysis_contract或费用保护。任务进度暂不新增为模型上下文字段；既有questions路径会接收任务问题，但Qwen上下文仍保留原最多四条问题限制，第五个缺口维度在计划和审计中完整保存。如何在模型中呈现完整进度属于后续阶段，本轮未提前修改。

## 五类任务与状态

所有条目有id、kind、required、reason、questions、fact_ids、candidate_evidence_ids、required_sources及初始pending。候选ID来自当前payload范围，只表示候选，不授予引用资格。

|任务|answered判定|未解决状态|
|---|---|---|
|net_profit_fact|LocalFacts验证通过，名称必须净利润，有两期、scope/currency及base/current/change元字段，且本轮取得fact绑定的合格来源；返回可信事实快照|未取得来源pending；事实缺失/不可信或元数据不完整evidence_gap|
|operating_cashflow_fact|同上，名称为经营活动产生的现金流量净额|同上；不以现金流入分项冒充净额|
|cashflow_disclosure|合格且本轮取得E07_28、现金流事实可用、同比口径且原文含主要系；返回原始quote与仅为披露的支持边界|未检索pending；授权无该披露或支持不足evidence_gap|
|profit_cashflow_divergence|本阶段不自动判answered；两个事实或披露并不构成调节/经营解释|尚无相关来源pending；取得来源仍缺可信调节解释判定时evidence_gap，列明缺少调节资料与经营解释|
|remaining_evidence_gaps|本阶段不把记录缺口等同于解决缺口|汇总其他未回答问题；未调查时pending，已有缺口时evidence_gap|

状态由本地核验结果重建，不相信输入task.status或模型自行宣称完成。task_progress记录eligible_evidence_ids、missing_fact_ids、candidate_evidence_ids、missing_evidence_types、unresolved_questions、reason、answer和budget_exhausted。候选与合格来源明确分离。

answered对事实任务只表示该事实核验完成，对披露任务只表示已取得年报的定性披露，不代表经营因果成立；仍须后续原Validator验收模型结论。背离原因不确定时不能因为两个指标已取得而关闭缺口。

空tasks返回planning_gap=true、complete=false，避免all([])导致真值误判。预算耗尽将未完成条目标为evidence_gap并保留原reason、补budget_exhausted=true；已经核实的事实不撤销。预算标记不代表已穷尽所有资料，未将预算停止伪装成证据真实性结论。

## 信号选择与范围

五个任务reason统一为authorized_goal，required=True。异常检测profit_down_cashflow_up单独保留detected_signal_ids，避免误用两种signal ID。select_tasks保留所有required任务再取匹配任务；没有required的旧计划仍使用原有matched-or-all语义。净利润基础任务不会因为异常任务匹配而被筛掉。

没有增加现金流桥接、关系、事实或原文，不导入cash_7/cash_15/cash_16。原本5模型请求、4工具、1200输出及其他预算不变。独立任务契约不新增模型动作、不自行搜索、不自动重试、不改变explain/stop终态。

## 离线验证

新增14项专项已通过：非空五任务、authorized_goal匹配、必需基础任务保留、未检索不可回答、净利润合格来源与事实联合判定、现金流/披露不能完成背离、空关系不变、空计划不完整、预算保留缺口、三种状态、篡改名称拒绝、实际Replay写审计并保留stop、真实入口全Mock接入五任务、真实编排4工具上限及未解任务。

真实入口测试中prepare、QwenDecider、LiveBailianTransport、investigate均为Mock，网络禁止；临时目录仅保存synthetic-offline测试工件，不是新的真实调查授权。其他集成测试使用ReplayTransport，历史input只读，合成动作明确作为测试，不修改历史日志。

全量：308项，306通过、1失败、1错误、0跳过，146.452秒。失败test_timeout_or_missing_usage_preserves_reserve_and_stops与错误test_correct_model_region_and_free_tier_send_once均为既有price_reverification_required日期问题；未修改费用保护，无新增回归。

四项独立回归：证据链9/9、现金流关系15/15、引文11/11、自由数字10/10全部通过，均0失败、0错误、0跳过。第一阶段专项14/14通过，离线阶段验收通过；全量不宣称全绿。

使用 python -X utf8 -m unittest discover -s tests -v，子进程TMP/TEMP为项目tmp，PYTHONPATH使用已有tmp/test-deps。日志tmp/task-contract-full-tests.log。git diff --check通过。

## 限制与后续边界

本轮契约保守：尚未实现可信的背离解释自动评估器，故不提供自动将第四类任务标为answered的路径；第五类只汇总缺口，不把记录缺口标为业务完成。因此当前样本完整任务complete仍false，即使前三类已答。不得用此契约声称整个调查已解决。

披露任务仅支持当前既有E07_28同比披露，不做泛化语义评估。未来新问题、新来源需要明确受审查任务规则，不能从related_facts标签自动认定解释成立。

任务状态暂不用于阻断Explain或改写最终状态，现有核心前置检查仍照常；完整循环、支持边界Validator与Prompt改进属于后续阶段。当前阶段不新增这些能力。

完成后停止，不进入第二阶段。
