# 第四阶段保留事项（2026-10-17）

Agent 自主调查仍是核心技术目标；本轮仅调整交付优先级，没有删除或替换 QwenDecider、接口、Prompt、测试、日志和真实运行记录。第四阶段不能标为全部完成。以下是已有问题的交接，不是本轮开发计划。

| 已知问题 | 证据与代码位置 | 后续修复方向（本轮未实施） |
|---|---|---|
| 重复事实查询 | 真实运行 `outputs/agent_live/20261017T095133-282a117e04` 第五次重复 fact_get(cash_2)；`qwen_decider.py:check_action` 的 repeated_action 保护终止执行 | 保留防重复保护，利用查询历史避免重复动作；先离线回放验证 |
| 已有上下文利用不足 | `qwen_decider.py:context` 将授权事实、queried_facts、history、remaining 传入；实际模型仍只查询事实 | 检查实际请求的上下文与提示词信息组织；原因尚未通过对照实验确认，不能断言仅是模型问题 |
| 证据检索预算不足 | 4次工具调用全部 fact_get；`agent.py:investigate`、`qwen_decider.py:Budget`、`prompts/agent_decision_v1.txt` | 明确证据缺口和剩余预算，验证能进入 search/get，再形成有引文解释；不得放宽引用校验 |
| 最终 explain 尚未真实验收 | 此次 Agent 没有 explain，不能说最终解释校验已通过或已经失败；第三阶段曾有真实 validation_failed，详见 `focused-output-fix.md`、`tests/fixtures/qwen_focused_validation_failure.json` | 保留 `stage3.py:validate` 和 `analysis_contract.py` 严格规则；检查金额与metric_ids关联、百分比自由文本及本期/同比口径，离线通过后另行授权真实验收 |

完整目标仍是：分析问题 → 选择工具 → 查询事实 → 检索年报证据 → 提出解释 → 严格核验 → 人工复核。本轮没有重新运行模型，没有调整规划策略，没有消耗新的 API 预算。

历史依据：[唯一真实 Agent 记录](stage4b2b-live-result.md)、[第三阶段真实分析](stage3-test-handoff.md)。本轮完成后停止，等待用户验收。
