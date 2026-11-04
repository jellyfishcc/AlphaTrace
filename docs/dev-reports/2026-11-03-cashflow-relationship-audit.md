# 现金流金额关联与会计关系只读审查

审查日期：2026-11-03。项目：D:/Projects/TraceLab。HEAD：daf1e32f9c03c55bb6d421518f8c24be95b1dc20；分支 main。工作区已有前几轮未提交修改和未跟踪文件，本轮保留全部现状，仅新增本报告。未调用模型、未修改 Python/Prompt/Schema/测试/数据/历史记录，未 commit/push。

## 1. 结论与审查材料

两个现金流入分项的差额数值正确，但模型没有把它们列入本条结论的 metric_ids，且只引用了定性披露；又把未在输入中核验的关系写入 accounting_links，并声称解释覆盖全部净额变动。现有 Validator 已拒绝这些结构化错误，并非错误关系已经通过验证。

实际读取原始目录 `outputs/agent_acceptance/20261102-authorized-3409dac866/live/20261102T143227-e1ab7ac1f3/investigation/` 下的 input.json、analysis.json、checks.json、events.jsonl、decisions/03.json。结合当前源码检查历史记录，不将当前第一项专项修复后的行为倒推成历史行为。

数据快照：`outputs/final_revision/20261017T093152-d80de1cefa`。读取 cash_metrics.json、cash_checks.json、source_checks.json、cash_bridges.json、bridges.json 等；通过现有 load_agent_payload 只读重新核验来源与 PDF 记录，按历史事实/证据范围投影，复现 accounting_relations 为空。使用 Decimal 独立复算两期直接法勾稽和变动额。没有启动真实调用入口。

## 2. 三个指标定义、金额与来源

金额单位均为人民币元（CNY）；base=2024，current=2025，change=current-base。输入声明为披露口径合并报表，合并范围发生变动，非恒定主体比较。

|事实 ID|实际项目名称|2024|2025|差额|
|---|---|---:|---:|---:|
|operating_cashflow|经营活动产生的现金流量净额|29,369,250,570.66|46,383,114,754.02|17,013,864,183.36|
|cash_2|销售商品、提供劳务收到的现金|171,937,113,993.38|180,152,594,833.80|8,215,480,840.42|
|cash_6|收到其他与经营活动有关的现金|3,249,319,163.59|18,284,568,266.19|15,035,249,102.60|

上述含义来自实际工作表项目名和 PDF 对照，不是按内部 ID 猜测：final_release.py 按“经营现金流”工作表行号生成 cash_ID，cash_2 对应 B2:C2，cash_6 对应 B6:C6；核心 operating_cashflow 对应“核心指标”B9:C9。现金流表 cash_16 是相同净额的另一内部行 ID。

原始报表为《格力2025年年度报告.pdf》合并现金流量表，印刷页88、PDF页89，列示2025及2024比较数。operating_cashflow 的2024数另有2024年报第114页交叉核验。证据分别为 F_operating_cashflow、F_FINAL_cash_2、F_FINAL_cash_6。cash_6 原始行包含附注“五、70（1）”。E18 也包含经营活动现金流表，但其 related_facts 仅绑定 operating_cashflow，不能只因摘录含有多行就绕过当前结构化证据映射。

cash_16 工作表公式缓存存在浮点尾差（29369250570.660034、46383114754.01996），本报告使用已核验 PDF 对应精确十进制金额，未改写任何数据或公式。

## 3. 真实计算关系及数据充分性

当前结构化 cash_metrics 包含经营活动直接法15行（cash_2 至 cash_16），不是仅有两项流入。独立核算与既有 cash_bridges.json 一致：

- cash_7（经营现金流入小计）= cash_2 + cash_3 + cash_4 + cash_5 + cash_6。
- cash_15（经营现金流出小计）= cash_8 + cash_9 + cash_10 + cash_11 + cash_12 + cash_13 + cash_14。
- cash_16（经营活动现金流净额）= cash_7 - cash_15。

