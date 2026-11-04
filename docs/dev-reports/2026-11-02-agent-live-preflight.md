# 2026-11-02 真实 Qwen Agent 第二轮验收预检

## 修复审查
最小实现修改通过审查，保留以下局限。已检查实际git diff：Prompt增加按需金额、核心结论、连续逐字引用、支持边界及至少一个未决问题，证据不足可stop；所有原有规则仍保留。qwen_decider.context.remaining.max_output_tokens正确来自Budget，与实际请求max_tokens一致。SCHEMA_V2、财务公式、金额/单位/期间/口径、来源、证据白名单、已检索引用、重复动作、工具预算及人工复核均未改动。
新增紧凑explain测试确实经过investigate→validate完整路径，但fixture原本amounts=[]，再次赋空不构成新的压缩案例；不能据此证明真实输出缩短或1200 Token足够。此问题已报告，本轮未擅自修改。预算可见性和length拒绝测试有独立覆盖。原有错误金额、引用和来源等负例保留。
另：stop的程序要求仅保证非空reason，未自动证明理由包含完整检索范围/具体缺口。Prompt有此要求，但本次实际验收必须人工核对；单凭insufficient_evidence不能宣称合理stop，预算耗尽也不等于证据不足。

## Git与测试
main，HEAD daf1e32f9c03c55bb6d421518f8c24be95b1dc20。本地origin/main同值。最近三提交：daf1e32、f7984b5、9e1ef76。GitHub ls-remote代理连接失败，未同步远程，不能确认实时远端HEAD。
三个修改文件共33行增加：Prompt 5行、qwen_decider 1行、测试27行。原开发报告未跟踪，本报告新增。原有两个output/pdf计划书PDF保留。没有reset、clean、覆盖checkout、commit或push。git diff --check通过。
测试使用既有tmp/test-deps内pypdf==6.10.0，TEMP/TMP设为工作区tmp，PYTHONPATH指向该依赖目录。命令：python -X utf8 -m unittest discover -s tests -v。结果见报告末尾；日志tmp/agent-preflight-tests.log。

## 数据与来源核验
选用现有最新final_revision快照20261017T093152-d80de1cefa（另一目录为更早的092837）。复用agent_preflight.prepare及agent_live.prepare，均在禁用网络、真实API和密钥读取的保护下执行。完整release_hashes逐文件校验、原PDF引文/页码及可信事实绑定检查通过；45项事实准入，9项冲突resolved，0未决。四项事实和六项证据均存在，通过project和ExportScope校验，未扩大范围。

事实白名单：net_profit, operating_cashflow, cash_2, cash_6。

证据白名单：F_net_profit, F_operating_cashflow, F_FINAL_cash_2, F_FINAL_cash_6, E07_28, E18。

| 证据 | 原PDF页 | 印刷页 | 核验 |
|---|---|---|---|
| F_net_profit | 88 | 87 | True |
| F_operating_cashflow | 89 | 88 | True |
| E07_28 | 29 | 28 | True |
| E18 | 89 | 88 | True |
| F_FINAL_cash_2 | 89 | 88 | True |
| F_FINAL_cash_6 | 89 | 88 | True |

来源均为格力2025年年度报告.pdf；完整PDF、金融组Word/Excel及未授权材料不进入请求。目录不是已读取原文。

## 配置与预算
模型由agent_live明确指定qwen-plus；DASHSCOPE_MODEL、TRACELAB_MODEL未配置，不影响显式模型。北京百炼工作空间匹配。Endpoint：https://ws-6sp1nti4y4d07vun.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions

仅检查DASHSCOPE_API_KEY变量名和Windows用户注册表元数据，均存在；未读取、打印或记录密钥值。未验证余额、Key权限或网络连通性。
建议沿用现有代码：一次调查，最多5轮/5个模型请求、4个工具调用；单次输出1200 Token，总保守预算60000 Token，输入正文每次16000字节，单次超时90秒，0自动重试。真实目标首请求11016字节，未超过输入上限。不能保证后续每轮都能容纳上下文，超限安全停止。
费用未知：项目未配置可确认单价，本轮不估算人民币金额。60000为程序Token预算，包含保守预留，不是人民币费用上限；需要用户明确接受实际计费不确定性或另行确认费用约束后才可调用。

## 待批准授权申请（尚未授权）
请求仅在用户后续明确确认真实调用及费用预算后，使用现有tracelab.agent_live入口开启一次调查。历史gree-acceptance-20261017-cda49f231621已使用，禁止复用。届时使用新的唯一authorization_id，由现有claim_once独占创建消费标记；本轮未创建已批准授权或消费标记。CLI的--execute-real是技术开关，不代表用户授权。
业务问题：格力电器2024—2025年净利润下降，但经营活动现金流量净额增长。根据已核验财务事实和公开年报原始披露，调查可能的解释及其证据边界。

本申请绑定上述commit、未提交diff、以下Prompt/代码哈希、快照及scope。执行前必须再次逐项比对；变化则暂停重新审查。
预期真实流程search→get→explain/stop。explain须经完整校验后pending_human_review；stop须明确检索范围及具体证据缺口。真实运行必须记录simulation=false、llm_called=true；金融组业务复核独立于程序核验。HTTP 200不能作为通过依据。
截断、非法JSON、未知用量、白名单或核验错误、重复动作、超时、工具/Token预算问题安全终止，0重试、不补齐输出、不改写成功。预算性停止不能冒充合理证据不足。
未来日志由原入口写入outputs/agent_live/<新run_id>/，包括authorization.json、source_audit.json、code_hashes.json和investigation下decisions、events.jsonl、result.json、manifest.json；只有提交完整analysis才有analysis/checks。未知费用如实标记。

