# 第 4B-2B 阶段：唯一真实 Agent 调查验收

2026-10-17，本次用户明确授权的一次调查已结束，不得复用授权再次运行。

- 来源：`outputs/final_revision/20261017T093152-d80de1cefa`，9 条差异 resolved，45 项事实重新通过来源加载检查。
- 运行：`outputs/agent_live/20261017T095133-282a117e04`。
- 真实标识：`simulation=false`，`llm_called=true`。
- 5 次 Qwen 请求全部 HTTP 200、finish_reason=stop，JSON 完整。请求耗时合计 4.640 秒（不含本地来源核验）。输入 12939 Token，输出 87 Token，人民币费用未知。
- 实际动作：fact_get(cash_2) → fact_get(cash_6) → fact_get(net_profit) → fact_get(operating_cashflow) → fact_get(cash_2)。最后一次被 repeated_action 拒绝，实际只执行 4 次工具调用。
- 结果：validation_failed；没有检索证据、没有提交 explain，所以不存在通过财务归因验收的结论。金额、引用及因果检查未进入最终分析阶段，不能记为通过。
- 白名单复核：每轮只有授权的 4 项事实、6 项证据目录；未发送内部文档或白名单外金额。没有重试、第二次调查、自动提交或推送。

## 本轮最小代码变更

- `tracelab/agent_live.py`：默认离线，显式 `--execute-real` 才构造真实传输；校验预检与来源哈希、严格投影工具范围、固定本次预算、一次性授权记录及审计文件。
- `tracelab/qwen_decider.py`：可固定预检对应的接口地址；缺少服务用量时立即停止，不执行候选动作。
- `tests/test_agent_live.py`：增加入口、白名单、来源变更、重复授权、接口变化和离线轨迹检查。
- 必要回归：52 项通过、0 失败、0 跳过。旧 153 项全量通过记录仍保留；本轮未重复全量运行。

## 审计位置

运行根目录的 `authorization.json`、`source_audit.json`、`code_hashes.json`、`post_run_review.json`、`offline_tests.log`；子目录 `investigation/decisions/` 保存每轮真实请求及原始可见响应、HTTP 状态、请求 ID、耗时和用量；`events.jsonl` 保存实际动作和工具结果；`result.json` 保存失败状态。无候选解释，因此没有伪造 analysis/checks 文件。

真实入口参数为 `--stage2-run`、`--preflight`、`--scope`，默认只做准备；实际执行额外需要 `--execute-real --authorization-id`。本次一次性标记保存在 `outputs/agent_live/authorizations/stage4b2b-20261017-once.json`，不得删除以重跑。下一次真实运行需新的用户授权。

下一步最值得改进：让决策器有效复用已提供事实，并为证据查询保留有限工具预算。此次实测未能验证证据调查及最终解释能力；后续经营因果、净利润口径与本期/同比区分仍需金融组复核。本轮到此停止。

后续离线修复：2026-10-17晚针对重复事实查询完成上下文及预算保护调整，详见[现有第四阶段修复记录](agent-pending.md)。本页唯一真实调用结果不变，离线Replay通过不代表真实模型成功。