|项目|2024|2025|变动|
|---|---:|---:|---:|
|客户存款和同业存放款项净增加额 cash_3|50,560,729.20|-97,277,745.41|-147,838,474.61|
|收取利息、手续费及佣金的现金 cash_4|690,447,891.17|200,053,993.35|-490,393,897.82|
|收到的税费返还 cash_5|3,596,859,028.53|3,374,836,508.02|-222,022,520.51|
|经营现金流入小计 cash_7|179,524,300,805.87|201,914,775,855.95|22,390,475,050.08|
|购买商品、接受劳务支付的现金 cash_8|108,253,725,552.93|117,300,948,888.33|9,047,223,335.40|
|客户贷款及垫款净增加额 cash_9|1,579,170,000.00|1,096,845,000.00|-482,325,000.00|
|存放中央银行和同业款项净增加额 cash_10|485,197,013.98|35,123,619.38|-450,073,394.60|
|支付利息、手续费及佣金的现金 cash_11|157,403,936.47|23,127,968.03|-134,275,968.44|
|支付给职工以及为职工支付的现金 cash_12|11,779,145,121.58|11,967,701,115.43|188,555,993.85|
|支付的各项税费 cash_13|16,976,161,858.63|15,902,339,423.32|-1,073,822,435.31|
|支付其他与经营活动有关的现金 cash_14|10,924,246,751.62|9,205,575,087.44|-1,718,671,664.18|
|经营现金流出小计 cash_15|150,155,050,235.21|155,531,661,101.93|5,376,610,866.72|

已有三个桥接均标记 user_confirmed_formula、金融组最终确认的直接法勾稽、exact_zero_residual，两期及变动残差均0.00，无缺失项。独立 Decimal 复算通过。保留 cash_3 的负数；没有把 PDF 未列金额的空白行自行补零。

变动桥接为：

```
两项流入增量 = 8,215,480,840.42 + 15,035,249,102.60
             = 23,250,729,943.02
其余流入变动 = -860,254,892.94
流入小计变动 = 22,390,475,050.08
净额变动     = 22,390,475,050.08 - 5,376,610,866.72
             = 17,013,864,183.36
其余项目净抵减 = -6,236,865,759.66
```

因此，本地完整经营活动直接法数据支持“披露口径下的算术变动桥接”，但两项流入的增加不能单独等同于净额增加，也不能说明完整经营因果。可以在经核验完整公式中表达两项的带符号算术项，不能将其包装为独立、排他的经营贡献。当前授权模型事实只有 net_profit、operating_cashflow、cash_2、cash_6，未提供其他全部分项的结构化事实及授权关系，不能让模型自行完成完整桥接。完整年报 PDF 的存在也不等于其中全部内容已经获准外发。

不能据此宣称已完成投资、筹资等整张现金流量表的结构化覆盖，更不能宣称有完整净利润到经营现金流的间接法调节或恒定合并范围因果分解。

## 4. E07_28 的支持边界

原文（2025年报印刷28页/PDF29页）为：

> 1.经营活动产生的现金流量净额同比变动 57.93%，主要系销售商品和提供劳务收到的现金增加、收到其他与经营活动有关
> 的现金增加所致。

A 报表归属：cash_2、cash_6 是经营活动现金流入项目，由报表及字段映射支持。

B 会计计算：净额由全部流入减全部流出形成，由完整表及既有确定性桥接支持；不能由这段定性披露代替公式核验。

C 经营解释：这段话支持“年报披露主要系两项现金流入增加”的有来源定性说明。没有列出两项差额，没有给出占比或完整贡献拆解，没有解释两项增加的更深业务原因，也没有建立与净利润下降的调节关系。

模型 support_limit 中“该解释覆盖全部现金流量净额变动幅度”超出原文和计算支持边界；“主要系”不等于“全部定量归因”。换行逐字比较属于另项任务，本报告不提出相应修复。

## 5. accounting_relations 为空的数据流根因

