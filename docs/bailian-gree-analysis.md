# 格力案例第一次百炼分析准备（2026-10-16）

后续超时诊断、本地修复及第二次调用建议见[bailian-timeout-diagnosis.md](bailian-timeout-diagnosis.md)。
本页下方保留第一次调用的历史参数；第二次请求尚未发送。

## 首次真实调用结果

用户明确确认后，于北京时间2026-10-16 20:24:38发起一次qwen-plus请求。
客户端约57.328秒后捕获TimeoutError，配置超时55秒；状态call_failed，未重试。
日志未取得HTTP状态、模型回答或Token用量，不能判断服务端是否已生成或计费，也不能由此判断是否收到过响应头。
请求哈希与审批前准备的request.json一致，没有新增外发材料。
记录：outputs/stage3/20261016T122437-017f7cac62/manifest.json和error.json。
尚未得到真实归因结论，金额与引用检查因无响应未执行。
后续如调整等待时间或缩短输出后再次调用，需要新的明确许可。

## 调用前的准备记录

本轮仅本地开发及Mock测试，真实格力请求尚未发送。既有连通性测试不重复执行。
53项测试通过，包括百炼格式转换后成功进入现有校验器，以及错误金额、引用、JSON结构和HTTP异常。
Mock答案均为合成测试材料，不是格力分析结论或真实模型响应。

## 输入范围

第二阶段来源：outputs/stage2/20261016T053315-83447d4dedf0。
十项财务事实包括营业收入、营业总成本、其他收益、营业利润、利润总额、所得税费用、
净利润、归母净利润、少数股东损益、经营活动现金流量净额；保留两期元金额、Python差额和亿元展示。
另含本期票据保证金等净减少额，其金额不作为现金流同比增量。

共十三段原文：十段数值所在年报行，以及E07拆分的印刷页28同比说明、29净利润差异说明、179保证金注释。
再次从原始PDF核对文本、金额及哈希。来源是用户提供的公开年报；未另行联网认证原始文件。
请求不含金融组Word/Excel、内部摘要或证据评级；本地delivery目录中的原始资料不发送。
手续费空白及营业外收入精度不一致项目排除；缺少组成项时不得补算完整利润总额桥接。

## 实际请求

准备目录：outputs/stage3/20261016T121808-b2817efa8a。
input.json为模型事实和证据；request.json为实际无密钥请求；local_checks.json为本地检查与请求哈希。
模型qwen-plus，使用既有北京Base URL加/chat/completions。
JSON Object模式，enable_thinking=false，stream=false；本地既有Schema、金额、引用与措辞检查保持不变。
接口文档支持JSON Object不等于保证Schema完全匹配；实际结构化输出质量仍待真实请求验证。

当前输入8317字符、11077 UTF-8字节，粗估3000—6000 Token（未使用该模型分词器）。
输出上限3000 Token；输入超过32000字节时本地阻断，字节限制不是精确Token计数。
一次请求，55秒超时，无重试。按北京qwen-plus非思考输入0.8元、输出2元/百万Token估算，
若输出达到上限，本次约0.0084—0.0108元；实际用量和收费以服务返回与云账单为准。
阶段预算仍为20元；程序无法保证账户累计费用上限。超时也可能已经产生服务端费用，不自动补发。

价格：https://help.aliyun.com/zh/model-studio/qwen-plus
结构化输出：https://help.aliyun.com/zh/model-studio/qwen-structured-output

## 用户确认后执行

```powershell
cd D:\Projects\TraceLab
& 'C:\Users\65751\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -m tracelab.stage3 --provider bailian --model qwen-plus --stage2-run outputs/stage2/20261016T053315-83447d4dedf0 --execute
```

本轮实际运行的是去掉--execute的本地准备命令。
真实运行会创建独立目录，保存最终响应、checks.json、耗时、用量、模型与请求ID、输入及代码哈希。
不保存隐藏思维链、密钥或认证头。自动检查通过仍为completed_pending_human_review，需金融组复核。
此前未提交改动继续保留，本轮未commit或push。
