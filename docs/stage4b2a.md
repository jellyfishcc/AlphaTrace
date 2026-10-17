# 第四阶段 B-2A：Qwen 决策适配器与离线验证

日期：2026-10-17。保留未提交的 B-1 改动，增量实现；本轮没有真实 API 请求、真实密钥读取、提交或推送。没有改动财务计算公式或历史快照。

## 接入方式

`QwenDecider.decide(state)` 接入已有 Decider 协议，返回一个动作。编排器继续负责工具执行和 explain 的最终财务核验。没有新增 Agent 框架或独立 HTTP 客户端。

- `tracelab/qwen_decider.py`：动作校验、上下文筛选、预算、日志、Qwen 适配；复用 bailian.chat_body/as_response 与 stage3.call_api。
- `prompts/agent_decision_v1.txt`：独立调查决策提示词；不替换财务分析 V3 提示词。
- `tracelab/agent.py`：提供剩余轮数和工具次数，记录决策器实际模式及状态，保存 manifest。
- `tracelab/agent_offline.py`：只允许假响应演示，入口强制阻断网络、配置读取和真实调用函数。
- `tests/test_qwen_decider.py`：18 项离线测试；其余 B-1 文件及测试保留。

LiveBailianTransport 构造必须显式 authorized=True；配置和密钥只在未来真实 send 时惰性读取。此布尔参数不是用户授权的替代品。当前没有真实调用 CLI，只有 offline 演示入口；下一轮必须先确认外发范围及预算，再准备真实执行入口。假传输不读取配置。

## 每轮输入和权限

必须显式提供 ExportScope（允许外发的 fact_id、evidence_id 和授权说明），不能把“本地可查”视为“允许外发”。构造时再检查事实准入和年报来源记录。

请求只含：调查目标、至多四个问题、动作说明及 analysis Schema、授权事实名称/层级目录、授权证据来源/页码/口径目录、最近查询的至多两个事实和两个证据、最近至多六步动作摘要、剩余预算。get 后优先保留所取原文。

单段原文最多保留前 2400 字符，记录 omitted_characters；省略的早期详情、问题或目标尾部也明确标记。省略不表示原文不存在。不存在自动分页补齐；必要引文不在可见部分时应查询其他资料或停止，不能补写。全部消息超过字节限制则请求前停止，不无提示删除关键内容。

不发送完整 44 项金额、完整原文集合、原始日志、金融组 Word/Excel、conflicts 原文、来源控制哈希表或任意 state 字段。内部传输授权目录与公开事实来源核验是两层不同检查。本次演示选择净利润、经营现金流两个事实和 E18、E07_28、E07_29、F_net_profit、F_operating_cashflow 五段证据，**只用于离线回放，不构成真实外发授权**。

## 动作与输出

保持 list、search、get、facts_list、fact_get、explain、stop。动作只能是一个完整 JSON 对象，顶层仅 action/arguments，参数字段、类型、必需项、字符串长度及 ID 白名单由本地检查。重复 JSON 键、额外字段、未知工具、路径式 ID、非授权项目、非法 analysis Schema 均拒绝；不会执行模型代码。

相同非终止动作重复一次即停止；不同表达的重复检索仍受全局次数限制。explain 的结构先检查，随后仍由原 validate 校验实际检索证据、金额、逐字引用、关联项目和比较口径。通过后仅 pending_human_review。没有自动补 JSON 或修改模型结果。

## 预算和失败保护

| 项目 | 默认 | 可配置硬上限 |
|---|---:|---:|
| 调查轮数 | 6 | 原编排器 20 |
| 本地工具次数 | 4 | 原编排器 20 |
| 模型请求次数 | 6 | 6 |
| 每次 max_tokens | 1200 | 3000 |
| timeout | 90 秒 | 180 秒 |
| 每次消息 UTF-8 字节 | 16000 | 24000 |
| 累计 Token 预算 | 60000 | 120000 |
| 自动重试 | 0 | 不支持 |

