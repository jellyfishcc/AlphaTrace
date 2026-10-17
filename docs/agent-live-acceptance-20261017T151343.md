# 第四阶段真实 Qwen 有限调查验收记录

时间：2026-10-17 23:13—23:14（北京时间）。本次为用户新授权的唯一一次调查，不是 Replay。未修改源码、财务公式、来源规则或输出校验，未重试、未启动第二次调查、未 commit/push。

**验收分类：情况 D，真实调查失败；同时保留已实际完成的 search/get 进展。完整有限调查工程闭环尚未通过。**

最终 `validation_failed`，错误 `incomplete_response`。第三次响应 HTTP 200，但 `finish_reason=length`，输出达到单次1200 Token上限。可见文本以 explain 开头，但JSON不完整，未被解析为有效动作，未提交合规解释或合理stop。不能把HTTP成功或部分解释片段写成验收通过。

## 授权、版本与执行前检查

- 一次性授权：`gree-acceptance-20261017-cda49f231621`，由用户明确同意本次外发范围及既定预算内费用；已使用，不能再次使用。
- 分支 `main`，Git commit：`5e759b3f78a2a7418a9e2c828de480e33edc5342`。执行前工作区干净，所有受检代码和Prompt在运行后仍一致。
- 代码及Prompt集合摘要：`5c4daaa6ddb63cf3f005980254b8e817383487ea8beb2adfa279ea12600f4e89`。
- Prompt文件：`prompts/agent_decision_v1.txt`；SHA-256：`e4a276420d082893203a99f2dff6492d80dcb409c8e820e3baf797128bff2bfd`。
- 数据：`outputs/final_revision/20261017T093152-d80de1cefa`；manifest SHA-256：`08e359e416ad2db2a3921feacca2cafc7b9db1f38b472a4a3b1a10db2b4ade33`；release_hashes SHA-256：`2b48dad9e56d0448a3d9c68eaa5dea5036ab8dec0d272d49bfd58276906d2495`。
- 预检根目录：`outputs/agent_acceptance/20261017T150554-20125dc3a2`；新预检为其下 `preflight/20261017T150644-bd8eba404e/preflight.json` 及同目录 `export_scope.json`。
- 独立版本绑定 `acceptance_binding.json` 的 SHA-256：`b955f63b8b361a4bed6aa90d6b4c89cec41139a6a3e148d5da611aa6604513f2`。运行前再次比对代码、Prompt、预检、快照及旧授权哈希，并通过现有 `agent_live.prepare` 重核来源。记录见同目录 `authorization_recheck.json`、`execution_recheck.json`、`authorization_received.json`。
- 45项可信事实准入、9条冲突全部resolved；运行后再次检查快照清单文件哈希不变。旧授权文件及历史运行原样保留。
- 本轮预检重新执行定向72项、全量183项测试，均0失败、0跳过。日志为预检根目录的 `targeted-tests.log`、`full-tests.log`。这些是离线软件测试，不能替代真实验收。

执行仅调用原 `tracelab.agent_live.main` 和 `LiveBailianTransport`；本地执行辅助脚本只核对版本和调用现有入口，不生成模型动作、不替代传输。运行没有使用ReplayTransport或MockDecider。

## 真实运行与边界

运行目录：`outputs/agent_live/20261017T151343-d0d3b954f5`。真实标志为 `simulation=false`、`llm_called=true`、`decision_mode=qwen_real`。

服务为已授权百炼北京工作空间，模型 `qwen-plus`。仅允许一次调查、最多5轮/5请求/4工具，单次最多1200输出Token、总保守预算参数60000、每次正文16000字节、90秒超时、0自动重试。

财务事实白名单：`net_profit`、`operating_cashflow`、`cash_2`、`cash_6`。

证据白名单：`F_net_profit`、`F_operating_cashflow`、`F_FINAL_cash_2`、`F_FINAL_cash_6`、`E07_28`、`E18`。

逐轮外发检查确认事实、证据目录、已检索原文标识及初始金额均在上述范围且与核验输入一致；Prompt摘要和模型参数一致。首次真实请求与预检 `live_first_request_not_called.json` 逐字段相同。没有外发完整PDF、金融组Word/Excel、私有附件或其他事实。密钥仅由现有客户端用于认证，未打印或写入审计正文。检查结果保存在运行根目录 `post_run_review.json`。

## 每轮真实动作与执行结果

下表记录实际返回，未用模拟轨迹替换。

| 轮次 | 模型实际返回及参数 | 执行结果 | 证据文件 |
|---|---|---|---|
| 1 | `search`，`query=净利润与经营活动现金流量净额差异原因`，`metric_id=net_profit` | 成功，命中 `E07_28`、`F_net_profit` | `investigation/decisions/01.json`、`investigation/events.jsonl` |
| 2 | `get`，`evidence_id=F_operating_cashflow` | 成功读取经营现金流净额原文，印刷88/PDF89页 | `investigation/decisions/02.json`、`investigation/events.jsonl` |
| 3 | 原始文本以 `action=explain` 开头，arguments.analysis未完整输出 | `finish_reason=length`，JSON不完整；`incomplete_response`，无有效动作、未执行工具 | `investigation/decisions/03.json` |

