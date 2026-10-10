# P30 本地模型与知识助手适配

先看[资产复用清单](p30-reuse-inventory.md)：复用现有 Ollama、已审核资料检索与证据定位，不另建知识库。原事实门和确定性项目审查继续独立可用。

## 使用

```bash
workbench explain-project output/project/bundle/project-report.json --question "哪些验收项阻断，缺什么证据？" --model qwen3.5:2b --ollama-url http://127.0.0.1:11434 --output output/explanation
```

地址必须是部署实际可达的服务 origin。原知识助手 Compose 不发布 Ollama 端口；在其 backend 网络内使用 `http://ollama:11434`，宿主机地址不能直接照抄。输出目录必须不存在。

需要资料检索时额外传入 `--knowledge-url http://127.0.0.1:18080 --knowledge-query "UDS timeout diagnosis"`。两项必须一起给出；资料检索只发送显式查询，不发送 ECUC 文件。`--timeout 30` 是每次 HTTP 请求的超时，不是整条流程总时限。无隐式重试或引用修补。只读请求仍可能唤起模型加载与现有 embedding 运算。

输出：

- `fact-request.json`：完整复验后的允许事实集合。
- `model-context.json`：本次选取的最多 24 个事实（累计 12000 字符预算）和最多 3 条已审核手册摘录；不足/未选取有明确 gap。
- `model-input.json`：实际提示、版本、结构化格式和生成选项；输入摘要记录在结果中。
- `raw-model-response.json`：服务返回的原始 JSON 对象（成功解码时）。`transport.json` 保留各 HTTP 请求、响应原文或错误，包括非法 JSON。
- `explanation.json` / `explanation.md`：项目原状态、独立模型处理状态、已核对的结构化引用、语义未验证的解释草稿、未执行的建议和缺口清单。

模型名称、前后两次模型 digest、服务版本、输入摘要、输出摘要、延迟与返回的 token 指标分别记录。模型 tag 在调用期间变化、截断、非法引用、对象/数值/严重度改写、手册摘录不匹配、历史请求替换均拒绝。模型不能调用工具、修改配置或打开总线。

结构校验 `status=passed` 只表示允许的引用和值经过核对；`project_status` 保留工程判定，`answer.semantic_status` 始终为 `unassessed`。模型自由文字不是已验证结论；不要把合法引用误认为整段文字语义成立。语义评测仍是 P30 未完成的独立门。

模型服务缺失时 CLI 返回 3 / blocked；输出被拒绝时返回 2 / refused；模型声明缺证据时返回 2 / unassessed。三种情况仍保留项目事实摘要。资料服务失败单独记录 gap，可继续仅基于项目事实生成。复验期间项目改变则清空旧事实展示并拒绝本次解释。

## 离线复验与验收

```bash
workbench verify-model-explanation output/project/bundle/project-report.json output/explanation
python scripts/run_model_explanation_scenarios.py --output output/model-scenarios
python scripts/check_installed_explanation.py --output output/model-installed
```

复验不使用网络，重新复验项目并依次重放捕获的请求/响应，再比较请求、结果、原始输出、Markdown 和完整文件清单。它验证保存证据的一致性，不认证服务身份或证明模型原文正确。报告及依赖整体搬移后仍可复验。

协议场景包含成功、非法引用、状态改写、手册不支持、非法 JSON、输出截断、模型 digest 漂移、服务不可用、超时、缺证据、未审核资料、无依据自然语言保持未评估；全部使用明确标识的合成 HTTP 服务。真实 Ollama/资料现场门及模型独立质量评测另记，不能由这套夹具替代。

接口依据：[Ollama chat](https://docs.ollama.com/api/chat) 的结构化 format / 非流式返回，[模型清单](https://docs.ollama.com/api/tags) 的 digest。知识助手接口按本机已读源码固定，详见复用清单。


## 现有 Docker 环境的实际路径

本轮直接复用 `simulink-assistant_backend` 网络和 `simulink-assistant-api:dev` 镜像。以下 PowerShell 示例在 Workbench 仓库根目录运行；输入是本轮最终场景生成的公开合成项目报告，输出须使用新的目录名：

```powershell
$workbenchRoot = (Get-Location).Path
$evidenceRoot = Join-Path $workbenchRoot "output\my-model-check"
New-Item -ItemType Directory -Force $evidenceRoot | Out-Null
docker run --rm --pull never --network simulink-assistant_backend `
  -e PYTHONPATH=/workspace/src `
  --mount "type=bind,source=$workbenchRoot,target=/workspace,readonly" `
  --mount "type=bind,source=$evidenceRoot,target=/results" `
  --entrypoint python simulink-assistant-api:dev -m automotive_workbench.cli `
  explain-project /workspace/output/p30-model-validation/final-scenarios/project/bundle/project-report.json `
  --question "项目报告最终状态是什么？" --model qwen3.5:2b `
  --ollama-url http://ollama:11434 --output /results/run
```

可选资料参数为 `--knowledge-url http://api:8000 --knowledge-query "AUTOSAR runnable RTE event mapping"`。输入换成自己的项目报告时，先保留其完整依赖目录；不要将原始私有工程输出提交到公共仓库。

真实模型开发观察和空间结论见[本轮完整报告](p30-upgrade-report-2026-10-05.md)。

## 提示 0.5：问题相关事实与模型默认推理

新请求优先点名的检查、请求字段及必要上下文；不再用无关通过项填满窗口。结构化生成限制事实 ID/原值配对、原文摘录和 unassessed 空列表；最终仍由独立校验器接受或拒绝。0.1–0.4 保存的请求继续使用原排序、提示与生成设置离线重放。

0.5 保留模型的默认推理模式，生成预算为 4096 token；本机 `think=false` 曾绕过 Ollama 的格式约束，开启推理又可能消耗预算导致截断。现场建议显式 `--timeout 120`，每次请求仍有上限且无隐式重试。格式和引用通过不代表语义正确。模型选择、XML 与多模态边界、微调启动条件见[模型适用性评估](p30-model-suitability.md)。

## 提示 0.12：按已验证模型 family 关闭 thinking

本机 qwen3.5 的 0.11 完整适配器归档显示两次请求都把 4096 token 用于 thinking，正文为空。0.12 在调用前读取并固定模型身份；只有 `details.families` 明确包含 `qwen35` 时才发送 `think=false`。qwen3-vl 沿用 0.8 起的独立 family 策略；未知 family 不强制开关。实际发送的选项仍保存在 `model-input.json`，模型调用前后 identity 必须一致。

0.1–0.11 的历史 payload 和重放保持不变。关闭 thinking 只修复“没有正文”的服务兼容性，不绕过结构化 schema、两项状态引用、类型化值、token 预算、模型 digest 或人工语义审核门。
