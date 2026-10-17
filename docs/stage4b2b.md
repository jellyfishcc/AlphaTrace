# 第四阶段 B-2B：修订版增量验收与真实调查预检

2026-10-17。本轮只离线处理，无真实API请求、密钥内容读取、提交或推送。

- 实际读取“最终版(1)”Word、Excel；保存18处单元格差异、Word差异、新旧文件哈希。
- 原9条冲突逐项保留并标记resolved，未解决0条。旧描述和旧值保留作历史，当前状态以status及verification为准。
- 31项核心金额未变；复用既有计算，重新核对利润桥接、成本八项及现金流关系。其他经营收付款两期已列示明细合计也精确一致，空白未填零。
- 新快照重新建立来源信任。事实44→45，恢复fair_value_income；cash_26、cash_27仍只有基期，未开放查询或同比计算，fee_income仍阻断。

## 本次输出

- 修订快照：`outputs/final_revision/20261017T093152-d80de1cefa/`。
- 新附件：该目录inputs；冲突验收：conflicts.json；差异及勾稽：revision_checks.json、revision_cells.json、revision_word.diff。
- 预检：`outputs/agent_preflight/20261017T093813-c22073fa16/preflight.json`。
- 明确白名单：同目录export_scope.json；未真实发送的首轮请求：first_request_not_called.json。
- 假响应轨迹：同目录offline_replay，3次模拟决策，状态pending_human_review。合成用量不是实际消耗，也不证明自主调查能力。
- 最终全量日志：`outputs/stage4b2b/20261017/tests.log`。

## 真实调查建议范围

事实：`net_profit`、`operating_cashflow`、`cash_2`（销售收款）、`cash_6`（其他经营收款）。

证据：`F_net_profit`、`F_operating_cashflow`、`F_FINAL_cash_2`、`F_FINAL_cash_6`、`E07_28`、`E18`。

四项事实的已核实元金额作为必要初始摘要，避免逐项取数占满请求次数；已检索的对应短引文继续保留，防止历史压缩丢失必要引用。未检索的引用不能凭摘要直接通过验收。其他事实虽可本地查询，不自动扩大这次外发范围。

配置已按变量名和注册表大小元数据检查，匹配既有百炼北京工作空间；未读取密钥内容，未验证密钥有效性、权限、余额或连通性。

建议一次调查，预计3—5次请求，最多5轮/5请求/4工具调用；qwen-plus，每次1200输出Token、90秒、零重试。累计预算60000为保守预留控制，不是准确消耗或人民币保证。遇到未知用量、异常、重复动作或预算耗尽会停止。

旧文档存在历史价格估算，但本轮未重新确认当前计费单价，项目没有可执行的人民币硬限额配置。因此预检费用为未知，不记录0元。仍可能因超时、截断、格式/引用失败产生费用而没有可验收结论。下一次须明确授权数据白名单、一次调查的请求上限和费用容忍范围，再准备真实执行入口。

## 离线运行

```powershell
$py = 'python'
& $py -X utf8 -m tracelab.agent_preflight --stage2-run outputs/final_revision/20261017T093152-d80de1cefa
```

重建修订快照使用 `python -m tracelab.final_revision --source <两份修订附件目录> --previous outputs/final_release/20261017T001129-fb6ba35805`，每次独立生成，不覆盖旧版本。

本轮新增final_revision.py、agent_preflight.py和10项定向测试；final_release.py仅调整resolved冲突的事实准入，qwen_decider.py新增最多4项显式授权初始摘要。未改核心财务公式。定向10项通过，最终全量153项通过、0失败、0跳过；全量仅执行一次。当前为ready_pending_authorization，不是已授权真实调用。
