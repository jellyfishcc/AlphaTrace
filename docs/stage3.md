# 第三阶段：一次有限证据分析

本页保留第三阶段早期操作与历史交付说明；当前状态以[项目首页](../README.md)为准，最近一次独立真实分析结果见[第三阶段测试与交接](stage3-test-handoff.md)。

2026-10-16补充：已增加百炼Chat Completions最小适配，可显式选择--provider bailian；
原OpenAI默认路径保留。以下OpenAI配置说明仅适用于原路径。
百炼配置、无费用检查和真实连通性许可步骤见[bailian-connectivity.md](bailian-connectivity.md)。

复用第二阶段结果与pypdf依赖。模型接口此前不存在，本阶段新增标准库HTTP调用OpenAI Responses API，
采用结构化JSON输出。当前环境未发现可用的模型凭证或模型名，实际结果以运行manifest为准。
没有真实响应时不生成analysis.json，不以测试中的人工样例冒充模型结果。

本次真实调用命令被自动审批拒绝：尚未明确授权向OpenAI这一具体服务外发资料。
已改为仅本地准备；实际运行还需用户确认服务目的地，并在本地配置凭证和模型名。

## 运行

在仓库根目录执行。Python环境需已安装requirements-stage2.txt；本机可用内置运行时：

```powershell
python -X utf8 -m tracelab.stage3 --stage2-run outputs/stage2/20261016T053315-83447d4dedf0 --execute
```

普通环境：

```powershell
python -m pip install -r requirements-stage2.txt
python -X utf8 -m tracelab.stage3 --stage2-run "第二阶段运行目录" --execute
python -X utf8 -m unittest discover -s tests -v
```

省略--execute仅生成请求样例。传入--execute但配置缺失也保存not_called并正常退出，
必须读取manifest.status，不能只凭退出码宣称模型调用成功。
配置环境变量OPENAI_API_KEY和TRACELAB_MODEL（或OPENAI_MODEL），模型需支持Responses与JSON Schema。
密钥在本地安全设置，不粘贴到聊天、源码、命令历史或提交到Git。脚本不读取Codex登录凭证，
不自动加载.env，不重试请求。当前仅支持固定官方端点；其他模型服务需单独适配。
请求超时为55秒，max_output_tokens为3000，store=false；不请求或保存隐藏思维链。

接口依据：[OpenAI官方结构化输出文档](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)。

## 输入与外发范围

启动时检查第二阶段verification、原始快照哈希，重新读取原始PDF相应页，
核对数值、差额及原文摘录。仅选择十个精确核实的财务项目及一个本期保证金金额。
金融组Excel/Word、内部摘要、证据评级、完整财报页、未核实金额不进入请求。
报告来自用户提供的年度报告文件；尚未另行联网认证报告来源。

手续费及佣金收入本期空白、营业外收入存储值未精确匹配等排除理由保存在input_audit.json。
营业外收入缺席意味着本次模型不能完整重建利润总额桥接。其他未选项目仅因本次范围有限。
比较口径是披露合并报表，合并范围有变化；不称恒定主体经营比较。
E07拆分为E07_28、E07_29、E07_179，并保留父编号与准确印刷/PDF页码。
F_开头编号对应第二阶段数值核验的原始年报行。

## 输出检查和边界

claims区分会计事实、披露解释、待验证假设。金额放在amounts中，按财务项目、期间字段、
单位和值核对；自由文本出现数字或中文金额时要求复核，不默认放行。引用ID必须存在，
短引必须是原文子串，财务项目必须与引用关联。空结论、无证据、虚构引文、金额不符均失败。
假设的确定性措辞采用基础规则拦截。措辞检查不能理解全部语义，
即使基础检查通过也始终是needs_human_review，需金融组检查引文是否真能支持结论。
未定义新的证据等级、重要性阈值或异常分类。

## 记录与交付

- input.json：实际可发送的最小输入；input_audit.json：来源哈希及排除理由。
- prompt.txt、request.json：提示词与无凭证请求正文，提示词版本evidence_v1。
- manifest.json、events.jsonl：运行时间、模型、参数、状态、哈希；未调用时耗时/用量为null。
- response.json：仅真实调用返回的最终消息、状态、用量，不保存reasoning条目。
- analysis.json、checks.json：真实JSON结果及检查，未调用时只有检查未运行的状态。
- error.json：失败类型和HTTP状态；不保存可能回显密钥的服务端错误正文或请求头。
- 人工复核清单.md：具体复核项目。
- delivery/：本地交付副本，含源码、模板、真实输入快照、第二及第三阶段结果与文件哈希清单。

交付副本含金融组原始材料，仅供本地团队交接，不作为整体外发模型的内容。
重跑交付副本时在delivery目录使用--stage2-run stage2_results；输出仍生成独立运行目录。
数据整理、口径确认、证据选取和命令启动均仍有人工作业，系统尚非全自动。
