# 2026-10-16 分析质量修复与小范围测试准备

本轮仅离线开发，未调用真实API、未自动重试、未commit或push。
分支main；已有stage2、stage3及文档等未提交修改保留，未覆盖或重置。

## 失败复盘

读取第二次真实运行20261016T124914-9411219b6a的manifest、response、post_run_review及请求。
HTTP200，输入3364 Token、输出3000 Token、68.062秒。Chat请求max_tokens=3000是长度限制来源。
确实设置response_format=json_object、enable_thinking=false；Schema被写入提示词，不是服务端严格JSON Schema模式。
原始API finish_reason被旧适配器丢弃，保存记录仅有incomplete，故无法追溯确认其字面值为length。
输出用满上限且JSON截断，强烈支持长度限制导致截断，但不能补造历史finish_reason。
新代码将保存finish_reason及incomplete_reason。

原始正文有所得税加法试算、以少数股东损益解释净利润缺口、以营业外收入解释营业利润缺项，
并以本期票据保证金金额除以现金流同比增量称贡献比例。上述内容不能作为验收结论。
旧Prompt已有禁止自行计算和禁止本期/同比混淆的要求，但未被模型遵守。
同时要求逐层利润说明及现金流解释、最多六条结论，增加了输出负担；这是合理影响因素，不是经对照实验确认的唯一根因。

## 修改文件与职责

- tracelab/analysis_contract.py：只读取已有bridges.json及directional_impacts.csv，核对它们与已核实事实一致，复制关系和影响方向；不重新计算桥接或生成金额。零残差且用户确认公式、所需事实齐全才标verified。未通过关系不升级为完整桥接。
- tracelab/stage3_input.py：原prepare核验完成后附加版本化契约、关系来源哈希；focused模式只选净利润、经营现金流、票据保证金及五段相关原文。完整模式保留十一项事实与十三段证据。内部摘要和财务组原始文件不加入请求。
- prompts/evidence_v2.txt：明确利润层级、所得税负向、少数股东损益边界、保证金口径和证据不足时拒绝归因；限制字数及结论数量。
- tracelab/stage3.py：保留旧Schema和旧响应校验入口，新契约在每条结论增加accounting_links及comparison_basis；默认full，新增focused；保留全部金额、期间、单位、引用、原文和结构检查。输出上限可配置，默认3000，允许1—6000。
- tracelab/bailian.py：保存白名单finish_reason，区分length等未完成原因，不补全残缺JSON。
- tests/test_analysis_quality.py及tests/fixtures/qwen_truncated_response.json：真实失败样本和离线回归。样本只包含已返回文本及用量，移除请求ID；不含内部附件、密钥或隐藏思维链。

Python固定数值、关系、符号与核验边界。LLM继续选择值得调查的披露、提出解释或假设、说明支持限度和补充材料。
focused模式不传入额外利润组成金额，也不要求输出利润桥接；accounting_links通常为空。
full模式关系方向来自原方向结果；不把公式的数学正确性等同经营归因正确。

## 检查能力和限制

| 问题 | 处理 |
| --- | --- |
| 所得税影响方向错误 | accounting_links.effect与已核验方向不一致则失败 |
| 少数股东损益、营业外收支层级混淆 | 不存在或未verified的target/component关系失败 |
| 保证金同比贡献率 | Schema没有比例字段，额外字段失败；自由文本数字继续失败；本期披露标为同比解释失败 |
| 虚构证据、引文不匹配、金额期间单位错误 | 继续由既有校验器拒绝 |
| 截断JSON | response_failed或validation_failed，不补括号、不提取部分结论冒充成功 |
| 经营语义、遗漏关系声明、文字与结构矛盾 | 必须人工复核；没有关键词黑名单充当财务语义证明 |

例如只有文字“所得税增加推动净利润增长”，而accounting_links为空，仍可能进入needs_human_review而非failed。
这不是自动验收通过。相同限制适用于没有数字的保证金贡献表述、因果范围与集中解押假设。
人工须逐条核对，而不能直接发布模型解释。旧假设确定性措辞检查仍有启发式局限，不能作为语义证明。

## 验证

python -m unittest discover -s tests：76项全部通过（原60项＋新增16项）。
包含结构化财务逻辑错误、语义人工复核、证据/金额错误、真实截断样本、正常Mock、小范围dry-run。
真实失败文本不作修补；模拟finish_reason=length和stop时均不能误判成功。

focused离线准备：outputs/stage3/20261016T133104-93915028a5，not_called。
三项事实、五段证据；5214字符、7780 UTF-8字节（含提示词和Schema）。全部金额和原文与上次输入子集一致。
full离线准备：outputs/stage3/20261016T133235-7074ac55c1，not_called。
记录日期和目录是本轮实际运行结果；不代表真实模型质量已经验证。

## 参数选择与下一次方案

官方JSON Object支持Qwen-Plus非思考；严格JSON Schema支持列表未列qwen-plus，继续JSON Object加本地严格核验。
官方提醒输出Token限制可能截断JSON，并建议结构化输出不设max_tokens以避免该问题；本项目因预算和单次测试边界保留明确上限，接受截断时失败，不能保证永不截断。
兼容接口文档将max_tokens标为即将废弃并推荐max_completion_tokens；本轮保留刚刚实测支持的max_tokens，不在无真实兼容验证时同时更换参数。

方案比较：
- 缩小任务到最多两条，每条解释≤100字符、边界≤140字符、问题最多两条≤80字符；保留完整字段及所有必要引文，首选。
- 适度提高到4000可留给后续完整模式，但不能解决错误推导或保证遵循规则；本次不默认提高。
- 不设上限会使用模型默认限制，增加费用与耗时不确定性，不用于下一次有限测试。

推荐qwen-plus，北京既有环境变量端点，focused、180秒、max_tokens=3000、非思考非流式、一次零重试。
输入粗估2500—3500 Token，输出目标800—1500 Token、硬上限3000；非分词器精确计数。
按输入0.8元/百万Token、输出2元/百万Token，目标约0.0036—0.0058元，若输出满上限约0.008—0.0088元。
实际费用以百炼账单为准，不能保证账户累计20元硬上限。

以下命令仅供用户审核，本轮未执行带--execute的命令：

```powershell
cd D:\Projects\TraceLab
& 'C:\Users\65751\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -m tracelab.stage3 --provider bailian --model qwen-plus --stage2-run outputs/stage2/20261016T053315-83447d4dedf0 --analysis-mode focused --timeout-seconds 180 --max-output-tokens 3000 --execute
```

去掉--execute可只做本地准备。有条件进入下一次有限真实测试，但须用户重新明确授权；不能声称质量修复已由真实模型验证。
本轮结束，不开展动态Agent。

官方资料：
- https://help.aliyun.com/zh/model-studio/qwen-structured-output
- https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-chat-completions/
- https://help.aliyun.com/zh/model-studio/qwen-plus