1. accounting.py 已有通用 bridge 计算。final_release.py 分别生成利润 bridges.json/directional_impacts.csv 和 cash_bridges.json；final_revision.py 对已保存桥接复核。因此不是项目完全没有会计关系计算，也不是本地完全没有现金流数据。
2. stage3_input.prepare 调用 analysis_contract.configure。configure 只读取 bridges.json 和 directional_impacts.csv，没有读取 cash_bridges.json。verified 要求公式已确认、零残差、所有分项事实在当时 payload 中，还核对目标金额和各分项方向。
3. final_release.load_agent_payload 在 prepare(full) 之后继续扩展核心及现金流事实，但没有重建 accounting_relations，也没有导入现金流桥接。cash_16 未作为另一个现金流事实导出；其与 operating_cashflow 的显式桥接别名映射也没有进入分析合同。不能让模型自行用别名或传递关系补齐。
4. 未投影 payload 中已有的是利润关系（net_profit、parent_profit 等，部分 verified=false），没有现金流关系。agent_live.project 仅保留 target 和所有 components 都在授权事实白名单内的关系。净利润关系所需 pretax_profit、income_tax 不在本次范围，因此被正确排除；其他关系也不满足范围。
5. 复现投影结果与历史 input.json 一致：accounting_relations=[]。本次 mode=full，不是 focused 模式清空导致。空数组是“现金流关系未接入 + 本次完整分项不在授权范围”共同造成，不能仅凭空数组判断为 Bug。
6. agent 状态持有 analysis_contract，但 QwenDecider.context 没有把该关系合同传给模型。原始 decisions/03.json 的实际上下文亦没有 accounting_relations；传入 analysis_schema 仍允许 accounting_links 的对象形状。因此模型可生成语法合法但业务不合法的链接。这里不能声称一个已经获准的现金流关系只是被适配器遗漏：本次输入中本来就没有它。
7. source_contract 负责来源、PDF哈希、页码、原文及事实绑定，并不据此授权算术关系。report_check 的单事实金额/方向检查也不是现金流关系生成入口。

## 6. Schema、Validator 与真实错误逐项核对

SCHEMA_V2 允许一个 claim 涉及多个 metric_ids；amount 使用 fact_id、field（base/current/change）、unit、value，引用在 claim 级 citations 中，不是 amount 级。amount 的 fact_id 即对应财务指标身份，不是把 cash_2 金额写在任意净额指标下都合法。

stage3.validate 已要求 amount.fact_id 属于同条 metric_ids，按事实/字段/单位用 Decimal 精确核对；每个 metric 要有相关引用。analysis_contract.check_contract 要求 accounting_links 的 target 存在已验证关系、component 是该关系明确成员、effect 符合 Python 结果，且两者均在本条 metric_ids。它不自动推导跨层关系。空 relations 时所有非空 links 均被拒绝。

|原始第二条结论内容|核对结果与原因|
|---|---|
|metric_ids 只有 operating_cashflow，amounts 为 cash_2、cash_6|差额本身准确，但漏列两个独立指标；checks.json 实际记录两次“金额未关联该条财务项目”|
|citations 只有 E07_28|支持定性披露，不提供两个金额的结构化来源。仅补 metric_ids 仍不足，应有当前规则允许且绑定对应事实的原始金额证据|
|两条 cash 分项到 operating_cashflow 的 links|输入没有相应已验证关系；实际记录两次“会计层级或关系未获输入核验支持”|
|两条 links 的 component 未在 metric_ids|实际另记录两次“会计关系未关联所引用项目”|
|support_limit 称覆盖全部净额变动幅度|不受定性披露支持；忽略其他流入、流出，不能由正确金额推出因果或完整覆盖|

现有防护已拦截本次结构化错误。尚可加强的是每笔 amount 与同条 claim 中已合格引用的 fact.evidence_ids 精确绑定，避免只满足较宽的 related_facts 关联就混用定性来源。source_contract 的 disclosure 检查与人工复核不能等同于自动证明定量归因。第一项证据覆盖检查也不能替代同条 claim 的金额来源绑定。

不必给每个 amount 增加新 evidence_id 字段：现有 fact.evidence_ids 与 claim.citations 的交集可表达来源关系。change 可以由已核验 base/current 计算，不应要求 PDF 引文逐字包含计算后的差额。disclosure_explanation 和 accounting_fact 已有 kind 区分，优先分别组织披露解释与数值事实，不必新造整套结构。accounting_relations 为空时应明确要求 accounting_links=[]；这是现有业务校验规则，而不是必须修改静态 Schema 才能实现的限制。

