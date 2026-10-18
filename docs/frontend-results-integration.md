# 已有后端结果的离线展示

> 结果集成验收记录：本文的数据契约与来源映射仍可参考；页面位置随后已重组。当前操作为“开场 → 选择研究资料 → 载入案例 → 三页业务流程”，见[当前交接清单](delivery-2026-10-18.md)。文中 Python 222项、前端12项是本次历史验收；最新前端验收为32项，未重跑Python。

2026-10-18，开始 HEAD ee9f0e4，工作区干净。本次不修改财务计算、来源规则、Agent 或 Prompt，不调用模型。

## 数据映射

|输入（outputs 下）|页面|展示边界|
|---|---|---|
|report_check/92ddd5a529414b028c8613414f40ac0c/result.json|研报纠错|人为构造结构化错误陈述；方向错误，正确方向下降；并非已发表研报|
|pdf_extract/20261017T195532-0c947edc10 的 extracted_financial.json、comparison.json、extraction_audit.json|PDF 提取|5 指标两期共10条；PDF88/印刷87；提取值与可信值分列|
|final_revision/20261017T093152-d80de1cefa/bridges.json、directional_impacts.csv|财务拆解/利润链|6个目标分别展示自身变化、对目标影响、残差；营业总收入 incomplete|
|同快照 cash_bridges.json|财务拆解/经营现金流|3个直接法勾稽，残差为零；未提供贡献不补算|
|同快照 revision_checks.json、conflicts.json|核验与交付|9项历史冲突已解决，当前0项未解决；不导出内部附件原文或旧的待修正说明|
|agent_live/20261017T151343-d0d3b954f5|查看调查轨迹|保持 validation_failed / incomplete_response|

## 可复现导出

使用已安装 pypdf 的 Python，在仓库根目录执行（输出文件必须不存在）：

```powershell
python -X utf8 -m tracelab.display_export --stage2-run outputs/final_revision/20261017T093152-d80de1cefa --agent-run outputs/agent_live/20261017T151343-d0d3b954f5 --report-check-run outputs/report_check/92ddd5a529414b028c8613414f40ac0c --pdf-extract-run outputs/pdf_extract/20261017T195532-0c947edc10 --financial-details --output outputs/frontend_integration/review-display.json
Copy-Item outputs/frontend_integration/review-display.json frontend/public/data/gree-display.json
cd frontend
pnpm dev
```

当前机器验证使用 `C:\Users\65751\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`；系统 Python 的 pypdf 环境不同。不要覆盖历史后端输出。这里只替换可重新生成的浏览器展示包。

## 契约与安全

保留 alphatrace-display-v1，新增可选 record.modules（snapshotId、sections）。新适配器兼容无 modules 的旧包并显示缺失；旧适配器因严格白名单会拒绝新包，部署须同时更新适配器与展示包。section 包含种类、标题、列、字符串单元格、证据引用、运行编号与输入摘要，不包含原始审计文件。

纠错结果按同快照来源审计关联，并用现有 check_claim 在内存复核；当前导出只接受已知构造示例。PDF 重新读取同一原始 PDF，核对历史行、页文本摘要和现有 compare 结果。桥接、贡献、修订和冲突文件核对 release_hashes；桥接状态与 revision_checks 对应。导出经过敏感文本拒绝检查；前端检查形状、快照、证据引用，金额仅显示字符串。文件摘要用于关联，不是数字签名或第三方审计。

public/data、dist、outputs 均继续忽略。浏览器不访问私有 PDF、内部附件、完整请求或密钥。导出依赖本机私有快照与原始 PDF，干净克隆须另备资料；不会用模拟数据冒充。

## 验收与演示

真实导出成功：44财务记录、61证据、3轨迹；10 PDF金额及页码逐项一致、9桥接残差及全部利润贡献逐项一致。浏览器已点击纠错、证据跳转、PDF、利润链、现金流、核验；切换模拟后显示未提供且无真实金额。构建目录仅页面资源和白名单 JSON，无私有附件。

命令：`python -X utf8 -m unittest discover -s tests -q`；定向 `python -X utf8 -m unittest discover -s tests -p test_display_modules.py -v`；frontend 下 `pnpm typecheck`、`pnpm test`、`pnpm build`。新增 Python 定向7通过，前端12通过/0失败/0跳过；类型检查及构建通过。全量 Python 222通过、0失败、0跳过（139.975秒）；原有财务与核验回归包含在内。

建议4分钟：选格力真实案例 → PDF提取（两期金额、原文及证据）→ 财务拆解（自身变化与会计影响分开、未闭合项保留）→ 研报纠错（构造陈述、下降35.0832亿元、证据跳转）→ 核验与交付及真实Agent失败轨迹。

仍未展示：全部93条来源逐行检查、其他收付款明细校验及完整文件版本链；当前仅核验/冲突摘要。尚无在线PDF上传、任意研报语义理解、审核写回或Agent合规最终解释。现金流逐项贡献没有现成贡献输出，保持未提供。经营因果需人工复核。

