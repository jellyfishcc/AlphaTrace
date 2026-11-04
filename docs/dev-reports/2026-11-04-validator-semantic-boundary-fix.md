# 第二阶段：Validator财务口径与证据支持边界

日期：2026-11-04。基线8bfb016717a19dad358d4778cc29b82cc4987aad，分支main。开始时第一阶段4个模块未提交，第一阶段测试及报告、审查报告和原PDF未跟踪，全部保留。本轮未调用真实模型/API、未读取密钥、未commit/push。

## 1. 实际调查与根因

读取两份指定报告和当前stage3.validate、analysis_contract.check_contract、source_contract、report_check.check_claim、可信指标层级代码。实际读取20261102-authorized-3409dac866下investigation/input.json、analysis.json、checks.json。

net_profit可信名称为净利润，绑定F_net_profit，原文为“五、净利润（净亏损以“-”号填列）”。历史模型把该引文改成“归属于母公司股东的净利润”。现有引用核验能拒绝改写，但原先正确引用搭配错误正文名称没有独立冲突检查。report_check有结构化metric_name对照，却不是Agent分析Validator入口；不能认为Agent已继承它。

E07_28原文说主要系相关现金流入增加，模型support_limit却声称覆盖全部净额变化。原disclosure_errors验证来源、比较基准、指标标签；check_contract检查长度与会计links；没有自动审查支持强度。因此去除其他违规项的过度归因可能errors=[]而待人工复核。

## 2. 修改文件与接入

- 新增tracelab/semantic_boundary.py：check_semantic_boundary与有限句式stance分类。
- tracelab/stage3.py：在既有逐条claim核验中调用辅助检查，追加errors和manual_review，不替换或删除任何原校验。
- 新增tests/test_semantic_boundary.py：12项专项测试，多个子场景。
- 本报告。

第一阶段规划器/任务状态、Agent循环、前置检查、终态转换、Qwen上下文、Prompt、SCHEMA_V2、财务数据、计算公式、费用保护、原引文比较均未修改。没有新增事实、证据或会计关系。语义模块仅读取当前payload，不扩授权。

## 3. 自动拒绝与人工复核边界

### 指标口径

使用source_contract事实摘要验证的name作为基准，不按金额相同推导等价。仅对已经存在的net_profit与parent_profit层级采用明确别称：归母净利润/归属于母公司股东的净利润属于parent_profit，净利润属于net_profit，不合并两个ID。

若claim仅声明其中一个利润层级，可信name匹配对应基准，正文在明确断言句式中使用另一个层级，报metric_scope_conflict，标明statement/support_limit字段。例如net_profit claim写“归母净利润下降”、或“本项金额等同于归母净利润”。对历史F_net_profit绑定的引文被以归母名称开头替换，也提供独立citations冲突诊断；原逐字与金额来源错误继续保留。

“不是/并非/而非/不等于”等局部否定，以及对比、条件、问题、引述或复杂指代不自动当成替换；增加明确人工复核提示。多个利润ID同时出现时不凭关键词猜各段金额所属，逐项归属需人工检查。parent_profit使用自己可信名称和证据正常通过。正确引文并不能替代正文口径核验。

### 支持强度

读取当前引用证据的来源验证状态和原文限定词“主要系”。当缺少已核验经营现金流净额关系，模型在明确肯定句中声称覆盖全部/完全解释/完整定量贡献等完整净额归因时，报support_scope_overreach。纯名词“完整贡献”不是自动拒绝条件；须有相应断言形式。此规则不因claim.kind改为accounting_fact就绕过。

按分句判断，否定不会豁免后面“但”转折后的独立肯定断言。“不能覆盖全部”“不能证明该解释覆盖全部”“完整贡献尚未核实”“该说法缺乏证据”不因相同关键词误拒绝。原始quote保持不变，quote中的来源说法不直接当模型自行断言。

如果存在已核验关系、多个潜在支持来源或复杂引述，辅助检查不宣称已经证明完整因果，继续明确人工复核。已有关系/金额/引文Validator仍执行，关系存在也不自动证明经营因果。

有限词形与句式只能覆盖明确错误，不是通用中文指代、否定辖域或因果推理器。未命中规则不意味着自动核验了语义；每条claim均增加这一人工复核说明。规则不会重写模型文字、自动修正口径或把待审结果当金融组认可。

## 4. 测试与历史样本

新增12项：正确净利润；正确引用但错误归母正文（两个别称）；金额已核验也不能视指标等价；独立合成parent_profit正确名称来源；否定/对比；适当限定披露；完整覆盖和分项流入完整贡献拒绝；否定/缺乏证据不误拒；否定不豁免后续肯定；复杂因果人工复核；kind变更不绕过；真实历史诊断与原样Replay。

parent_profit测试是明确标注的合成来源夹具，复用相同数值仅验证“金额相同不代表层级相同”，不是声称真实归母金额等于净利润，没有改真实数据。历史analysis直接送现有validate后新增两类诊断均可单独断言，其他原校验错误没有删除。实际原样Replay仍在原证据前置检查失败，三次模拟请求，无真实调用；不会声称新语义模块在该被前置阻断的执行中已被调用。

初次测试发现“完整贡献尚未核实”被误判，已将局部后置未核实表达归为非肯定、并要求名词贡献有直接断言形式；正反例最终全部通过，未放宽旧Validator。

- 新专项：12通过，0失败、0错误、0跳过。
- 第一阶段：14通过，0失败、0错误、0跳过。
- 四项历史专项：9、15、11、10全部通过，均0失败、0错误、0跳过。
- 全量：320项，318通过、1失败、1错误、0跳过，138.430秒。失败test_timeout_or_missing_usage_preserves_reserve_and_stops、错误test_correct_model_region_and_free_tier_send_once均为既有price_reverification_required日期问题，无新增回归；费用保护未改。
- 第一阶段4个源码文件及其测试、Prompt、QwenDecider、source_contract的前后SHA-256相同；git diff --check通过。第二阶段专项离线验收通过，全量不宣称全绿。

执行python -X utf8 -m unittest discover -s tests -v，测试子进程使用项目tmp及已有tmp/test-deps。日志tmp/semantic-full-tests.log。第一阶段入口测试完全Mock且禁用网络，打印starting_authorized_investigation为测试入口输出，不是实际授权或真实模型请求。

## 5. 限制与验收边界

本轮自动规则局限于两个利润层级及来源限定与完整净额归因的明确冲突。更复杂的代词、多重否定、跨句引用和其他利润层级不冒充自动理解，交人工复核；不能据此承诺模型所有口径错误都可被识别。一般语义安全并非已解决。

不改变第一阶段任务完整性，不提前开发第三阶段自动继续调查或状态转换。新规则只追加拒绝/复核理由。完成后停止，等待后续指令。
