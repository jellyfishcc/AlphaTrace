# focused结构化输出修复（2026-10-16）

本轮无真实API调用、无重试、无commit/push。已有未提交改动保留。
已实际读取20261016T134204-78da8e3494的analysis、checks、post_run_review及现有输入、Prompt和校验代码。
历史返回和核验结果保持原样；测试中的修正版仅是合成变体，不是真实模型成功记录。

## 最小修复

新增prompts/evidence_v3.txt，保留v2以便回溯；stage3的PROMPT_VERSION切换v3。
明确amounts每个fact_id必须同时出现在同条metric_ids，并有对应有效引用。原关联检查未放宽。
现有模型输入amounts只包含元/亿元及base/current/change，输出Schema也没有可引用的结构化百分比。
本轮不需要展示百分比，因此不把上游增长率扩展进模型事实，不修改Schema或财务计算。
年报57.93%只保留在原文quote中，其他自由文本使用“同比增长”等定性描述；数字检查保持原样。

analysis_contract.py新增通用限制：comparison_basis为yoy时，不能引用只有current、没有base/change的事实金额作为量化依据。
原有披露比较口径检查仍保留，不能用current_period的经营披露支撑yoy披露解释。
Prompt明确本期现金流与净利润差异不等于现金流同比变化，要求说明无法据此量化同比贡献。
这不是经营因果的自动判定。文字与口径字段冲突、无量化数字的过度归因仍须金融组复核。

## 测试与准备

新增tests/fixtures/qwen_focused_validation_failure.json：真实失败的输入与输出，仅已有公开事实和披露，不含API凭证或内部附件。
新增tests/test_focused_regression.py：八项测试覆盖原错误复现、金额关联、自由文本百分比拒绝、原文百分比保留、本期/同比混用、通用规则与正确合成变体仍需人工复核。
全部84项测试通过，无失败。既有金额、引用和层级回归均通过。
full与focused分别执行无execute的本地准备，均not_called：
- focused：outputs/stage3/20261016T135305-f7d43e4a74
- full：outputs/stage3/20261016T135307-9275eb50fc

当前本地规则与请求准备已就绪；不必立即付费重测，可先完善金融组人工复核和交付。
只有需要确认Qwen能否实际遵守新版Prompt时，才值得在用户重新授权后进行一次focused测试；离线测试不能替代这项真实验证。
本轮结束，不进入动态Agent开发。