请求前以消息字节数加 256 估计输入 Token，再预留输出上限；累计保留每轮预留量，不因服务用量较少而返还。实际返回用量更大时追加占用，并检查实际累计超限。**字节估计不是准确 Token 数，也不能程序化保证绝对费用或 Token 上限。**实际用量只能依赖服务返回。

超时、限流、拒答、截断、非法 JSON/动作均终止，失败后不能用同一决策器继续重试。用量缺失时实际总量为未知，停止下一次请求。没有把未知费用写成零；本轮模拟数字也不算真实消耗。每次调用前保存请求，结束后保存脱敏状态、HTTP 状态、阶段、请求 ID、耗时、可用用量及最终文本，不保存隐藏思维链或认证头。

## 模式记录

- 预设 Mock：decision_mode=preset_mock，simulation=true，llm_called=false。
- Qwen 假传输：qwen_replay，simulation=true，llm_called=false；usage_origin=synthetic_transport，actual_total_tokens=null。
- 真实适配器：qwen_real，simulation=false；只有进入 HTTP 请求尝试后才将 llm_called=true。该标志不证明服务端成功执行。
- model_requests 记录适配器请求次数，real_request_attempts 单独记录真实请求尝试；请求前被预算阻断时不增加次数。
- model_status 区分 not_called、valid_action、invalid_action、request_failed。预算终止原因另见 result.errors；上一次模型状态不会被伪装为新的请求。

## 离线演示和测试

最终演示：`outputs/agent_replay/20261017T015531-8abdc9407b/`。

轨迹为 fact_get(operating_cashflow) → search(metric_id=operating_cashflow) → get(E18) → explain(待验证假设)。4 轮模拟模型响应、3 次 Python 工具调用，pending_human_review。这是人工编写的协议回放，既不是实际 Qwen 响应，也不证明自主调查能力。

每轮请求位于 decisions/01.json 至 04.json，可检查到底发给假传输哪些字段。消息大小分别为 5676、6361、8542、8109 字节，对应保守输入估计 5932、6617、8798、8365，均不是准确 Token 数。回放提供的每轮输入100/输出50仅为合成用量，replay_notice.json明确说明。实际模型用量和费用均没有发生测量。

全部 **143 项测试通过，0 失败、0 跳过**（原125项＋新增18项）。覆盖合法动作、多轮上下文变化、非法JSON/参数、越权、重复、超时、拒答、限流、预算耗尽、缺失用量、最终财务检查失败、状态标识和不可改写事实。真实模式标识测试也仅用无网络测试替身或合成配置，不读取真实凭证。

日志：`outputs/stage4b2a/20261017/tests.log`。私有快照在本机存在并参与集成测试；干净克隆缺失时原有集成类会明确跳过。

```powershell
$py = 'C:\Users\65751\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$env:TEMP = 'D:\Projects\TraceLab\tmp'
$env:TMP = $env:TEMP
& $py -X utf8 -m unittest discover -s tests -v
& $py -X utf8 -m tracelab.agent_offline --stage2-run outputs/final_release/20261017T001129-fb6ba35805
```

## 下一次真实测试前

预计一次小范围调查需 3—5 次决策请求，最多6次；模型可能提前 stop 或触发预算阻断，不能承诺固定次数。默认1200输出Token可能不足以一次生成复杂 explain，应保留截断失败，不自动提高上限。

需要用户单独授权：一次端到端调查；具体事实和证据白名单；百炼北京现有配置及 qwen-plus；轮数、工具次数、请求次数、timeout、输出/累计Token预算与人民币费用上限；未知用量时停止及零重试。之后再给出可执行真实入口及最终请求预览。本次未授予或使用这些权限。

风险仍包括真实模型协议遵循、解释长度、逐字引文、上下文省略造成信息不足、源文件哈希不能代替联网真实性认证，以及程序无法完全判断经营因果。金融组原9条资料冲突保留，争议事实继续隔离。历史V3失败状态不变。
