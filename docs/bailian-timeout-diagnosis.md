# 格力首次请求超时诊断（2026-10-16）

本轮没有发送新API请求，没有commit或push。以下第二次调用命令必须得到用户新许可后执行。

## 已确认与未知

原运行：outputs/stage3/20261016T122437-017f7cac62。
北京时间20:24:38.079开始请求，20:25:35.409结束，耗时57.328秒，TimeoutError，无重试。
实际使用北京工作空间Chat Completions端点：
https://ws-6sp1nti4y4d07vun.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions

参数：qwen-plus、max_tokens=3000、stream=false、enable_thinking=false、response_format=json_object。
timeout=55是urllib套接字阻塞操作超时，不是整个请求的硬截止；总耗时稍大于55秒不构成计时错误证据。
实际Chat请求没有Responses API的max_output_tokens/text.format字段。
输入两条消息共8317字符、11077 UTF-8字节，11项事实、13段证据，粗估3000—6000 Token，未用模型分词器精确计数。

输出Schema包含claims和questions；每条结论包含类型、解释、项目、引文、金额和支持边界，最多六条结论由既有校验器检查。
Schema是提示词中的结构约束，接口采用JSON Object；不能把JSON格式支持理解为服务端严格Schema保证。
未发现请求字段或本地解析路径中可直接证明本次TimeoutError原因的错误。实际输出格式是否满足核验仍未获真实响应验证。

旧call_api在完整读取正文并解析JSON之后才返回request ID，run在其返回后才写HTTP状态。
因此http_status=null不代表未收到响应头。没有阶段日志/堆栈，无法区分连接、TLS、代理、等待响应头或正文读取超时。
当前urllib检测到系统本地代理（127.0.0.1）；没有修改代理，不能证明上次设置相同或它就是原因。
服务端排队/生成较慢、网络/代理等待、正文读取停滞均是未确认可能原因。
不能把客户端超时判断为服务端未执行；上次真实Token及费用未知。
旧日志无服务端request ID；本地run_id和request_sha256不能当作服务端请求ID。

## 方案选择

| 方案 | 改动与兼容性 | 风险及决定 |
| --- | --- | --- |
| A 延长超时 | 新增--timeout-seconds，默认仍55，允许1—300；建议下次180。Schema和校验不变 | 只增加等待机会，不能保证成功或取消服务端执行；采用 |
| B 压缩输入/精简输出 | 本轮仅压缩JSON无意义空白；全部事实、证据和Schema字段保留 | 输入减少561字节约5.1%，不保证Token等比例下降。暂不删引文或降低3000输出上限，避免截断JSON；采用无损部分 |
| C 流式 | 百炼Chat支持SSE；需拼接delta.content、判断结束、处理断流，使用stream_options.include_usage获取末尾用量 | 可在生成时持续接收，但首包仍可能超时。完整JSON后才可运行原校验，中途片段不可视为有效结论；本轮不实现 |

流式文档：https://help.aliyun.com/zh/model-studio/stream

## 本地修改与验证

- tracelab/stage3.py：可配置超时；在读取正文前保留HTTP状态与x-request-id；新增transport.json；失败时checks.json明确未核验。
- tracelab/bailian.py：Schema序列化只移除空白。
- tests/test_stage3_transport.py：新增七项离线测试，覆盖响应头前超时、正文超时、JSON解析阶段、HTTP错误、日志脱敏/无重试、Schema等价及参数边界。
- tests/test_bailian_analysis.py：测试辅助函数适配调用失败也保存checks.json的行为，保留原HTTP错误断言。
- 本文及bailian-gree-analysis.md：诊断和下一步命令说明。

新增transport.phase的connect_or_wait_headers不能进一步区分DNS/TLS/代理/服务端等待；read_body表示已取得响应头；decode_json表示已读完正文；complete仅表示外层JSON读取完成，不代表模型输出核验通过。
仅保存白名单HTTP状态和请求ID，不保存认证头、密钥或异常正文。HTTP错误及失败均无自动重试。
未修改财务计算、桥接、事实、引用或金额校验。

运行python -m unittest discover -s tests：60项通过。
准备目录outputs/stage3/20261016T124045-da702fc137，manifest.status=not_called，llm_called=false。
local_checks.json验证新旧全部事实、证据、提示词正文及Schema等价。
新输入7756字符、10516字节；11项事实、13段证据不变。
新request.json SHA256：fc1dbbfa06ffa6ffbf55376f2a5f226ef3ea42c734aaa649763859d21464f445。
原请求和失败日志未覆盖。已有其他未提交修改保留。

## 第二次调用建议（尚未执行）

qwen-plus，北京既有端点，180秒套接字操作超时；输出最多3000 Token，非思考、非流式、JSON Object，单次、零重试。
输入仍粗估3000—6000 Token，输出上限3000，不保证必须输出满额。
按北京非思考输入0.8元/百万Token、输出2元/百万Token，若达到输出上限，估算0.0084—0.0108元。
这不是费用承诺；实际以账单为准，前次超时费用未知。程序不能保证账户累计20元预算硬上限。
价格：https://help.aliyun.com/zh/model-studio/qwen-plus

```powershell
cd D:\Projects\TraceLab
& 'C:\Users\65751\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -m tracelab.stage3 --provider bailian --model qwen-plus --stage2-run outputs/stage2/20261016T053315-83447d4dedf0 --timeout-seconds 180 --execute
```

只在明确许可后执行。去掉--execute即为无费用本地准备，本轮只执行了该准备。
真实运行仍保留请求、输入/证据哈希、最终输出、金额与引用核验、耗时及可用用量；新增网络阶段日志。
自动检查通过后仍需金融组人工复核，不能称为真实归因已完成。

## 核对上次调用与费用

1. 百炼控制台选择北京及本次业务空间ws-6sp1nti4y4d07vun；在运维管理→模型监控按qwen-plus、2026-10-16北京时间20:20—20:30查看调用量、Token、成功率等。服务端可能在客户端断开后继续，必要时扩大时间窗口。
2. 费用用量→模型用量查看同日同模型用量；费用与成本→账单详情选择2026年10月、大模型服务平台百炼，导出明细，按业务空间、模型、ApiKeyID以及输入/输出计费项核对。无需分享API Key明文。
3. 用量/账单存在汇总粒度和更新延迟，若有并发调用，不能仅凭汇总增量认定本请求费用。现有日志没有服务端ID，无法保证逐请求精确关联。
4. 若控制台无法定位，向阿里云支持提供上述工作空间、模型、北京时间、耗时及客户端错误类型，请其核对服务端执行/计费。不要提交API Key。20:09的成功连通性请求ID不属于本次分析。

官方查询说明：https://help.aliyun.com/zh/model-studio/bill-query-and-cost-management
模型用量：https://help.aliyun.com/zh/model-studio/model-usage-statistics
