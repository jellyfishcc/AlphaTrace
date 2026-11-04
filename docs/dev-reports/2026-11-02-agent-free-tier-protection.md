# 2026-11-02 免费额度保护接入与真实 Agent 验收准备

## 结论
按本轮用户要求，将主要保护切换为人工确认的百炼免费额度“用完即停”，保留实际usage累计、5模型请求、4工具、1200单次输出、90秒超时、0重试及辅助30元预留。60000为调用后usage控制目标，不能保证单次在途请求不越过剩余目标。没有真实模型请求，没有commit/push，没有生成已批准授权。

## 实际配置核对
agent_live显式传model='qwen-plus'，bailian.configuration的显式参数优先于环境模型配置，不使用qwen-plus-latest。北京Endpoint：
https://ws-6sp1nti4y4d07vun.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions
现有configuration_presence检查显示北京工作空间匹配，进程Key变量名存在，Windows用户注册表Key存在性元数据通过，key_value_read=false。没有打印、写入或修改密钥。
用户在本轮另行明确确认：当前环境中的Key属于ws-6sp1nti4y4d07vun且与已启用免费额度用完即停的业务空间一致。**这是人工确认，不是程序/API验证**。运行前Endpoint仍逐次核对，错误模型/地域或缺Key拒发。

## 人工确认的额度状态
- 模型qwen-plus，地域北京。
- 总免费额度1,000,000 Token，人工查看时剩余958,750 Token。
- 到期2027-01-15，“用完即停”已开启。
- 来源：用户2026-11-02控制台确认及本轮业务空间补充确认；api_verified=false。
- 剩余额度是确认时快照，不是实时余额，也不保证被其他调用共享后仍有相同余额。

