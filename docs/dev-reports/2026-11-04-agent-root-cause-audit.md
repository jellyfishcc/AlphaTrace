# 真实 Agent 调查失败根因只读审查

日期：2026-11-04。分支 main，HEAD 8bfb016717a19dad358d4778cc29b82cc4987aad，与指定基线一致。开始时仅 output/ 未跟踪，包含原有PDF，不能称工作区干净。本轮仅新增本报告；未改代码、Prompt、Schema、原始资料、费用保护或历史记录，未读取密钥，未联网/API调用，未commit/push。

## 一、实际读取与定位

以下文件均在指定唯一授权调查内实际找到、完整读取并解析，没有借用其他调查。execution_binding.json 位于授权根目录，不在 investigation 子目录。

|文件实际路径|存在|关键字段及作用|
|---|---|---|
|D:\Projects\TraceLab\outputs\agent_acceptance\20261102-authorized-3409dac866\live\20261102T143227-e1ab7ac1f3\investigation\input.json|是|company/periods/currency/scope/facts/evidence/analysis_contract/source_contract；六证据授权集、四事实及空会计关系|
|D:\Projects\TraceLab\outputs\agent_acceptance\20261102-authorized-3409dac866\live\20261102T143227-e1ab7ac1f3\investigation\analysis.json|是|claims/questions；两条模型结论、引用、金额、链接及支持边界|
|D:\Projects\TraceLab\outputs\agent_acceptance\20261102-authorized-3409dac866\live\20261102T143227-e1ab7ac1f3\investigation\checks.json|是|status/errors/manual_review/boundary；历史11条错误原始清单|
|D:\Projects\TraceLab\outputs\agent_acceptance\20261102-authorized-3409dac866\live\20261102T143227-e1ab7ac1f3\investigation\events.jsonl|是|started/model_decision/decision/tool_result/finished；逐轮工具和终态|
|D:\Projects\TraceLab\outputs\agent_acceptance\20261102-authorized-3409dac866\live\20261102T143227-e1ab7ac1f3\investigation\result.json|是|status/usage/retrieval_audit/stop_reason/evidence_gap；最终失败与实际取得的五条证据|
|D:\Projects\TraceLab\outputs\agent_acceptance\20261102-authorized-3409dac866\live\20261102T143227-e1ab7ac1f3\investigation\plan.json|是|signals/investigation_tasks；authorized_goal及空任务|
|D:\Projects\TraceLab\outputs\agent_acceptance\20261102-authorized-3409dac866\execution_binding.json|是|authorization_id/user_authorized/max_investigations/real_request_started/goal/budget/commit/code_hashes/source_audit；执行前授权与快照绑定|

另读取 decisions/01.json、02.json、03.json 的请求消息、响应、action与usage。execution_binding.real_request_started 是执行前记录，不能据其否认之后调用；真实调用由 events/result 的 simulation=false、llm_called=true及三轮请求证明。当前提交不能当作历史实际执行版本；历史执行另有代码哈希绑定。

## 二、真实过程还原

|轮次|动作|输入/输出Token|关键事实|
|---|---|---|---|
|1|search(query=净利润与经营活动现金流量净额差异原因, metric_id=operating_cashflow)|2983 / 27|返回F_operating_cashflow、E07_28、E18、F_FINAL_cash_6、F_FINAL_cash_2|
|2|get(E07_28)|3609 / 18|取回该授权摘录；不是全库阅读或新PDF抽取|
|3|explain|3509 / 786|完整JSON，finish_reason=stop；不是预算截断|

累计输入10101、输出831、合计10932，3模型请求、2工具调用、0重试。每轮questions=[]，历史模型上下文没有accounting_relations字段。第二轮queried_evidence显示两个现金流分项，第三轮显示E07_28；初始事实的retrieved_source_quotes还会携带已取得的相应原文，因此不能将queried_evidence的两个条目当作全部模型知识。

F_net_profit在三轮initial_facts和目录中都有ID与可信净利润金额，name与financial_level均为净利润，但retrieved_source_quotes始终为空。三轮工具记录均未取得F_net_profit。为什么模型选择现金流后不继续查净利润，是可观测动作；其内部心理或训练原因尚未证实，不推测模型思维链。

历史终态validation_failed、stop_reason=explanation_submitted、evidence_gap=null，反映代码将“提交解释事件”与“解释是否有效”分开记录，但没有为拒绝结果提供结构化原因分类。

