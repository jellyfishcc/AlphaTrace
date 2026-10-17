# 单条研报核查示例

`simulated.json` 的公司、金额、来源均为软件测试构造，不是真实金融结果。使用 `python -X utf8 -m tracelab.report_check --simulated-demo` 无需附件或密钥，可得到方向错误演示。模拟来源没有年报页码，不伪造页码。

`gree_direction_error.json` 是人为构造的错误陈述，不是实际研报原文。实际事实不随此输入提供，必须由 `--stage2-run` 指向的本地修订快照重新核验取得。缺失快照返回“无法核实”。命令见仓库 README。

输入字段：company 为公司全称；period/base_period 为本期/基期；metric_id 与 metric_name 同时匹配；scope 使用来源的完整披露口径；comparison_basis 当前只支持 yoy；value_kind 为 current（本期金额）或 change_magnitude（同比变化绝对金额）；value 使用普通十进制字符串，其小数位表示展示精度，最多8位；unit 为元/万元/亿元；direction 为增长/下降/持平；original_text 保存原文。

方向始终比较两期原始元金额；金额从已有事实的元值换算，ROUND_HALF_UP 按输入精度展示，不能先对两期展示值相减。指标缺失、期间或口径不一致、来源核验失败均无法核实。数值恰好对应另一单位时提示“数值或单位错误”，不臆测作者意图。原文不会自动解析，使用者须确认结构化字段忠实于原文。

每次运行生成独立目录，包括 JSON、Markdown、真实模式来源审计哈希及核验步骤。退出码0表示完成核查（包括发现错误），2表示无法核实。函数 `check_claim` 可供未来 Agent 调用；真实模式只接受可信加载器生成的 payload，不能直接信任模型或外部 JSON 声称的来源回执。
