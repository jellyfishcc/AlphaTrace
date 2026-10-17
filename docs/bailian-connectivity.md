# 百炼本地检查与一次最小连通性测试

日期：2026-10-16。用户明确同意后，已完成一次最小真实连通性测试。

## 本次真实结果

北京时间2026-10-16 20:09:54开始，模型qwen-plus，HTTP 200，回复“连接成功”。
请求耗时2.797秒；服务返回输入20 Token、输出2 Token、合计22 Token，缓存命中0。
仅发送固定连接测试文本，一次请求、无重试、无财务资料。没有继续执行归因分析。
按下述公开单价估算0.000020元，非实际账单，账户费用以百炼控制台为准。
原始脱敏记录：outputs/connectivity/20261016T120954-a3217b38/manifest.json和response.json。
此结果确认当前Key、北京端点及模型可连通；尚未验证真实结构化财务分析质量。

## 已检查状态

分支main，最近提交14ad619。已有未提交的待确认清单改动保留原样：
docs/progress.md、docs/self-check.md、tracelab/stage2.py、tracelab/review_status.py。
原stage3.py为固定OpenAI Responses接口，已有dry-run及unittest Mock测试，无百炼适配。
系统Python为3.13.9，足以运行连通性脚本及测试；未安装pypdf。
内置Python3.12.14有pypdf6.10.0，供财报步骤使用。本次没有新增第三方依赖。

## 配置与兼容性

DASHSCOPE_API_KEY在当前进程与Windows用户环境均存在；DASHSCOPE_BASE_URL当前进程未继承，用户环境中存在。
只读回退读取HKEY_CURRENT_USER/Environment，无需重建Key或修改注册表。
优先级：显式模型参数、DASHSCOPE_MODEL、TRACELAB_MODEL、默认qwen-plus。
Base URL只读取用户配置，无默认地域替换。本次核实为：

https://ws-6sp1nti4y4d07vun.cn-beijing.maas.aliyuncs.com/compatible-mode/v1

追加/chat/completions作为请求地址。保留原OpenAI接口和默认行为；stage3增加--provider bailian，
只做请求/响应转换，复用已有日志和结果校验。本轮不执行财务分析调用。

官方文档说明Responses存在基础兼容，但不能假设原text.format严格JSON Schema请求在qwen-plus完全兼容。
当前结构化输出文档列出qwen-plus非思考模式支持JSON Object，严格Schema支持列表未列出该别名。
因此采用Chat Completions与response_format=json_object，将Schema放入提示词并保持本地校验。
最小连通性测试只要求文本回复，不使用JSON或财务材料，不能由它证明结构化分析质量。

来源：
- https://help.aliyun.com/en/model-studio/qwen-api-via-openai-responses
- https://help.aliyun.com/zh/model-studio/qwen-structured-output
- https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope
- https://help.aliyun.com/zh/model-studio/qwen-plus

## 无费用本地操作

```powershell
cd D:\Projects\TraceLab
python -X utf8 -m unittest discover -s tests -v
python -X utf8 -m tracelab.connectivity
```

第二条默认仅保存request.json、manifest.json及events.jsonl，status=not_called。
Mock只在单元测试内运行，合成响应不作为真实服务测试结果。

## 等待本次许可后才执行的命令

```powershell
cd D:\Projects\TraceLab
python -X utf8 -m tracelab.connectivity --model qwen-plus --execute
```

唯一输入：请只回复“连接成功”，不要输出其他内容。
固定输入、最多16输出Token、enable_thinking=false、stream=false；单次POST，30秒超时，零自动重试、禁止重定向。
记录请求时间、HTTP状态、模型、实际耗时、服务返回的usage；未知用量为null。
只保存最终可见回复，不保存reasoning_content、请求头、Key或服务端原始错误正文。
默认outputs被Git忽略；本次不提交、不推送。

## 预算

本阶段预算20元。按核查的北京qwen-plus短上下文非思考原价，输入0.8元/百万Token，输出2元/百万Token。
预计输入约30—100Token（未使用模型分词器，非精确值），输出最多16Token，估算约0.00003—0.00012元。
实际分词、免费额度、折扣和账单以百炼为准，不保证调用免费。
程序限制本次请求大小与次数，无法强制账户累计20元上限，也无法核查其他程序的消费。
失败后不会自行重试或换模型/地域；需另行确认。