## 三、11条错误归类，不是11个独立Bug

|历史错误序号|内容|共同根因|
|---|---|---|
|1、2|结论1引用不存在证据、财务项目缺少相关证据|本轮取得集合没有F_net_profit，Validator看到的是过滤子集；不是授权包无此证据|
|3|结论2引文与原文不一致|E07_28指定位置PDF软换行；第三项已修复|
|4、5|结论2金额未关联财务项目|cash_2/cash_6在amounts但不在同条metric_ids|
|6|自由文本数字|正文复述金额、差额、比例、年份及页码；历史一条泛化提示掩盖多个字段|
|7|结论1解释或支持边界过长|statement超100字符；不是输出Token截断|
|8、10|会计关系未获核验支持|输入关系清单为空却写两条links|
|9、11|会计关系未关联项目|两条links的component不在metric_ids，与4、5共同涉及指标声明不完整|

净利润口径替换、完整覆盖净额的夸大并未作为独立语义错误出现在历史11条中。不能因此认为程序已证明它们正确。

## 四、净利润口径与映射

stage3_input.prepare（stage3_input.py:58—78）按standard_metric映射、PDF数值记录与计算结果核对，建立F_+key、fact_id=key、name=item_name。final_release.CORE（:22）将net_profit映射“核心指标”第7行，parent_profit另为第8行，非同一指标。

历史fact_id=net_profit，name=净利润，evidence_ids=[F_net_profit]；2024为32,371,069,287.35元，2025为28,862,746,016.16元，change=-3,508,323,271.19元。F_net_profit为2025年报印刷87/PDF88页：“五、净利润（净亏损以‘-’号填列）”对应原始行（实际中文引号样式按日志保存）。原文与结构化名称一致。模型引用却改成“归属于母公司股东的净利润”，属于无依据替换口径，不是原始映射错。

须分三种错误：授权目录中没有ID→未知证据；授权内但本轮未检索→引用资格缺失；取得后原文名称被改→引文不匹配。当前第一项明确记录第二种；独立诊断将全部授权证据交给validate时，净利润错误变成“结论1引文与原文不一致”。这个诊断不是授予其引用资格，也不是生产路线A。

LocalFacts（agent.py:78）向模型提供净利润与归母净利润不同financial_level；stage3没有claim.metric_name字段，也没有全面解析正文名称。只要模型在正文错误改称归母、引用仍为正确净利润，现有结构性检查未必发现。report_check.check_claim（:15、:53）另有metric_name严格等于fact.name的校验，但该模块属于独立结构化报告纠错入口，不在Agent→stage3调用链，不能将其能力误算给Agent。

## 五、四项修复实际覆盖及本轮只读验证

本轮用python -B在内存读取原样analysis和工具历史，调用当前explain_precheck、validate及quote_matches；没有运行会写输出目录的完整investigate，没有伪造新模型响应。读取四个专项测试文件，确认测试方法数9、15、11、10及其正负例。没有重新运行完整unittest，不将此前测试数字当成本轮新结果。

1. 证据链：当前precheck返回ready=false，missing_core_metric_ids=[net_profit]，ineligible_citation_ids=[F_net_profit]，missing_claim_metric_ids=[net_profit]。已覆盖历史提前引用与核心来源缺失。它检查“来源存在且已取得”，不是完整调查问题都已回答。
2. 金额与关系：QwenDecider.__init__（:124）只导出verified严格True且target/components均在scope内的关系；context（:183）显式传空清单。stage3.validate（:99—117）核对Decimal值、fact/metric对应、fact摘要和同条引用交集、来源摘要及口径；analysis_contract.check_contract（:81）核对关系/方向/指标。历史cash金额继续拒绝，不会因换行已修复而通过。
3. 引文：source_contract.quote_matches（:87）先精确子串，失败后须PDF哈希和完整evidence摘要命中登记，才能删除零起始第58位LF。历史E07_28现在匹配；数字/标点/实质改写没有放行。stage3一般引文与金额来源检查共用该函数；bind_sources仍严格核验原摘录，第一项前置检查不做正文匹配。文本匹配本身不是来源授权，其他来源检查仍必要。
4. 数字：stage3.free_text_number_errors（:61）区分有边界、授权periods内的四位年份+年；金额、比例及页码仍拒绝。历史现在报告claims[0].statement、claims[1].statement、claims[1].support_limit三个字段；原文quote不扫描，57.93%在quote保留、正文拒绝。ratios_allowed=false由configure设置，但布尔值本身并未在validate中分支读取；现行为由统一禁止正文比例实现，不存在已支持true模式。初始事实有change但历史第一条amounts没有；程序不自动补差额，也不要求每个金额字段机械齐全。正确base/current并不能授权正文未结构化差额。