## 绑定哈希
- `tracelab\accounting.py`：`a1d3d887c45a5e7b799b8756435f7a8f7cf4442bdebba0857bb7f16b09124110`
- `tracelab\agent.py`：`825f44f55965e9639774aab35df58556ea65b8a88481e7b6dcc8ddd40061178a`
- `tracelab\agent_live.py`：`f622ba606cf7fed00f1197561ca06d24ba5aa5dbfa0633667992e8df578f2372`
- `tracelab\agent_offline.py`：`3357c90018c4ec16cf81c4b2fe5501a76a5b5b7828a5e75de98c0c97f8dc126f`
- `tracelab\agent_preflight.py`：`80cb56c4e1e89b7049f8583e3e167288ee63763b82cc0cb459db4af9dfc989f5`
- `tracelab\analysis_contract.py`：`5ecd0a5cf97157318475bf77ec8399a1eccc998c70628df9053bc1a3379130d2`
- `tracelab\bailian.py`：`734ff8cbddb5e7370ff3e84aa2551a415404f9677c14b1c57797f4c9a23a10f6`
- `tracelab\connectivity.py`：`b4b9dac12b29f8359e281fb87b9621c91d02b148f0c4d9c2a25b44bd51a53a4e`
- `tracelab\display_export.py`：`643026943c1ceac16b8b65e754f60bcc48aae5e3ce54c036ce087cb7ce419dca`
- `tracelab\display_modules.py`：`71d64cb557685e5b56dfb6c968e1a1bc2357fd45e019fc5d93023683f1db0e6f`
- `tracelab\final_release.py`：`6d0b42303aa1406320ad60a7910b02fd4b724b7c0e802b92ad55a2e5891ea4f2`
- `tracelab\final_revision.py`：`77e3d6fe2fb39757b3ffc1f060fff7663a7fdc971f93ffa96087ccf5a9f37e22`
- `tracelab\investigation.py`：`646a861c1a8c36225251250f29d8d736fd863e1bfd67efb4af4a3b04e7312824`
- `tracelab\pdf_extract.py`：`4853a9bdb0d4e367961e80d6b06b0f4988883b3a72d9df144ada5b265c45a127`
- `tracelab\qwen_decider.py`：`9664b3d4c4ad9fa6aafe782edeec05058bb358ccbb86c721e4f9009c1d192bdb`
- `tracelab\report_check.py`：`e967d1d8f10174d188bf42b9886e9f305b47b524018b033e559da11f55a33bbb`
- `tracelab\review_status.py`：`c4b1e51b4cb391b37f1c76a52dadf5675342361e56135168f8b671dfbae8e04c`
- `tracelab\source_contract.py`：`35a2f03c03439431995834fee92e1babd44db36b2b9c177591df43398d102e02`
- `tracelab\source_io.py`：`60a539a9065478309df88ee8f3ff5c88b544ebfb1ef82b1ae3737c1eece084ff`
- `tracelab\stage1.py`：`fc72ba73f8b58fe95563f68814256a1d9bd3839b38bacce08aaefa0348bbaa5a`
- `tracelab\stage2.py`：`6b3ea0ccda10747b855fce8a97f03316a760675560ad6250bb7b1440708c671e`
- `tracelab\stage3.py`：`a1e73f7da33ed9ae44f5dc1517f17e06be6c550811f16efe7fc996d379d18c28`
- `tracelab\stage3_input.py`：`2883f9e59c275957fb1382b5047ab449fd36e225470ffabeeed65b0e3d160eec`
- `tracelab\__init__.py`：`2ae331fb8aadbde02083af5630038508138e94efbb71a38f98385701bbe42477`
- `tracelab\__main__.py`：`ecc986ce771e299d1e16546d84a86e64fbcfd584af7828c6aea73afc3ac2bd8b`
- `prompts\agent_decision_v1.txt`：`a5b2a32bd7db23d350bce7843a085c599ed1c8d72bbd4f338ca64221b02943b6`
- `tests\test_agent_progress.py`：`beb4ffc5a2bb831ee7dbcb7f267daefd314f8dca45e45d27b0018a71bbd3832c`

快照manifest SHA-256：`08e359e416ad2db2a3921feacca2cafc7b9db1f38b472a4a3b1a10db2b4ade33`

## 预检工件与限制
本轮工件目录：`outputs\agent_preflight_20261102\20261102T131348-ba3c710647`。preflight.json记录来源审计与配置；export_scope.json明确authorization=not_granted；readiness_binding.json记录全部Python代码哈希、来源与逐ID核验；live_first_request_not_called.json为使用真实GOAL构造的请求，未发送。原first_request_not_called.json属于预检Replay目标，不冒充真实首请求。
离线Replay状态pending_human_review，3次合成请求；不是Qwen成功。技术状态ready_pending_authorization；真实调用仍须新的明确授权及费用确认。所有预检网络请求为零，未调用真实模型。本轮到此停止。

## 最终测试结论
重新运行225项，225通过、0失败、0错误、0跳过。日志SHA-256：`d087baf188ff4c57c4ec54e21474cbdfb318dac9851838d4e4dc2b0293dd9a7f`。离线回归通过，技术预检通过（上述测试覆盖局限保留），当前待用户授权，不具备已获准执行状态。
