# 最小本地调查编排（2026-10-16）

本轮仅Mock。无真实API、无密钥读取、无网络检索、无任意代码执行，无commit/push。
原工作区已有未提交改动保留。本轮只新增agent.py、test_agent.py及本文，不改财务计算、原始证据或stage3校验。

## 已实现与边界

tracelab/agent.py复用stage3_input.prepare对事实和原文重新核验，复用已有investigation_plan.json，并与prepare_investigation读取metrics产生的信号核对。
没有写死公司或公司结论。当前只接入focused已核实的三项事实、五段原文；不把E01—E07整套材料无条件升级为已核验证据。

LocalEvidence真实执行本地操作：list列出编号、关联项目、来源、页码；search按项目或关键词检索，也能使用计划中的question_index；get按ID返回原文和出处。
检索为简单词面匹配及中文双字片段排序，不是语义检索，不保证召回率。未知ID拒绝，工具返回深拷贝，不修改原资料。

Decider.decide(state)是可替换决策接口。state包含计算信号产生的目标、候选问题、事实、会计约束和完整工具历史。
本轮只有MockDecider可从CLI启动；没有真实Qwen决策器或execute选项，也不会访问API Key。

动作格式为JSON兼容对象，顶层只能有action和arguments：

| action | arguments | 行为 |
| --- | --- | --- |
| list | {} | 返回证据目录 |
| search | query、metric_id或question_index | 检索原文；question_index选择已有计划问题 |
| get | evidence_id | 获取指定证据 |
| explain | analysis | 按现有stage3 Schema提交候选解释并校验 |
| stop | reason，可选analysis | 标记证据不足；若附带解释则同样校验 |

非法动作、未知字段和参数拒绝；不将决策解释为Python代码或动态工具名称。
默认最多六轮、四次工具调用，配置允许范围均为一至二十。
输入payload/plan及单次工具结果上限各100000 UTF-8字节，决策30000，累计决策上下文500000，关键词300字符。
达到轮数/工具上限是insufficient_evidence，stop_reason明确记录是资源上限，不冒称已穷尽全部财务证据。

解释只能引用本次search/get已返回的证据，list目录本身不能支撑结论。
复用stage3.validate，不放宽金额、关联、引用、层级和口径规则。
结果状态：pending_human_review、validation_failed、insufficient_evidence。
若stop附带错误解释，仍保留全部检查错误并以validation_failed结束，不能用证据不足掩盖错误。
通过基础检查也不证明经营因果；模拟假设只表示待复核候选。

## 运行与真实Mock演示记录

```powershell
cd D:\Projects\TraceLab
& 'C:\Users\65751\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -m tracelab.agent --stage2-run outputs/stage2/20261016T053315-83447d4dedf0
```

实际输出outputs/agent/20261016T140940-ee9d2b94f0。
四轮：Mock选择list→按首个候选问题search→get E07_29→提交预设待验证假设。
真实Python工具调用三次，最终pending_human_review，simulation=true，llm_called=false。
该假设只是“相关披露是否足以解释调查目标中的变化”，并明确证据尚不足以确认经营因果，不是模型自主发现。

- events.jsonl：每轮决策、实际工具参数及完整结果、错误及最终状态。
- input.json / plan.json：核验事实、证据及已有调查计划快照。
- analysis.json / checks.json：模拟候选解释及原校验器结果。
- result.json：最终状态、上限、实际轮数、检索证据ID与人工复核事项。
- manifest.json：模拟标识、输入核验来源、源文件哈希和编排代码哈希。

## 测试

python -m unittest discover -s tests：96项全部通过，包含原84项及新增12项。
新增测试覆盖真实样本载入、信号目标、问题检索、非法动作与ID、停止、轮数/工具/输入大小限制、未取回证据拒绝、错误金额与引文、多错误保留、完整日志。
Mock编排测试禁止socket、模型调用函数及配置读取；全部通过，不产生真实API请求。

## 下一阶段所缺内容

Decider接口可接Qwen，但尚需实现决策提示词和响应解析、每轮调用日志与用量、总调用预算及外发审查；必须重新获得用户授权。
接入时应显式区分mock/真实来源，并把当前默认simulation标记改为由受控运行模式决定，不能将真实决策仍记作Mock或反之。
还需验证Qwen能否遵守动作协议、选择合理调查方向；目前没有自主决策能力证据。
不应将本轮模拟成功覆盖V3真实分析validation_failed的历史状态。

金融组仍需确认本期利润/现金流差异与同比增长的解释边界、保证金调节项的支持范围、缺失组成项目和合并范围影响。
局部公开证据不能支撑全量经营归因，不能自动推断盈利质量改善。
本轮停止，不进入真实调用或前端开发。