使用历史retrieved_evidence_ids过滤payload再单独执行当前validate，得到16条错误：第三项的换行错误消失；新增金额原始来源约束与字段级数字错误令数量变化。全部授权证据的独立诊断得到15条，净利润转为引文不一致。当前真实编排会先被precheck拒绝，不会实际同时产生这16条，因此不可把这次诊断输出冒充真实运行日志。

历史数字细节：第一条正文2025、2024（两次）；金额28,862,746,016.16、32,371,069,287.35、46,383,114,754.02、29,369,250,570.66；差额3,508,323,271.19、17,013,864,183.36；57.93%。第二条正文57.93%，support_limit第28页。年份当前允许，金额/比例/页码仍拒绝。

## 六、支持边界的实测缺口

Prompt已明确“主要系”不等于“覆盖全部”，禁止将cash_2/cash_6增量直接当净额独立贡献。source_contract.disclosure_errors（:66）只检查来源真实性、比较基准与指标标签交集；stage3检查support_limit非空、数字规则；analysis_contract检查长度上限140。没有验证support_limit语义是否超出引文。

本轮内存合成探针：只保留历史第二条，删除金额与links、用无数字的年报披露statement，但保留“该解释覆盖全部现金流量净额变动幅度”。validate返回needs_human_review且errors=[]。这证明自动边界检查不充分，而不是证明该结论成立；manual_review确实要求人工核对因果。

保留“年报披露主要原因，但完整贡献尚未核实”的文字+support_limit+questions在现有Schema内可行；没有必要重写协议。两项流入增量合计23,250,729,943.02元，而净额只增17,013,864,183.36元，需要其他流入及流出抵减。已存在本地cash_bridges不代表本次四事实授权包含所有分项。configure只读利润bridges，live.project又过滤不完整授权关系；不要为解决这一问题全量导入cash桥接或扩大外发范围。

## 七、规划、提前Explain与终态

### 任务生成

agent_live.main（:110）直接构造authorized_goal信号和investigation_tasks=[]，现版本仅额外给两个core_metric_ids，仍未接入prepare_investigation。investigation.prepare_investigation（:5）本可生成利润层级及利润/现金流调节问题，但真实入口没有调用。agent.investigate（:148—151）的matching or tasks只是从已有任务选择，不会为[]生成新任务；有signal.description时保留用户目标，无signal才回退默认目标文字。

另一个集成注意点：prepare_investigation产生profit_down_cashflow_up，而真实入口使用authorized_goal；不能仅粘贴任务就假定reason匹配。若已有匹配异常任务，matching or tasks还会排除未匹配的基础利润任务，未保证“先完成利润层级”叙述与实际选择一致。未来整合应明确必做任务，不盲目扩大利润分项授权。

### 工具与覆盖

LocalEvidence.search（agent.py:35）由模型提供metric_id，先按related_facts过滤，再中文双字/英文词匹配排序，最多20条。F_net_profit只绑定net_profit，因此被operating_cashflow过滤；不是工具遗漏已匹配项。get（:49）按ID取授权摘录，不自行探索其他材料。

旧progress按是否读过证据提示explain，缺少核心覆盖；现context覆盖提示弥补此点，但没有完整任务账本。search实际返回原文，所以路线B允许search或get取得资格，不必每个命中重复get。模型看到的详情裁剪与完整检索集合分开，不能等同。Prompt要求原文当前可见，precheck只检查已取得资格而不检查每次实际可见片段；这是可见性与资格的不同层次，不应倒退放宽路线B。

### 前置检查覆盖矩阵

