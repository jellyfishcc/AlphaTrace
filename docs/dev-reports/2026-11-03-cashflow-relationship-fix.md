# 现金流金额关联与会计关系约束修复

实施日期：2026-11-03；收尾核对日期：2026-11-04（Asia/Shanghai）。项目：D:/Projects/TraceLab。

## 1. 根因与本轮边界

依据上一轮 cashflow-relationship-audit 报告及真实调查 `outputs/agent_acceptance/20261102-authorized-3409dac866/live/20261102T143227-e1ab7ac1f3/investigation/` 的 input.json、analysis.json、decisions 原始记录。

真实第二条结论只声明 operating_cashflow，却列出 cash_2、cash_6 的 change，且仅引用 E07_28 的定性披露；accounting_relations 为空仍生成两条 accounting_links，并夸大为覆盖全部净额变化。已有指标关联及关系 Validator 实际已拒绝这部分错误。本轮补足模型关系上下文与金额原始来源绑定，并澄清 Prompt，未导入本地全量现金流桥接。

工作区分支 main，HEAD daf1e32f9c03c55bb6d421518f8c24be95b1dc20；开始时已有前轮未提交修改。本轮在其上增量编辑，保留其他文件及未跟踪 PDF。未 commit/push，未修改历史日志或数据。

## 2. 修改文件与行为

|文件|本轮修改|
|---|---|
|tracelab/qwen_decider.py|构造时读取已加载分析合同，筛选 verified 严格为 True、target 及全部 components 都在 ExportScope 事实集合内的关系；仅导出 target、verified 和 component/sign/effect；每次 context 明确带 accounting_relations，空时为 []。|
|prompts/agent_decision_v1.txt|追加财务事实/定性披露区别、每笔金额绑定本条指标与事实原始来源、空关系禁止 links、禁止跨层/别名推导和完整贡献夸大；change 不必逐字见于 PDF。|
|tracelab/stage3.py|保留原规则，增加每笔 amount 的事实哈希凭据、fact.evidence_ids 与本条合格引用交集、原文与来源哈希及比较口径核验。|
|tests/test_cashflow_relationship.py|新增15项离线回归，含真实响应原样 Replay 和明确标注的合成变体。|
|tests/test_stage3.py、tests/test_bailian_analysis.py|给旧模拟输入补齐 fact.evidence_ids、模拟 source_contract 及来源类型；原测试断言保留。|
|tests/test_focused_regression.py|已有模拟来源凭据补齐 facts 的摘要；历史 JSON fixture 不变，原断言保留。|

analysis_contract.py 未改；SCHEMA_V2 未改；财务计算、现金流桥接、第一项证据链实现及其测试、费用保护均未改。Git 总 diff 包含前轮工作，不应将其全部归为本次变更。

## 3. 会计关系传递规则

仅接受本地已核验合同中的 verified=True 关系；verified=False 不导出，不把它转成 True，也不凭模型或常识补关系。范围内关系保留 verified 标记，使“已核验可用”语义明确。任何未授权 target 或 component 都使整条关系不导出，不截掉部分项形成残缺公式。

空清单显式传给模型；Prompt 要求对应 accounting_links=[]。程序仍由 analysis_contract.check_contract 核对关系、分项、方向及本条指标关联，Prompt 不是唯一防线。没有读取 cash_bridges.json，也没有增加 cash_7、cash_15、cash_16；不建立传递闭包或净额别名。

关系核验信任现有本地加载合同；本轮不重新计算或扩充会计公式。合同不是模型可以提交的新事实来源。

## 4. 金额来源规则

每笔 amount 继续按 fact_id/field/unit 精确比较 Decimal，并要求 fact_id 在同条 metric_ids 内。新增要求：

1. fact 的内容摘要等于 source_contract.facts 的加载凭据，不能事后改写金额或来源绑定。
2. 同条 citations 至少包含一个该 fact.evidence_ids 中的来源；只在 related_facts 中出现不够。
3. 该证据须仍在当前校验 payload 中，通过 verified_evidence 的年报类型与摘要核验，并正确关联本 fact。
4. 引文非空且逐字出自该证据；v2 比较口径在来源允许范围内。

Agent 的检索资格仍由第一项修复先行检查；本规则不会把目录、未获取证据或初始 fact 的来源 ID 自动变成已读取原文。

对 change，数值来自已核验事实；来源可为支持 base/current 的原文，不新增“引文必须包含差额”要求。币种、单位、期间及既有来源/公式校验没有放宽。静态输出 Schema 无需新字段。

## 5. 新增测试及真实/合成区分

新增15项：原始响应原样 Replay 拒绝；只补 metric_ids 仍拒绝；两个合格来源及 change 通过；合格金额经 Agent 完整路径进入 pending_human_review；空关系拒绝 links；无 links 的定性披露通过；未验证/错分项/错方向/缺指标拒绝（subTest）；空上下文明确传递；只导出授权已验证关系且不合成；cash_16 别名拒绝；事实/证据哈希篡改拒绝；仅相关来源拒绝；错金额拒绝；跨层关系拒绝；即使相关标签经模拟绑定也不能替代 fact 来源。

真实 Replay 逐字使用已保存 response.messages 文本及原 usage，没有人工修复真实响应。成功路径和关系边界数据为测试中明确标注的合成案例，不是新的 Qwen 输出，不代表真实调查成功。真实样本首先仍被第一项前置检查拒绝，同时直接调用原 Validator 验证第二项错误继续被拒绝。

## 6. 测试环境与结果

使用 `python -X utf8 -m unittest discover -s tests -v`。仅为测试子进程配置 TMP/TEMP 到项目 tmp，并将已有 tmp/test-deps 加入 PYTHONPATH；没有安装新依赖或修改 API 环境变量。

初次专项因系统沙箱临时目录权限报错，改用项目 tmp 后解决。初次全量未带已有 pypdf 依赖，存在依赖导入错误；同时旧模拟夹具缺少新增要求的来源凭据，补齐测试凭据后通过，生产校验没有降级。

- 新增专项：15通过、0失败、0错误、0跳过。
- 第一项证据链专项：9通过、0失败、0错误、0跳过。
- 中间完整运行：271项，269通过、1失败、1错误、0跳过，179.826秒；当时发现阶段尚未收集后来追加的两项边界测试。
- 最终完整运行：273项，271通过、1失败、1错误、0跳过，210.674秒。已包含全部15项新增测试；完整输出保存于 `tmp/cashflow-final-tests.log`。除上述两项既有费用日期问题，无新增回归。
- `git diff --check` 通过。

已知两项费用日期问题均位于 test_free_tier：test_correct_model_region_and_free_tier_send_once 报 price_reverification_required；test_timeout_or_missing_usage_preserves_reserve_and_stops 预期 cost_unknown，但日期保护先返回 price_reverification_required。原因是价格核验日期仍为2026-11-02，该次测试运行日期为2026-11-03（本报告于2026-11-04收尾确认）。本轮没有改日期、冻结时钟、绕过保护或修改这些断言。

## 7. 验收边界

本轮专项离线验收通过，现有证据链专项通过。不能将全量称为全绿，也不能将 Replay 成功说成真实 Qwen 成功。后续真实调用仍需独立授权及原有价格/预算预检。

Prompt 不能确保模型永不生成错误；程序会拒绝未核验 links 和来源不足金额。自由文字因果强度及是否充分回答业务问题仍需人工复核。本轮不实现完整定量贡献桥接，不自动扩大授权范围，不处理引文换行、自由文本数字等其他专项。

未调用真实模型、未消耗免费 Token、未自动重试、未修改真实日志。完成后停止。
