# 自己检查 TraceLab 完成情况

当前是命令行原型：终端启动程序，结果保存为CSV、JSON和Markdown。
可以用Excel看CSV，用编辑器或Codex文件面板看JSON和Markdown。
阶段二计算完成不等于业务验收通过；阶段三代码完成不等于已调用模型。

## 先看本机已有结果

在D:\Projects\TraceLab下：

| 文件 | 看什么 |
|---|---|
| outputs/stage2/20261016T053315-83447d4dedf0/summary.md | 第二阶段运行摘要 |
| 同目录metrics.csv | 两期金额、difference本期减基期、status；空白项不得当零 |
| 同目录human_comparison.csv | 程序结果与人工参考的差异 |
| 同目录conflicts.csv和pending_questions.md | 尚未解决的问题；记录数不等于独立错误数 |
| 同目录evidence.json | 证据原文、印刷页和PDF页 |
| 同目录verification.json | 软件核验结果，不是金融组验收 |
| outputs/stage3/20261016T055556-19ecf75da8/input.json | 筛选后准备发给模型的内容 |
| 同目录input_audit.json | 排除项目及来源哈希 |
| 同目录request.json | 无密钥请求样例 |
| 同目录manifest.json | 模型是否真正调用、状态及用量 |
| 同目录人工复核清单.md | 人工仍需完成的判断 |

这次第二阶段为31个项目、30个完成计算、1个空白阻断。
冲突表按review_status筛选：只有“待确认”是剩余业务问题；“定位已核实，待文档同步”只需修订出处文字，
“处理已明确”“历史参考”“已知比较边界”无需重复向金融组提问。空白项继续阻断不等于处理方式尚未确认。
当前待确认文件已经更新；delivery内同名文件是当时交付快照，最新处理状态以第二阶段目录为准。
第三阶段为status=not_called、llm_called=false、model=null：尚未调用模型。
没有response.json或analysis.json是符合当前状态的，不是漏生成。

## 自己运行检查

打开PowerShell，进入项目目录：

```powershell
cd D:\Projects\TraceLab
python -X utf8 -m unittest discover -s tests -v
python -X utf8 scripts/verify_stage2_run.py outputs/stage2/20261016T053315-83447d4dedf0
```

当前测试预期显示38项和OK，真实结果核验应显示status为passed。
测试包含故意构造的无效输入，可能出现status=error日志；以整个测试套件最终OK/FAILED为准。
测试通过验证程序规则，不能证明真实模型可调用或经营解释正确。

仅在本地重新准备第三阶段，不发送模型请求：

```powershell
& 'C:\Users\65751\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -m tracelab.stage3 --stage2-run outputs/stage2/20261016T053315-83447d4dedf0
```

命令会打印新output目录，打开那个目录的manifest.json检查，不要误看旧运行。
正式调用的配置和方式见stage3.md；需要模型凭证、模型名和明确的服务目的地。

## 怎么判断真的完成

1. 数值：在metrics.csv选一个项目，用本期金额减基期金额；对照原始年报相应页。
2. 出处：打开evidence.json，按PDF页定位，确认摘录能找到；印刷页与PDF页可能不同。
3. 模型：llm_called=true仅表示尝试过；还要看status是否completed_pending_human_review及response.json。
4. 输出：checks.json若failed不能采用；即使needs_human_review，也必须按清单逐条人工确认。

完整闭环目前缺少真实模型测试与金融组对模型解释的验收。
GitHub保存代码、提示词、模板和说明；本机outputs及原始资料默认不提交。
队友仅克隆仓库不会自动得到本次数据，应通过获授权的团队渠道提供本地交付包。