|检查|现状|位置与限制|
|---|---|---|
|核心指标来源|有|evidence_progress:13/34，两个核心事实来源覆盖|
|引用资格|有|本轮search/get且来源核验，未取得拒绝|
|指标名称语义|部分|ID/层级提示及quote，正文名称无独立对照|
|金额来源|有，后置Validator|stage3:99，不在precheck重复实现|
|会计关系授权|有，后置Validator|analysis_contract:81，不自动推导|
|调查目标完成度|缺少|没有五个问题各自answered/gap账本|
|证据充分性|仅来源充分性|不证明能够解释两者背离或支持因果|

### 状态转换

历史及当前agent.py:203—210在有analysis时执行validate，将errors非空设为validation_failed，然后独立赋stop_reason=args.reason或explanation_submitted并break。它是动作原因，不是核验结论，失败也不会回到模型继续调查。末尾:251仅在insufficient_evidence时将stop_reason作gap，故历史失败gap=null。

当前第一项已为precheck拒绝提供结构化gap，但完整Validator拒绝仍可能只有errors+explanation_submitted+gap=null。异常分支:234—243也统一validation_failed/invalid_decision_or_tool_error。默认result又为insufficient_evidence/round_limit；工具超限:212会保留该状态并记tool_limit。因此不能只看insufficient_evidence就断言证据确实不足。

正常stop在此协议并没有另一个“成功结束”状态：无analysis或合法analysis且reason非空即insufficient_evidence；检查只保证reason非空，没证明具体缺口及已检索范围。合理停止、预算停止、校验拒绝、系统异常需用结构化终止分类区分，不能把失败自动包装为合理stop。无证据也不能无限自动重试。

## 八、完整数据流与契约

|环节|输入→输出|负责函数/合同|校验与失败|
|---|---|---|---|
|授权目标|goal+scope+快照→限定payload|agent_live.prepare/project，来源合同|哈希、scope不符在调查前拒绝|
|调查规划|GOAL→signals及空tasks|agent_live.main；不是prepare_investigation|当前无任务完整性校验|
|任务选择|signals/tasks→questions+goal+core|agent.investigate:148|空tasks得到空questions，不生成问题|
|决策|state→action/arguments|QwenDecider.context/decide/check_action；动作Schema|JSON/usage/预算/授权错误安全失败|
|search|get参数→原文+ID|LocalEvidence.search/get；授权证据对象|更新history/seen；未知ID等失败|
|上下文|history+initial facts→目录、有限原文、关系、覆盖|QwenDecider.context|scope过滤，详情截断标记；预算超限拒发|
|explain|模型analysis→前置覆盖结果|explain_precheck|缺核心/非法引用→validation_failed+结构化gap|
|结构核验|analysis+retrieved payload→checks|stage3 SCHEMA_V2+source_contract+analysis_contract|金额、文本、关系拒绝或needs_human_review|
|最终结果|checks+action→result/审计|agent.investigate:209/251|通过explain为pending_human_review；拒绝非stop成功；系统异常单列原因不足|

跨环节主要不一致：文字目标不等于任务列表；来源覆盖不等于目标完成；related_facts不等于金额来源；空关系的静态Schema仍能表达非法links但动态Validator拒绝；声明support_limit不等于已验证支持边界；终止动作原因不等于业务缺口类型。

## 九、问题—代码映射表

|问题|真实触发数据|实际文件及函数|根因|已有修复覆盖|最小建议|
|---|---|---|---|---|---|
|净利润证据未检索|F_net_profit|agent.LocalEvidence.search:35；evidence_progress.explain_precheck:34|仅查现金流且旧无核心来源门槛|第一项已覆盖|保留规则，在任务账本中显示未覆盖而非重新开发检索|
|净利润口径混淆|伪造归母引文|stage3.validate:77；LocalFacts:78；report_check.check_claim:15|模型改称；正文指标语义未绑定|原文不匹配能拒绝，正文仅部分覆盖|复用canonical name/level，增加有限已知层级冲突检查及人工复核|
|E07_28引文|指定LF|source_contract.quote_matches:87|PDF排版差异|第三项覆盖|不扩大全局空白规则|
|金额指标关联|cash_2/cash_6|stage3.validate:99|缺metric_ids且仅定性引用|第二项覆盖|保留原检查与错误字段路径|
|会计关系白名单|空relations+两links|QwenDecider:124/183；check_contract:81|历史上下文没合同，模型自行推导|第二项覆盖|不新增关系、不全量导入现金流|
|自由文本数字|正文金额/比例/页码|free_text_number_errors:61|载体不符；旧扫描混淆年份|第四项覆盖|不允许正文比例，不重写Schema|
|支持边界|覆盖全部|disclosure_errors:66；stage3:88；check_contract:79|有格式检查、无充分语义验证|仅Prompt/人工，探针证实缺口|明确已知全量归因过强断言拒绝，其余人工标记|
|任务列表空|plan.tasks=[]|agent_live.main:110；investigate:148；prepare_investigation:5|入口未接规划器，空列表不回填|未覆盖|最小范围五问题任务契约，不扩展数据范围|
|Explain前置|第三轮explain|investigate:190；explain_precheck:34|历史无核心检查；当前仍无目标完成度|来源层已覆盖|增加任务 answered/gap判定，缺口可在预算内补查|
|最终状态|failed/submitted/null|investigate:209/242/251|动作、校验、缺口分类未统一|仅precheck gap覆盖|保留失败原状态，增加终止分类及结构化错误/缺口，不自动转成功|