其他历史错误（证据链、换行、自由文本数字、长度及其他业务问题）仍保留原记录，均不在本轮修复建议范围。

## 7. 三种方案比较及推荐

|方案|内容|工程量/风险|Schema兼容性|
|---|---|---|---|
|A 数据结构约束|明确传递经授权且核验的关系清单（含空数组）、事实到金额来源的映射；不扩展白名单|小至中；需严格控制上下文外发范围|可只增上下文字段，SCHEMA_V2无需变更|
|B Validator 加强|保留已有 fact_id/metric_id/金额/关系检查；补强同条 amount 的合格原文来源绑定与针对性诊断|小至中；不能误拒绝由两期原文核算的 change|复用现有字段，兼容协议；可能拒绝旧的来源不足结果，应视为正确拦截|
|C Prompt 调整|空关系只能空 links；披露原因、数值事实、确定性公式、经营假设分清；不把两项增量宣称为完整贡献|小；仅提示不能保证正确性|无 Schema 变化|

推荐 A+B+C 的最小组合，但本轮不实施：

- tracelab/qwen_decider.py：向模型明确传递经过当前授权筛选的 accounting_relations（即使为空）及事实来源映射；保留证据可见性/取得资格区分。
- prompts/agent_decision_v1.txt：明确空关系限制及披露/金额分开组织的要求；不得自行推导 cash_2→cash_7→cash_16→operating_cashflow。
- tracelab/stage3.py：对 amount 复用已验证事实来源和同条合格引用，补强来源绑定。保留精确金额、单位、期间和引用核验。
- tracelab/analysis_contract.py：保留现有关系核验；如有必要只增强诊断。它已经会拒绝本次错误，无需重写计算。
- 对应 tests/test_qwen_decider.py、Agent进度/分析验证测试：增加上下文及完整执行路径回归。

不建议当前直接把 cash_bridges 全量导入：这会涉及全部分项的授权、cash_16 与 operating_cashflow 的别名核验、符号及多层关系定义，超出最小修复。未来如单独开展，应复用既有公式，不扩大本次数据范围，不用模型补公式。

## 8. 后续离线回归建议

1. 真实第二条输出重放：正确差额但漏列 cash_2/cash_6 时继续拒绝。
2. 补齐 metric_ids 但只引 E07_28，仍拒绝作为两笔金额来源。
3. 两期已核验原文、正确 fact_id/field/unit、合格证据及指标齐全时，允许数值事实通过；差额不必在原文中逐字出现。
4. 空 accounting_relations + 任意非空 links 拒绝；空 links 的合格定性披露可通过其余校验。
5. verified=false、错误 component、错误 effect、缺失目标/分项 metric_id 各自拒绝。
6. 上下文明确包含空清单；非空清单只含授权范围完整覆盖的已验证关系，不泄露其他分项。
7. 禁止自动跨层合成关系及 cash_16 别名替换。
8. 未取得或未授权金额来源仍由第一项修复拦截，不能因来源映射存在就获得引用资格。
9. 保留两期金额、单位、期间、来源哈希篡改拒绝测试；完整桥接未来应检查其他流入与流出符号及残差，不允许只取两项流入。
10. 定性解释未带 links 仍需支持边界审核；不能把空 links 误当经营因果自动通过。

本轮只读核算三条关系在两期及变动层面一致，加载/来源核验和历史范围投影通过；未运行完整 unittest（没有代码改动），不宣称新增测试或离线修复验收通过。

## 9. 限制与停止状态

本轮完成定位与方案，不实施修复。当前结构化关系校验已发挥作用，但自由文字的因果强度不能完全靠现有结构校验识别，金融组业务复核仍必要。原始调查处于失败结果，不应改写为成功；第一项证据链修复保持不变。

本报告是本轮唯一写入。未修改财务公式、原始数据、真实模型输出和日志，未读取或输出 API Key，未发起任何真实模型请求。完成后停止，等待后续指令。
