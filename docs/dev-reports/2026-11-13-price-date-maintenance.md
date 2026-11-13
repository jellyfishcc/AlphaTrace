# 价格核验日期与离线测试时间依赖维护

日期：2026-11-13，Asia/Shanghai。开始时main，HEAD 27a9a4b81c47a3407537278e9ffcb5ae4519db89。已跟踪文件干净；上轮预检报告和output下yang、yang_sample、yang_v2及三个就业/求职材料zip未跟踪，均保留。没有重置、提交或推送。

## 官方核实与生产更新依据

本轮重新只读访问[阿里云官方qwen-plus模型文档](https://help.aliyun.com/zh/model-studio/qwen-plus)，核对华北2（北京）实时非思考原价：

|单次输入Token|输入元/百万Token|输出元/百万Token|
|---|---:|---:|
|≤128000|0.8|2|
|128000＜输入≤256000|2.4|20|
|256000＜输入≤1000000|4.8|48|

模型qwen-plus功能等同快照qwen-plus-2025-12-01，最大非思考输入997952、最大输出32768。真实项目请求进一步限制输出1200，enable_thinking=false、stream=false；未启用Batch、联网搜索或显式缓存创建，费用估算不取免费额度或缓存折扣。

上述单价、容量和模式与当前代码一致。执行时读取的北京时间为2026-11-13（14:08），所以生产VERIFIED_DATE由2026-11-02更新为2026-11-13，PRICE_URL指向本次实际核实的官方.com URL。增加地域、模型版本、模式、档位与报告路径注释。没有改变价格公式、模型容量、Endpoint或日期策略；跨过北京时间午夜后仍须重新核验，不设永久有效或30天宽限。

## 复现与根因

改动前直接运行两个指定测试，结果1失败、1错误，日志tmp/price-maintenance-before.log。

- test_correct_model_region_and_free_tier_send_once：原拟验证合法Mock发送一次，但check_live_price先按真实日历发现日期不一致，抛price_reverification_required，Mock发送根本未执行。
- test_timeout_or_missing_usage_preserves_reserve_and_stops：第一次被日期关卡挡住，没有预留或未知usage状态；第二次仍是日期错误，不能匹配预期cost_unknown。该失败不是超时处理本身放行请求。

## 文件与最小修改

- tracelab/cost_budget.py：只改PRICE_URL、VERIFIED_DATE及核实注释。AST对比确认全部函数/类逻辑未改。
- tests/price_clock.py：新增共享测试夹具fixed_price_clock；以固定2026-11-02北京日期和同日测试VERIFIED_DATE建立受控环境。只patch被测cost_budget模块的datetime与测试价格日期，不设置系统时钟，不进入生产导入路径；测试结束自动恢复。
- tests/test_free_tier.py：setUp使用共享夹具，两个原测试保留完整请求次数、模型、输出上限、实际usage及未知费用预留断言。新增4项跨路径测试：价格过期、UTC日期相同而北京跨午夜、非法思考/流式/附加计费参数、价格有效但免费额度过期。
- tests/test_cost_budget.py：使用同一夹具；strict_bound测试由接受token_budget_exhausted或price_reverification_required，收紧为只接受token_budget_exhausted，确保真的走到输入预算关卡；新增五次模型容量原价上界测试。
- 本报告。

没有改Agent、QwenDecider、Validator、Prompt、SCHEMA_V2、财务或证据。旧blocked_cost_input_bound对应的可靠输入界问题未被绕过：strict_bound仍会因模型容量预留超过60000而发送前阻断。当前已有免费额度usage_target语义保持不变。

## 正反验证与费用复核

固定夹具日期不是最新生产价格记录。原合法发送/超时测试不再随宿主日期自然失效。新增北京边界测试使用同一UTC日15:59与16:59：前者北京仍核验日，Mock调用一次；后者已次日，拒绝且Mock调用0次。过期价格用例同时确认预留行为空；非法计费参数及免费额度过期均断言发送0次。

最坏原价单次：(997952×4.8+1200×48)/1000000 = 4.8477696元；5次上界24.238848元，与预检一致，低于30元，计算独立于免费额度、折扣及乐观Token估计。16,000字节仍不等于可靠Token上界；60000仍为累计实际usage目标，不是事前严格输入预算。账户账单、其他应用调用和供应商计费不由单次本地内存账本控制。

保持：最多5请求、4工具、1200输出、60000 usage目标、16000字节、90秒、零重试、30元辅助保护；usage未知/超时保留预留并停止、模型/Endpoint/计费模式检查不变。未修改FREE_TIER静态历史快照或推算新的绝对到期日期。

## 用户控制台确认与真实调用边界

本轮用户明确补充：qwen-plus、华北2北京、用户本人阿里云账号的默认业务空间，Workspace ws-6sp1nti4y4d07vun，当前Key归属该空间；免费额度用完即停已开启，余额947.82K/1M Token，显示剩余63天。以上记录为“用户已在控制台确认”，不是API验证。此前预检待确认的Key归属与开关事项已被这次人工确认补齐，无需仍列为未回答。程序未读取或输出Key；本轮没有调用任何真实模型或授权接口。

截至本次核验日，价格日期技术阻塞已解除。READY仅表示按本次公开核实与用户确认可进入新的授权流程，不代表已授予真实调用权限，不承诺真实Qwen验收成功。跨日、配置/模型/资料变化或免费额度状态变化需重新预检；仍须新的独立一次性调用授权与执行绑定，不能复用历史授权。

## 最终离线验收

- 修改前指定两项：2项，0通过、1失败、1错误、0跳过，均为真实日历日期与历史核验日不一致。
- 费用专项（test_cost_budget、test_free_tier）：29项通过，0失败、0错误、0跳过；本轮新增5项测试。日志：tmp/price-maintenance-special.log。
- 全量命令：python -X utf8 -m unittest discover -s tests -v。实际360项，360通过、0失败、0错误、0跳过，耗时203.492秒，退出码0。原有355项保留，新增5项，无新增回归。日志：tmp/price-maintenance-full.log。
- 全部使用现有离线夹具、Mock或Replay；没有真实HTTP模型请求。测试控制台中的模拟业务错误、simulation字段和CLI输出是既有测试样本输出，不代表真实调查或测试失败。
- git diff --check通过；生产费用模块全部函数/类AST与HEAD一致。实际北京时间2026-11-13下直接执行纯check_live_price校验成功，无Transport发送。
- 本轮只修改cost_budget.py、两个费用测试文件，新增共享测试时钟和本报告。原有未跟踪文件均保留，未暂存、未commit、未push。

PRICE_DATE_FIX: PASS

OFFLINE_TESTS: PASS

LIVE_PREFLIGHT: READY（仅指2026-11-13本轮价格/费用前置技术检查，结合用户本次控制台确认；并非真实API验证或执行授权。）

本轮未发现仍未解决的价格日期或离线测试阻塞。Key归属和免费额度用完即停已由用户明确确认，不再列为待确认事项；仍未进行程序端身份或开关核实。下一次执行仍须独立一次性明确授权及当次执行绑定/数据一致性预检，跨北京时间日期必须重新核实价格。本轮完成即停止，不执行真实调查。
