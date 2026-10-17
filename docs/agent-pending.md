# 第四阶段 Agent 重复查询修复与保留事项（2026-10-17 晚）

本轮沿用既有第四阶段架构，只调整上下文、动作预算约束和离线验收。没有新增阶段编号，没有真实 API 调用，没有读取密钥、复用授权或改动金融资料/公式/来源核验规则。Agent 仍是核心目标，第四阶段未全部完成。

## 失败定位：代码与实际请求共同支持的结论

唯一真实运行仍为 `outputs/agent_live/20261017T095133-282a117e04`，结果没有改写。五轮顺序是 cash_2 → cash_6 → net_profit → operating_cashflow → cash_2，均为 fact_get；第五轮 repeated_action，四次工具预算耗尽，没有证据查询或 explain。

逐轮读取实际 decisions/01—05.json 后确认：

- 每轮 initial_facts 都包含四项事实的 base/current/change 原始元金额。因此不能把失败解释成金额没进入模型上下文。
- 原 `QwenDecider.context` 的 queried_facts 只保留最近两项详情。第四轮丢失 cash_2 查询详情，第五轮仅剩 net_profit、operating_cashflow；omissions 有 earlier_fact_details，但没有独立完整的已查标识表。
- 本次 history 保留了全部四次动作，initial_facts 也始终包含 cash_2，因此“历史完全丢失”不是事实。history 只有动作和参数，没有检索结果摘要或明确状态。
- 原 Prompt 要求不重复请求，却没有明确 initial_facts 已足够、何时转向证据，以及如何为 search/get 和最终动作留预算。
- 原规则禁止相同动作的第二次调用，但不禁止第一次重复读取 initial_facts。4次可用工具全部花在已有事实上；剩余轮数/工具数虽然传给模型，没有相应事实查询预算保护。

这些是已证实的软件缺口与模型行为；仅凭一次实测不能断言模型为什么忽略了已有信息，或新版 Prompt 一定使真实模型正确决策。脱敏字段摘录与原记录 SHA-256 见 `tests/fixtures/agent_repeated_fact_failure.json`；既有第三阶段失败样本不是本次 Agent 重复动作的同一份样本。

## 最小修改

- `tracelab/qwen_decider.py`：新增完整 progress 标识表，区分初始提供、已查询、尚未查询、已可用、允许查询和禁止重查；查询详情仍受大小限制，完整状态不随最近详情/六条history截断而消失。search 摘要记录参数和命中标识，包括空结果。新增下一步建议。
- 已有事实的 fact_get 返回 fact_already_available，仍为 validation_failed；相同已执行动作继续保留 repeated_action。无已检索原文时为证据搜索/读取保留两次工具空间，已命中未get时保留一次，并为最后 explain/stop 留一轮。必要但未提供的事实仍可在预算允许时查询。程序不偷偷改动作、不自动重试、不强行生成解释。
- `prompts/agent_decision_v1.txt`：在原版本文件内明确事实复用、查询状态、证据优先、预算、合理stop与不足范围；每次审计已有Prompt哈希可区分修改前后。
- `tracelab/agent.py`：结果保存实际 retrieval_audit（查询参数、命中及get标识）和 evidence_gap；违规失败不产生成功结论。
- `tracelab/agent_offline.py`：沿用现有Replay入口，投影到真实入口同样的4项事实/6项证据范围，初始提供事实，支持 explain/insufficient 两种明确标注的合成响应。旧离线演示使用完整payload执行检索，虽决策器外发过滤，工具结果可能包含范围外条目；新演示用现有 project 统一工具范围。
- `tests/test_agent_progress.py`：新增10项离线测试；`tests/test_qwen_decider.py` 更新最后一轮工具请求的提前阻断预期，并继续测试请求总量硬上限。

动作白名单、外发范围、原始来源校验、金额/引用校验、预算上限、零重试和一次性真实授权保护均保留。`agent_live.py`、`agent_preflight.py`、财务公式、原始数据和 report_check 均未修改。

## 实际离线验收

```powershell
python -X utf8 -m tracelab.agent_offline --stage2-run outputs/final_revision/20261017T093152-d80de1cefa --scenario explain
python -X utf8 -m tracelab.agent_offline --stage2-run outputs/final_revision/20261017T093152-d80de1cefa --scenario insufficient
python -X utf8 -m unittest discover -s tests -v
```

需要现有本地修订快照及 pypdf；通用环境/临时目录说明沿用 README 与交付文档。两个Replay均使用相同真实财务来源核验和5轮/4工具/5请求预算，不需要API配置。

| 路径 | 实际轨迹 | 结果与本地记录 |
|---|---|---|
| A | 已有4项事实 → search(operating_cashflow) → get(E18) → explain | pending_human_review，errors=[]；`outputs/agent_replay/20261017T145338-a5f21edd2e` |
| B | 已有4项事实 → search(operating_cashflow) → get(E18) → stop | insufficient_evidence，errors=[]；`outputs/agent_replay/20261017T145350-8c2271e6b8` |

两条路径各3次合成决策请求、2次工具执行，simulation=true、llm_called=false、real_request_attempts=0。请求体字节数为9634、11128、12126，均小于16000；保守预算预留总计37256，小于60000。使用量是测试构造，不能宣传为真实Token/费用。

检索仅覆盖授权子集，命中 F_operating_cashflow、E07_28、E18、F_FINAL_cash_2、F_FINAL_cash_6，随后读取E18。B明确记录：汇总金额不足以量化经营原因，缺少对应明细支持；没有将局部不足写成全库没有证据。A提交的结构化内容是待验证假设，程序基础校验通过仍需人工判断原文是否足以支持，不是已经证明因果。

实际完整测试：183项通过、0失败、0跳过，用时71.683秒；日志 `outputs/agent-repair/full-tests.log`。定向Agent测试28项通过、0失败、0跳过；日志 `outputs/agent-repair/agent-tests.log`。测试覆盖两条路径、空检索、初始事实重查、必要新事实、完整标识保留、证据与末轮预算保护，以及重复/非法/越权动作、错误金额和未检索引用拒绝。旧授权一次性、超时、用量未知、请求预算、来源回执等回归仍执行。

## 下一次真实调查的前置条件与剩余风险

本轮要求的代码与离线路径前置条件具备；真实模型行为尚未验收。下一次真实调用仍需要新的明确授权和与当前代码/Prompt相匹配的预检范围确认；本轮没有生成真实执行授权，也没有尝试旧授权。原始真实失败日志及一次性授权标记原样保留。

尚未解决：模型可能仍选择被禁止动作并立即失败；Replay预设动作不能证明模型会自主规划；原文截断/关键词检索和有限白名单会遗漏资料；固定预算可能不足以完成复杂解释；完整最终explain尚无真实成功记录。第三阶段的金额关联、自由文本百分比、本期与同比混用失败继续由严格规则保护，未放宽也未重新真实验收。经营因果与解释强度仍需人工复核。

本轮完成后停止，不自动安排新的开发阶段。