## 十、五阶段最小修复路线（仅建议）

|阶段|具体问题与文件/函数|修改边界|测试样例与验收标准|依赖|
|---|---|---|---|---|
|一：数据与证据契约|agent_live.main、investigation.prepare_investigation、evidence_progress：明确五个调查问题、canonical指标及任务支持/缺口状态|复用四事实六证据；不改财务计算/SCHEMA_V2；不导入未经授权分项|空tasks不默认为已完成；net_profit与parent_profit区分；已检索ID仍不等于已回答因果问题；契约可由现有字段构造|现有四修复为基线|
|二：Validator|stage3.validate、analysis_contract.check_contract、source_contract.disclosure_errors：补有限口径冲突与支持强度边界；复用report_check名称规则思想|不把关键词检查宣称通用因果理解，不改quote算法和金额标准；无法证明的语义进入人工项|正确净利润原文+错误归母正文有明确冲突；“主要系”不能自动许可“覆盖全部”；谨慎披露可通过待审；原四专项全保留|依赖第一阶段canonical与支持边界定义|
|三：Agent流程|agent_live/main、agent.investigate、evidence_progress、QwenDecider.progress：传任务完成/缺口与终止分类|只用现有工具、最多5请求4工具；不无限重试；违规explain保留失败，优先在提交前引导补查|净利润未取得不得解释；两核心已取仍需披露与背离问题的answered/gap；预算结束与合理stop区分；Validator拒绝留分类且不伪装stop|依赖一、二的契约与错误分类|
|四：Qwen输出约束|prompts/agent_decision_v1.txt、QwenDecider.context：精简展示任务缺口、层级与边界规则|不堆叠Prompt、不增加预算，不让模型自行算贡献；不得重复四项规则|上下文总字节不突破既有限额；实际可见原文/检索账本区分；空关系明示；保留正常stop与紧凑explain|依赖三的任务状态；输出仍SCHEMA_V2|
|五：历史失败样本离线回归|tests/test_evidence_provenance.py、test_cashflow_relationship.py、test_quote_whitespace.py、test_free_text_numbers.py及必要流程测试|原始响应逐字Replay；合成成功路径明确标注；绝不改历史文件|原始失败保持失败但缺口定位清楚；四专项9/15/11/10不回退；完整校验正反例；预算/重复动作不可绕过；全量仅允许已知费用日期问题|依赖前四阶段，完成后再讨论独立真实授权|

五问题应涵盖净利润事实、经营现金流事实、年报原因披露、两者背离解释能力、尚缺证据；不是强迫五条结论或全白名单检索。任务无法在当前授权中完成时明确gap，不扩scope。当前缺口主要是规划、语义边界与结果分类，不应再次重写已完成四专项。

## 十一、尚未证实与限制

模型为何使用归母名称或偏向现金流，只有行为证据，没有可证明内部原因。当前自动校验不能证明经营因果；manual_review是待复核事项，不是金融组已经签字。简单反向关键词也可能误拒绝“不能覆盖全部”等正确边界，后续规则必须覆盖否定与来源归属。

本轮没有运行全量测试或真实模型，不宣称新的模型成功率或新的294项结果。本轮内存探针仅证明可观测程序边界。已有测试依赖本地历史输出，干净克隆不自带这些被排除的真实日志，回归环境需准备只读样本；不能将缺样本当作策略失败。

报告为本轮唯一新增交付。完成后停止，不进入修复阶段。
