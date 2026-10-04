# P30 只读项目事实门

P30 第一门将通过完整复验的 ECUC 项目报告（0.6–0.9）转换为结构化事实包。它是后续模型解释的输入与引用校验边界，目前没有调用 Ollama，也没有认证自由文本解释或问题相关性。P30 整阶段仍 implementing。

## 操作

已有 `run-project` 交付目录后，使用报告路径生成请求：

```bash
workbench prepare-project-explanation output/project/bundle/project-report.json --question "哪些证据记录了项目阻断？" --output output/request.json
```

输出必须不存在。请求固定问题、策略版本、报告 SHA-256、项目状态及允许引用的事实；每个事实保存 artifact 身份、源 SHA-256、JSON pointer、原始类型的值和内容摘要身份。只消费已有确定性审查允许的字段，不把完整 ECUC 文件放进请求。问题会原样进入请求；当前不发送到任何服务。事实可能仍含工程对象名称，应按原工程保密级别管理。

回答契约示意（尖括号内容必须替换为本次请求的真实值）：

```json
{
  "schema_version": "project-explanation-answer-0.1",
  "request_id": "<request.request_id>",
  "status": "selected",
  "claims": [{"fact_id": "<request.facts[0].fact_id>", "value": "blocked"}]
}
```

缺少支持时使用 `status: "unassessed"` 和空 `claims`。这只是声明未评估；不得凭一个请求内有效编号附加任意自然语言断言。

```bash
workbench validate-project-explanation output/project/bundle/project-report.json output/request.json output/answer.json
```

每次校验都重新复验项目并重建完整请求。错误编号、额外自由文本、状态/数值/对象值改写、重复引用、请求篡改及历史运行替换被拒绝，不补号。JSON `true` 不等于 `1`。`status: passed` 仅表示事实选取校验通过，原项目状态保存在 `project_status`，回答的 `unassessed` 保存在 `answer_status`。旧报告或不支持版本在进入事实包前拒绝；原审查命令继续独立可用。

请求不保存本机绝对源路径；报告依赖目录整体搬移后仍可验证。校验只读原始交付目录，临时审查文件在系统临时目录清理。它不启动 ECU、不打开总线、不更改配置。

## 验收与剩余工作

```bash
python scripts/run_project_explanation_scenarios.py --output output/p30/scenarios
python scripts/check_installed_explanation.py --output output/p30/installed
```

公开合成的 integration / transmitter 两工程覆盖 blocked 状态、正常事实选择、缺证据 unassessed、非法引用、状态改写、额外无证据文本、错误请求、中文及空格路径搬移和删除原输入。隔离安装使用无依赖 wheel，排除 checkout import，并再次复验归档。单元测试额外覆盖完整请求篡改、同配置新运行替换、依赖篡改和重复 JSON 字段。

后续仍属于 P30：接现有本地知识助手/Ollama，保存模型身份/提示/输入/原始输出、服务不可用回退、资料知识与项目事实分离，以及开发/独立验收问题和人工可用性评测。配置拒绝、影响范围、CAN 超时、诊断负响应的模型解释门尚未完成；这里的两项目 blocked 场景不能替代这些验收。
