# Agent explain 精简修复开发报告

## 一、本轮开发概述
在现有项目中完成最小范围的 Prompt 和输出预算可见性修改，保留输出协议、校验器、财务公式及真实调用入口。未调用真实 Qwen，未读取密钥，未使用历史授权，未 commit/push，未修改前端。

## 二、开发前状态
分支 main，HEAD daf1e32f9c03c55bb6d421518f8c24be95b1dc20，本地 origin/main 同值，git diff origin/main 无差异。GitHub ls-remote 因代理连接失败，不能保证远端实时状态。
存在两个未跟踪文件：output/pdf/TraceLab_项目计划书_初赛修订版_含原流程图.pdf 与 output/pdf/TraceLab_项目计划书_初赛提交修订版.pdf。已报告并保留；工作区非干净，未创建分支或重置。
修改前运行指定 unittest 命令：196 tests，107 errors（包含类初始化错误），0 assertion failures，0 skips；受临时目录权限及缺少 pypdf 影响。改用工作区 tmp 临时目录后，仍为196 tests，149通过、51 errors（含4项类初始化错误）、0 failures、0 skips。不能将 errors 直接用 tests 减得通过数。
将 requirements-stage2.txt 已固定的 pypdf==6.10.0 安装至 tmp/test-deps，仅用 PYTHONPATH 提供测试依赖，未修改依赖声明。日志在 tmp/agent-baseline.log。

## 三、问题分析
已阅读 agent.py、qwen_decider.py、agent_live.py、stage3.py、决策Prompt、两组指定测试及真实验收记录，并读取真实第三轮 decisions/03.json 的 response 和 usage。
已证实：第三轮输出1200 Token，finish_reason=length，在第三条 hypothesis 的 statement 中断；前两条包含12个完整金额对象（四项事实各base/current/change），statement还重复金额。真实记录同时指出未检索引用、数字纪律和过强因果断言，这些并不会因解决截断而自动合规。
SCHEMA_V2要求保留字段，但不要求每项事实或三种期间金额全部复述；amounts和accounting_links允许空数组。完整校验仍要求一至六条结论、引用覆盖财务项目、非空支持边界及未决问题。因此不改Schema。
原Prompt要求完整analysis，却没有给出紧凑组织策略；这是可改进的诱因，不能凭一次记录证明唯一原因。上下文已有事实、目录、历史及Schema，initial_facts中引用还可能与queried_evidence重复；本轮为避免丢失可见证据及改变检索语义，保留这些内容。1200对历史长输出已证实不足，对紧凑真实输出是否足够仍未知。

## 四、修改文件与位置
- prompts/agent_decision_v1.txt：末尾增加紧凑组织规则，优先一条必要结论，必要时增加不同结论；金额按需列示，避免机械展开；连续逐字短引文保留关键限定；合并重复问题，保留支持边界；无法完整表达时合理stop。
- tracelab/qwen_decider.py：context.remaining增加max_output_tokens，直接来自既有Budget；硬上限仍1200，未增加重试或更改完整性检查。
- tests/test_agent_progress.py：增加预算可见性与Schema一致性、紧凑explain经过完整核验、length不补全不重试三个测试。
- 本报告为新增文件。

## 五、修改前后对比
修改前只要求完整analysis；修改后明确如何在硬预算内组织必要结论，而非复制整个事实表。没有硬性裁剪模型响应，没有删除引用/金额字段，没有放宽金额、期间、单位、口径、白名单或逐字校验。Prompt版本标识仍agent_decision_v1，既有运行审计通过prompt_sha256区分内容；SCHEMA_V2保持不变，历史协议兼容。

## 六、测试结果
全量最终结果见下方补充。现有Replay覆盖search/get/explain进入人工审核、search/get/stop证据不足、未检索引用、错误金额、重复动作、非法JSON、length、工具预算、已有事实重复查询和未授权事实/证据。新增三项不替代原有测试。未修改或删除原测试。
测试环境：TEMP和TMP为工作区tmp，PYTHONPATH为tmp/test-deps；执行 python -X utf8 -m unittest discover -s tests -v。最终日志tmp/agent-final-ready.log。

## 七、验收结论
最终结果见下方补充。Replay仅验证预设响应通过既有工程校验，不能证明模型遵循新Prompt，也不能宣称真实Qwen截断问题已经实测解决。

## 八、下一步工作
重新真实调查前需审核本次diff与完整测试结果，重新检查来源、Prompt和代码哈希、外发范围及endpoint；取得新的单次明确授权并确认单次/总Token、请求数和费用预算。不得复用历史授权。真实测试应同时检查长度、引用可见性、金额、口径和业务因果边界。本轮结束即停止，不自动开展下一轮。

## 最终验收补充
完整依赖环境下全量运行225项，225通过、0失败、0错误、0跳过，耗时111.696秒。包含原有222项及新增3项。离线回归验收通过；真实模型有效性仍待新授权实测。首次测试因类初始化失败而未展开所有用例，故运行数较少。git diff --check通过。最终仍在main，同一HEAD；三个实现/测试文件修改和本报告未提交，原有output/两个PDF保留。无commit/push。