第二轮get选择来自授权证据目录，**不是**第一轮search的命中项；现有协议允许按目录ID读取，不应将其描述为“成功追踪了全部搜索命中”。它确实读取了真实相关原文，但没有读取现金收款两个分项的原文。

实际：3轮、3次真实请求、2次工具调用，0次fact_get；没有发生已有事实重复查询。已检索集合为 `E07_28`、`F_net_profit`、`F_operating_cashflow`。没有合规explain、没有stop。最后一个有效状态是完成第二轮get。

## 用量与耗时

| 轮次 | HTTP / finish_reason | 输入Token | 输出Token | 请求耗时（秒） |
|---|---|---:|---:|---:|
| 1 | 200 / stop | 2672 | 31 | 4.312 |
| 2 | 200 / stop | 3088 | 21 | 2.563 |
| 3 | 200 / length | 3069 | 1200 | 28.890 |
| 合计 | 服务实际返回用量 | 8829 | 1252 | 35.765 |

总Token为10081；1252是三次响应合计，不是突破单次1200上限。保守预算预留合计35626，未超过60000；没有使用剩余两次请求。耗时为模型请求耗时合计，不含执行前本地来源重核。人民币实际费用未知，未用Token预算冒充费用上限。

## 程序核验与可见片段诊断

来源、页码、输入金额和授权范围在调用前由既有加载器核验通过；search/get参数和白名单验证通过。第三轮在响应完整性检查处停止，尚未进入完整动作解析、Schema检查以及最终财务金额/引文/比较口径校验。因此不能声称最终金额、引用和因果解释通过验收。

程序没有生成 `analysis.json` 或 `checks.json`，因为没有有效的完整分析。原始可见响应完整保留于 `investigation/decisions/03.json`，没有补齐JSON、修改内容或再次提交。

只读事后诊断另外观察到：

- 可见的12个完整amounts对象片段与本次初始可信元金额一致；这只说明这些片段相符，不代表整体财务解释已通过校验。
- 片段引用了尚未检索的 `F_FINAL_cash_2`、`F_FINAL_cash_6`。在目录中存在不等于已获取其原文。
- 可见statement含金额/年份/百分比等数字，与既有Prompt的自由文本数字限制不符。
- 可见片段出现“无需调节”“可直接归因”等强断言及未经所读证据支持的原因猜测。截断后没有完整限定语或合规终态，不能作为经营结论采用。

以上标为片段诊断，保存在 `post_run_review.json.fragment_diagnostics_only`，**不是**对补写或修复后的响应运行正式校验。本次唯一正式失败原因为 `incomplete_response`。

## 与上一次真实失败比较

| 项目 | 旧运行 `20261017T095133-282a117e04` | 本运行 |
|---|---|---|
| 事实查询 | 四次fact_get，第五次重复cash_2被拒绝 | 无fact_get，没有复发该重复行为 |
| 证据调查 | 没有search/get | 自主search一次、get一次 |
| 最终输出 | 无解释提交 | 尝试输出explain，但达到长度上限而截断 |
| 最终状态 | validation_failed / repeated_action | validation_failed / incomplete_response |
| 工程闭环 | 未通过 | 仍未通过，但有真实证据调查进展 |

本次事实金额复用的可见行为有所改善，但一次实测不能证明重复查询问题在所有情形下彻底解决。预算及失败保护有效阻断了不完整响应，没有把部分进展包装成成功。

## 验收结论、业务边界与展示口径

按用户分类归入**D**：真实调查失败。虽然取得了情况C所描述的部分进展，但最终明确为validation_failed，不能改列A或B。

尚未达到“真实模型驱动的有限调查工程闭环通过程序基础验收”。金融业务验收更未完成：没有合规候选解释可批准；现金流入变化是否足以解释净利润与现金流分化、合并范围可比性、经营原因强度及所缺证据仍需金融组复核。不把本期受限资金当同比贡献，不由现金流增长推断盈利质量改善。

可以用于初赛展示的真实新成果：**修复后真实Qwen自主执行了证据搜索和原文读取，未重复查询已有事实；解释输出截断时系统保留审计并安全停止。** 必须同时展示最终失败状态及解释未验收的限制。不能写成“完整Agent闭环成功”“财务归因已通过”或“经营因果已证明”，不能使用截断片段作为获核验结论。

尚未解决的技术问题为有限输出长度下的解释完整性、未检索引用、自由文本数字纪律及解释强度；这里只记录，不在本轮修改、重试或安排新阶段。

完整审计索引：运行根目录的 `authorization.json`、`source_audit.json`、`code_hashes.json`、`post_run_review.json`、`audit_files_sha256.json`；子目录的 `input.json`、`plan.json`、`events.jsonl`、`decisions/01—03.json`、`result.json`、`manifest.json`。本次一次性标记位于 `outputs/agent_live/authorizations/gree-acceptance-20261017-cda49f231621.json`，保留且不得复用。

本次唯一调查已结束。停止，不自动修改代码、不再调用模型、不提交或推送。