[阿里云官方免费额度说明](https://help.aliyun.com/zh/model-studio/new-free-quota)说明免费额度耗尽且开启用完即停时返回403 AllocationQuota.FreeTierOnly。该文档说明产品行为，不证明本账号开关状态。本轮未通过API验证开关或额度，也未访问真实推理服务。

## Tokenizer调查与Token目标
查阅官方模型信息、Token用量说明及相关文档，未取得可验证与当前托管qwen-plus版本及完整聊天模板一致的本地Tokenizer。不能将其他开源Qwen分词器直接视为此服务的精确计量器。参考：[官方用量说明](https://help.aliyun.com/en/model-studio/model-usage-statistics)、[qwen-plus模型信息](https://help.aliyun.cn/zh/model-studio/qwen-plus)。未调用在线Token计数服务，未外发数据。
UTF-8字节数+256只作为日志粗略估算，既不是实际usage，也不再用于累计Token拒发。16000字节输入大小限制仍保留，这是真实字节约束，不宣称等价于Token限制。
发送前检查已知实际累计Token，达到60000拒绝后续；同时要求剩余目标足以容纳最大输出。每次返回后累计prompt_tokens和completion_tokens；超过目标记录实际数量并失败停止。输入无法精确预量，因此单次请求可能越过目标，不是严格60000硬上限。usage缺失或异常立即停止，不把未知用量当零。

## 费用保护调整
CostLedger保留strict_bound原模式及原测试；新增usage_target模式用于显式人工确认的免费额度调查。辅助人民币预留仍按官方模型容量界和1200输出计算，不用字节估计伪装费用上界；按既有公开价格进行保守未折扣核算，30元超额拒发。usage已知时结算本地公开价，不代表实际扣款；免费额度实际抵扣无法由usage单独确认，所以cost仍不伪报为0元。
免费额度是主要保护，人民币目标0元；辅助30元不是独立绝对账单保证。超时、缺usage等保留预留并阻止后续；403耗尽固定记录free_tier_exhausted并终止，不自动重试。错误正文仅读取有界内容提取固定代码，不落盘服务端原文。其他403不误标为额度耗尽。
保留价格核实日期检查（当前核实日2026-11-02），未来跨日应重新核实价格。人工额度到期日开始保守阻断，不能把过期确认长期使用。

## 修改文件
- tracelab/cost_budget.py：新增Token模式与人工确认元数据，保留30元、请求数、未知费用和输入模型容量界校验；检查业务空间确认与到期。
- tracelab/qwen_decider.py：显式确认的LiveTransport使用usage_target账本；移除粗略字节累计作为发送预算的用途，替换为actual usage；日志声明目标非硬上限；识别free_tier_exhausted；保留全部原Schema与财务核验。
- tracelab/bailian.py：增加有界403错误码识别，既有配置/HTTP路径不变，不记录错误正文。
- tracelab/agent_live.py：移除上一轮必然失败的模型容量Token预留关卡，替换为--confirm-free-tier-workspace人工确认门；执行仍须--execute-real及新的authorization-id；授权日志记录人工确认来源。确认参数只是重现本轮人工确认，不是调用授权。
- tracelab/agent_preflight.py：记录人工额度信息、Token目标非硬上限及待确认费用状态。
- tests/test_free_tier.py：新增11项离线测试，包含多个子场景；原有238项测试保留。
本轮没有修改Prompt、Schema、agent.py、search/get、财务公式、可信事实或原始证据；Git中这些历史修复仍按原样保留，不将历史diff误计为本轮改动。

## 离线测试
新增用例验证正确qwen-plus/北京配置可经Mock发送一次；模型/地域/缺Key零发送；403固定错误码与无重试；其他403不误分类；超时/缺usage保留预留并停止；累计usage/第六次拒发；达到60000停止；单次超目标如实记录；字节估算不再拒发；辅助30元及usage模式；人工业务空间确认门。
单次1200通过实际传给Mock的body断言；四工具上限继续由原test_agent/test_agent_progress/test_stage4b1覆盖。所有真实HTTP函数只在Mock下被调用，无真实网络调用，财务核验原有正负例全部保留。
执行python -X utf8 -m unittest discover -s tests -v；TEMP/TMP为工作区tmp，PYTHONPATH为tmp/test-deps内现有pypdf 6.10.0。最终结果见末尾，日志tmp/agent-free-tier-tests.log。

## 数据与真实调查准备
复用现有agent_preflight及agent_live默认非执行入口，禁止socket、真实API与Key读取。预检目录：outputs/agent_free_tier_preflight_20261102/20261102T142503-db15353024。
快照outputs/final_revision/20261017T093152-d80de1cefa，原来源哈希验证与ExportScope检查，事实45项、冲突9项resolved、0未决（详见preflight.json）。
本次范围仍为事实net_profit、operating_cashflow、cash_2、cash_6；证据F_net_profit、F_operating_cashflow、F_FINAL_cash_2、F_FINAL_cash_6、E07_28、E18。没有扩大范围或外发数据。
业务问题：格力电器净利润下降但经营现金流净额增长的可能解释及证据边界。预期search→get→explain→完整validation→pending_human_review，证据不足允许说明检索范围及具体缺口后stop。HTTP成功或insufficient_evidence标签本身不代表业务验收。

## 风险与授权状态
在人工配置确认真实且仍有效、价格检查通过、离线测试通过的前提下，具备进入新授权环节的技术条件。没有通过API证实免费开关、Key归属或实时余额。其他调用共享额度、开关被改、到期、模型服务变化仍需关注；程序不会声称零费用账单已保证。60k可能被最后一次请求越过，未知usage停止可限制后续但无法撤销已发生的调用。
最终真实运行仍需用户另行明确授权；本轮不是实际执行授权。不得复用历史授权。无需为了本轮读取Key或发送试探性请求。新授权前应核对本轮代码/Prompt/数据哈希和配置，运行日志沿用outputs/agent_live/<run_id>/。原两个未跟踪PDF和所有历史报告保留。main未commit/push，本轮结束即停止。

## 最终验收结果
249项通过，0失败、0错误、0跳过（原238项+新增11项）。Ran 249 tests in 202.528s。完整日志SHA-256：`7e9079839637a42671e5c8f202eb15277574936b40a299f2354828ab6c1a099b`。git diff --check通过。
现有agent_live默认非执行入口带人工业务空间确认参数返回ready_pending_authorization、llm_called=false。free_tier_readiness.json已保存本轮代码哈希、人工确认来源、authorization=not_granted及token_target_is_hard_cap=false。离线验收通过，真实模型验收尚未执行。
