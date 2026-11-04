# 2026-11-02 真实 Qwen Agent 单次调查验收

## 结论
**本次真实调查失败，最终validation_failed。** Qwen自主完成search→get→explain，第三轮输出786 Token、finish_reason=stop，完整JSON经动作Schema接受；没有复现上次1200 Token截断。但随后完整业务核验拒绝解释，未进入pending_human_review，未产生合理stop。不能把输出完整或HTTP 200写成Agent整体验收成功。

## 授权与版本
本轮用户明确授权一次调查，新授权ID：gree-acceptance-20261102-3ac37fd9409c。已经消费，禁止复用或再次调用。历史授权未使用。main HEAD：daf1e32f9c03c55bb6d421518f8c24be95b1dc20，工作区仍含此前未提交修复。此次未修改代码、Prompt、数据、证据或模型输出，未commit/push。执行前逐个比对预检绑定的全部Python代码及Prompt哈希；执行后再次比对通过。未覆盖或删除两个原有PDF。
Prompt SHA-256：a5b2a32bd7db23d350bce7843a085c599ed1c8d72bbd4f338ca64221b02943b6

来源快照：outputs/final_revision/20261017T093152-d80de1cefa。现有agent_live.prepare重核来源、45可信事实和9项resolved冲突通过；执行后release_hashes全部文件哈希不变。
事实白名单：net_profit、operating_cashflow、cash_2、cash_6。
证据白名单：F_net_profit、F_operating_cashflow、F_FINAL_cash_2、F_FINAL_cash_6、E07_28、E18。
逐轮检查外发事实/证据目录和可见证据标识均在限定范围；没有外发完整PDF或金融组Word/Excel。

## 执行路径与预算
使用原python -m tracelab.agent_live入口，--execute-real及--confirm-free-tier-workspace，新独立授权ID。未另写传输、未Mock/Replay、未自动重试。simulation=false、llm_called=true、decision_mode=qwen_real。
qwen-plus，北京Endpoint：
https://ws-6sp1nti4y4d07vun.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions
Key由现有环境配置读取，没有打印或记录。
上限5模型请求、4工具、1200单次输出、60000实际usage目标、90秒超时、0重试，辅助30元保护。免费额度及同一业务空间、用完即停为用户人工确认，未经API验证。60000仍不是发送前严格总Token上界。

## 真实逐轮结果
| 轮次 | 动作 | HTTP / finish_reason | 输入Token | 输出Token | 耗时秒 |
|---|---|---|---:|---:|---:|
| 1 | search | 200 / stop | 2983 | 27 | 1.756 |
| 2 | get | 200 / stop | 3609 | 18 | 1.571 |
| 3 | explain | 200 / stop | 3509 | 786 | 18.324 |

北京时间约22:32:27—22:32:49。首轮search query=净利润与经营活动现金流量净额差异原因，metric_id=operating_cashflow，命中F_operating_cashflow、E07_28、E18、F_FINAL_cash_6、F_FINAL_cash_2。第二轮get读取E07_28。第三轮提交两条结论和一个未决问题。
实际3模型请求、2工具调用、0 fact_get；停止后没有使用剩余两次请求。没有超时、缺usage或免费额度403，未触发60000或30元上限。

## 程序核验
model_status=valid_action仅说明动作结构合法，不表示财务解释通过。checks.json保留以下11条错误（包含同类错误对不同项目分别报告）：
- 结论1引用不存在的证据
- 结论1财务项目缺少相关证据
- 结论2引文与原文不一致
- 结论2金额未关联该条财务项目
- 结论2金额未关联该条财务项目
- 自由文本含未结构化数字，金额必须放入amounts供精确核验
- 结论1解释或支持边界过长
- 结论2会计层级或关系未获输入核验支持
- 结论2会计关系未关联所引用项目
- 结论2会计层级或关系未获输入核验支持
- 结论2会计关系未关联所引用项目

具体解释：F_net_profit虽在授权目录，却不在本次search/get已检索集合，不能用作结论证据；E07_28引文未逐字匹配；cash_2/cash_6金额未列入该条metric_ids；自由文本仍重复年份、金额和百分比；会计关系未获输入核验支持。金额没有被程序报为数值不一致，并不意味着其所属结论合法。

## 模型输出与人工复核边界
analysis.json为模型原始完整候选解释，未经修补。模型在net_profit引用中写出“归属于母公司股东的净利润”，存在净利润/归母净利润层级混淆风险；还写“覆盖全部现金流量净额变动幅度”，不能当作已获证据证明的结论。这些为事后只读观察，不替代checks.json，也不代表金融组认可。
manual_review列表只是程序生成的待复核事项，没有金融组签署或完成业务复核。完整解释已被程序拒绝，不应作为已核验归因用于展示或决策。会计勾稽不证明经营因果。

## 用量与费用
服务实际usage：输入10101、输出831，总计10932 Token。最终解释786 Token，不等于全次输出831。按既有未折扣公开单价核算0.0097428元，仅为usage_priced_not_invoice；实际现金扣款仍未知，不能声称已验证0元。免费额度剩余未重新读取。
日志reserved_cny=14.5433088是三次历史预留金额之和，不是实际花费或仍冻结金额；每次先预留4.8477696，再按usage核算。30元辅助保护保留，未超预算。

## 日志与验收工件
根目录：outputs\agent_acceptance\20261102-authorized-3409dac866
真实运行目录：outputs\agent_acceptance\20261102-authorized-3409dac866\live\20261102T143227-e1ab7ac1f3
- execution_binding.json：执行前哈希/快照绑定及本轮用户授权；其中real_request_started=false是执行前状态，最终真实状态见completion_audit.json。
- console.log：原入口标准输出与退出结果（退出码1，核验失败）。
- live/authorizations/新授权ID.json：独占的一次性消费记录。
- 运行目录authorization.json、source_audit.json、code_hashes.json。
- investigation/input.json、plan.json、events.jsonl、decisions/01.json—03.json、analysis.json、checks.json、result.json、manifest.json。
- completion_audit.json：执行后代码/数据/Prompt不变及逐轮摘要。
- audit_files_sha256.json：交付时审计文件哈希索引。

## 最终处置
本轮唯一调查已结束，无修补、无重试、无第二次调查、无commit/push。此次证明完整explain可在当前输出预算内返回，但只是一轮实测，不能保证截断问题普遍解决。后续若要修复引用纪律或解释组织，需要另行任务；再次真实调用必须重新明确授权。本轮立即停止。
