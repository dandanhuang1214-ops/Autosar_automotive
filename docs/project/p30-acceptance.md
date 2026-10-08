# P30 验收表

整阶段：implementing。首轮只读事实门 remote-accepted。实现 `a82ee62c758c82741aa083636744b5c6766892a3` / [run `37183484781`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37183484781) 七 job 全部 success；Windows/Ubuntu 事实场景、隔离安装、证据上传均 success。模型解释不在首轮已验收范围。

| 门 | 状态 | 证据与范围 |
|---|---|---|
| 只读复验事实输入 | remote-accepted | 项目 0.6–0.9 完整复验；报告、来源、问题、类型化值和策略绑定 |
| 严格引用与值校验 | remote-accepted | 非法编号、重复编号、值改写、额外文本、跨请求、历史运行、请求/依赖篡改拒绝；不补号 |
| 两工程 CLI / 搬移 | remote-accepted | 127 / 70 facts；各 4 类 CLI 拒绝；中文空格路径、删除原输入后复验 |
| 隔离安装 | remote-accepted | 无依赖 wheel、仓库外运行、排除 checkout、两工程流程与归档复验 |
| 双平台远端 | remote-accepted | `a82ee62` / [run `37183484781`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37183484781) 七 job success，双平台新增三步骤 success |
| Ollama 与现有知识助手 | remote-accepted | 原服务已恢复；只读接口、模型/提示/原始输出/回退、12 个协议场景及安装验证通过；真实模型质量另列 |
| 项目事实与资料知识分离 | remote-accepted | 原文检索与审核/来源核对，手册逐字摘录检查；草稿语义始终 unassessed |
| 冻结问题评测工具 | remote-accepted | `8735bc3` / run `37419810449` 七 job success；冻结证据/代码、分项评分与篡改拒绝 |
| 模型回答质量 | 未通过，继续 implementing | 早期六类冻结题与本轮 v3 开发配对均未达到质量门；最终 v3 仅 1/4 结构化任务通过，独立语义/资料适用性门未验收 |

## 提示 0.9 局部事实选择修正（2026-10-08）

点名检查时上下文筛选原先漏掉嵌套 binding 值和明确点名的阶段状态。实现改为选择问题明确请求的嵌套字段/阶段状态，并将提示版本加入 schema；旧提示重放保持原预算和 thinking 行为。完整实现、测试、隔离安装、提交和 CI 待本轮回填。

新题 v3 复用 P29 已见归档，属于开发回归，不能作为未见工程集或独立 gold。最终提示 0.9 双模型、两题配对中，六项 gold 全部进入上下文；qwen3.5 0/2 结构化通过，qwen3-vl 1/2 通过并引用 3/3 gold，另三次调用因 4096-token length 截断被拒。4/4 实际调用归档离线复验 passed。自然语言语义与资料适用性仍 unassessed，P30 整体保持 implementing。

本地证据：`output/p30-fact-validation/`。全量回归 400 项（398 passed、2 环境跳过），随后增加数值类型/对象身份负例，P30 与 topology 定向 9 项通过；56 schemas、76 bound/25 syntax-only、57-source mypy、Ruff、topology、pip check 与 whitespace 通过。源码与最终隔离安装场景通过。首次安装脚本误解析 venv Python 符号链接，修正为保留 venv 可执行路径后重跑通过。

后续状态回填固定实现 SHA 和真实 run/jobs，不把文档状态提交当实现验证。P25 人工验收、物理 ECU、商业生成边界保持。

## 远端记录（2026-10-04）

实现 `a82ee62c758c82741aa083636744b5c6766892a3` / [run `37183484781`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37183484781) 七 job 全部 success；Windows/Ubuntu 事实场景、隔离安装、证据上传均 success。

- `runtime-currency`：job `111380561415`，success。
- `core-contracts (windows-latest)`：job `111380561531`，success。
- `core-contracts (ubuntu-22.04)`：job `111380561539`，success。
- `runtime-evidence (ubuntu-22.04)`：job `111381028146`，success。
- `controlled-rejections (ubuntu-22.04)`：job `111381028182`，success。
- `runtime-evidence (windows-latest)`：job `111381028187`，success。
- `controlled-rejections (windows-latest)`：job `111381028195`，success。

原始记录 `output/p30-fact-validation/remote-ci.json`，双平台 artifact 为 `project-explanation-Windows` / `project-explanation-Linux`。本次回填是后续纯文档 `[skip ci]` 提交，固定引用上述实现 CI，不代表模型阶段验收。


## 模型适配本轮验收（2026-10-05）

- 协议/工程门 local-accepted：最终 409 tests（407 passed、2 环境跳过）；57 schemas、76 bound/25 syntax-only、61-source mypy、Ruff、topology、pip check、whitespace 通过。源码和无依赖隔离 wheel 各 12 个合成 HTTP 场景，含 schema、服务停止后的复验与归档复验；新增 8 项模型专项测试。
- 现场恢复原 Docker Desktop 及 Ollama/Qdrant/API，不下载镜像/模型，不改动原资料。原知识库 23 文档 / 15 可检索，模型三份均存在。真实检索取得 3 份原文摘录，保留 legacy_trusted 来源等级。
- 真实模型为 qwen3.5:2b，服务报告 digest `324d162be6ca5629ae4517c8710434d0bd2d665bc94dbad46e9af8fbf8a2f0df`，Ollama 0.31.1。共 6 次开发调用，1 次结构化单事实引用通过、5 次拒绝。提示 0.1 字段缺失，0.2 截断，0.3 双摘要误抄，0.4 单事实成功但带资料摘录与缺证据问题引用不合格；旧提示和原始失败可离线重放。
- 这些是开发观察，不是独立模型质量评测；不能把拒绝正确等同模型拒答正确，也不能用一条成功证明复杂解释可用。自然语言语义、问题相关性和建议可用性均未自动认证。
- 原服务缺失时的真实 blocked 回退另存 `live-unavailable`。本轮最终归档 `output/p30-model-validation/`，具体磁盘与资产结果见[复用盘点](p30-reuse-inventory.md)。
- P30 整阶段 implementing；下一项独立问题评测、输出约束适配和资料适用性/人工可用性。实现 `21a495e2047662084a6a30f78196ed6fd2f3f148` / [run `37264801076`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37264801076) 七 job 全部 success，双平台事实场景、模型场景、隔离安装及证据上传均 success。

## 模型适配远端记录（2026-10-06）

实现 `21a495e2047662084a6a30f78196ed6fd2f3f148` / [run `37264801076`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37264801076) 七 job 全部 success。固定 LF 写入确保模型归档可跨平台复验。

- `runtime-currency`：job `111619216006`，success。
- `core-contracts (windows-latest)`：job `111619216183`，success。
- `core-contracts (ubuntu-22.04)`：job `111619216213`，success。
- `controlled-rejections (ubuntu-22.04)`：job `111620503794`，success。
- `runtime-evidence (windows-latest)`：job `111620503805`，success。
- `controlled-rejections (windows-latest)`：job `111620503826`，success。
- `runtime-evidence (ubuntu-22.04)`：job `111620503830`，success。

原始记录：`output/p30-model-validation/remote-ci.json`。后续状态文档提交不是新的实现验收；真实模型质量仍未通过，六类评测在 P30 内继续。

跨平台实证（2026-10-06）：下载上述 run 的 `project-explanation-Windows`，源码 12 例及安装后 12 例共 24 份模型解释在 Linux 完整离线复验通过；原始结果 `output/p30-model-validation/windows-linux-replay.json`。

## 六类冻结评测实际结果（2026-10-06）

实现 `8735bc3b672bd4d95902fb5abcb431d88248efc1` / [run `37419810449`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37419810449) 七 job 全部 success。本地 413 tests（411 passed、2 环境跳过），新增四项评分与冻结篡改测试；57 schemas、76 bound/25 syntax-only、Ruff、新脚本 mypy、topology、whitespace 通过。

- `runtime-currency`：job `112126426660`，success。
- `core-contracts (windows-latest)`：job `112126426708`，success。
- `core-contracts (ubuntu-22.04)`：job `112126426772`，success。
- `runtime-evidence (windows-latest)`：job `112127980565`，success。
- `controlled-rejections (windows-latest)`：job `112127980645`，success。
- `controlled-rejections (ubuntu-22.04)`：job `112127980648`，success。
- `runtime-evidence (ubuntu-22.04)`：job `112127980742`，success。

远端原始记录 `output/p30-evaluation/remote-ci.json`。真实现场结果 `output/p30-evaluation/trial-v1-deps/summary.json`，五题两模式共十次推理全部 refused，全部归档离线复验 passed；历史替换在模型调用前拒绝。冻结摘要 `71d4396eb2913a6b0c1ec832d2eacba68e65a01376e4777b672793e8121ac6a4`。模型保持 qwen3.5:2b / 提示 0.4，未用本组结果回调提示。

配置拒绝、影响范围、CAN 超时各两条 gold 均未进入上下文；诊断两条全部进入但模型引用仍错误。五次检索每次返回三条来源，不能代替资料相关性验收。没有有效模型拒答，不能把十次校验器拒绝算成模型正确率。问题由代理编写并在推理前冻结，不是独立人工 gold。详见[评测指南](p30-model-evaluation-guide.md)。

下一项仍为 P30：版本化修正问题相关事实选择，优先纳入失败原因、精确影响对象与必要上下文；保留提示 0.1–0.4 的历史重放。随后针对结构化值、原文摘录和 unassessed 空引用约束改进输出，在新冻结问题上验收。当前六题已见，不再冒充后续未见测试；人工语义/资料适用性仍待验收。

后续纯文档状态提交引用以上实现 CI，不把状态回填当作新实现或模型质量验收。


## 提示 0.5 问题相关事实与模型评估（2026-10-08）

实现 `c60d8af5c0cc72c632a679e06fc264747267fb95` / [run `37646726266`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37646726266)：七个 job 全部 success；包括 `runtime-currency` `112879318052`、`core-contracts (windows-latest)` `112879318098`、`core-contracts (ubuntu-22.04)` `112879318414`、`runtime-evidence (windows-latest)` `112883075265`、`controlled-rejections (ubuntu-22.04)` `112883075330`、`runtime-evidence (ubuntu-22.04)` `112883075331`、`controlled-rejections (windows-latest)` `112883075370`。

418 tests（416 passed、2 环境跳过），17 项 P30 定向通过；隔离安装、合成协议失败闭环及旧提示归档重放通过。qwen3.5 冻结 v2 为 11 次截断拒绝、1 次超时、0 次结构化通过；12 份离线复验通过，gold 上下文覆盖 11/11。qwen3-vl 同题对照已离线复验 11 份归档（7 次超时、4 次 HTTP 400）；末份及汇总含空字节，不能完整验收，无有效模型回答。质量门不通过，整阶段保持 implementing。详见[模型适用性评估](p30-model-suitability.md)。

下一项是在工作台 120 秒边界内补足有效模型对照，完成独立人工语义/资料适用性验收，再确定用途和是否需要更强基线或训练。

下一项仍为 P30：完成本轮冻结集与现有模型对照，按证据决定模型可用任务范围；随后建立人工语义/资料适用性标注，再判断更强模型基线或微调。


## 提示 0.6 服务兼容性修正（2026-10-08）

提示 0.6 已实现：针对本机 grammar 重复次数限制，将生成草稿上限从 4000 收紧至 160 字符；0.1–0.5 重放保持。418 项回归（416 passed、2 环境跳过）、13 项模型测试、schema/类型/拓扑检查通过；11 份既有 0.5 真实归档修改后复验通过。隔离安装通过（12 类协议场景及归档复验）；两条提示 0.6 的已见问题开发调用均超时、2/2 归档复验通过，无有效模型答复。本次实现 `ff08e4d58bacea55d2e6ea36b1e2e9d042ef55e3` 的 [run `37713395967`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37713395967) 七 job 全部 success。

本机服务日志证明 grammar 的 `char{0,4000}` 超出重复次数限制；这是服务兼容性阻塞，不能据此归因于模型的汽车领域能力。生成限制变小，独立引用/类型校验和语义 unassessed 边界不变。

下一项仍为 P30：验收 0.6 的服务兼容性，恢复 120 秒内完整模型对照，随后按[人工验收表](p30-human-review-guide.md)完成独立语义/资料适用性审阅；质量门通过前不宣称模型解释可用。


### P30：提示 0.7 上下文预算与 token 用量门（2026-10-08）

- 新冻结提示 0.7 绑定 `num_ctx=8192` / `num_predict=4096`；0.5/0.6 的提示、16K payload 与历史复验保持。结构化生成输出上限为 160 字符；完成响应缺少整型 token 计数或 `prompt_eval_count + eval_count` 超上下文时拒绝。
- 已见诊断问题在 standalone 修改 payload 探针中 8K 返回成功（30.717 秒、3460 prompt / 292 completion tokens，目标事实 2/2），但它没有完整 adapter 重放边界。正式 0.7 adapter 同问题调用 56.251 秒，输出到 4096 token 上限而被拒绝；归档 `verify-model-explanation` passed，保持实际模型 status=refused。两个过程证明 8K 请求能较快完成，也暴露生成长度受上下文/模型行为影响，不能宣称稳定质量。
- 新增 token 上下文超限负例和版本化 payload 回归。本地全量 419 tests（417 passed、2 环境跳过）；14 项模型定向、Ruff、54-source 类型检查、57 schemas/76 bound/25 syntax-only examples、拓扑、pip check、compileall、安装后 12 协议场景与归档复验均通过。
- 实现 `04e50034dc2e9b517d8fca80a244225f2847126a` / [run `37726246623`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37726246623) 七 job 全部 success：`runtime-currency` 113144964548；`core-contracts (windows-latest)` 113144964747；`core-contracts (ubuntu-22.04)` 113144964916；`controlled-rejections (windows-latest)` 113146832094；`runtime-evidence (windows-latest)` 113146832136；`controlled-rejections (ubuntu-22.04)` 113146832158；`runtime-evidence (ubuntu-22.04)` 113146832196。模型 v2 问题已见；结构化拒绝仍有发生，完整模型质量、语义及资料适用性人工审核未完成。见[模型适用性评估](p30-model-suitability.md)和[人工验收表](p30-human-review-guide.md)。
- 下一项仍为 P30：保留模型生成结束状态、输出 token 数及耗时诊断；确定 8K 下不同模型和问题类型能否在 120 秒内结构化完成，再建立新冻结集并完成独立人工语义/资料适用性审阅。质量门前不将解释结果用于工程判定。


### P30：提示 0.7 预算实现远端验收（2026-10-08）

- 实现 `04e50034dc2e9b517d8fca80a244225f2847126a` / [run `37726246623`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37726246623) 七 job 全部 success：`runtime-currency` 113144964548；`core-contracts (windows-latest)` 113144964747；`core-contracts (ubuntu-22.04)` 113144964916；`controlled-rejections (windows-latest)` 113146832094；`runtime-evidence (windows-latest)` 113146832136；`controlled-rejections (ubuntu-22.04)` 113146832158；`runtime-evidence (ubuntu-22.04)` 113146832196。
- 419 项全量测试中 417 passed、2 环境跳过；14 项模型专项；隔离安装后的 12 项协议夹具和离线归档复验通过；Ruff、54-source mypy、57 schemas、76 schema-bound / 25 syntax-only、CI topology、pip check、compileall 通过。
- 本机正式 adapter 以 8K prompt 返回 4096-token length 截断并拒绝；该受控失败的归档离线复验通过。已见问题的直接修改 payload 探针有一次 30.717s 的 292-token 完成结果，不能代替正式 adapter 重放或新冻结问题对照。
- 本次记录属于 `[skip ci]` 文档状态回填，引用实现提交及其实际 run；新改运行代码时仍须该提交自己的 CI。
- 下一项为 P30：先确定 8K 下响应结束、耗时和 token 计数在模型/问题间的稳定范围，再冻结新评测集；完成独立人工语义及资料适用性审阅。现有代理编写的 gold 不是独立人工验收。P30 仍 implementing。


### P30：提示 0.8 的 qwen3-vl 思考模式适配（2026-10-08）

- qwen3-vl 本机 identity families=[qwen3vl] 经运行时核对后，在提示 0.8 使用 think=false；qwen3.5 和提示 0.1–0.7 不变，失败/成功均保存实际 model-input、身份与服务输出。不是所有 thinking 模型共用一个强制开关。
- 同一已见 qwen3-vl 问题的提示 0.7 默认调用用尽 4096 token、message.content 为空；提示 0.8 适配器调用约 25.7 秒结束，1129 prompt / 348 output tokens，结束原因为 stop。输出通过模型 schema、严格 fact_id/typed-value 校验，两个 gold 事实均被引用，正式归档离线复验通过。自然语言解释未经人工审核，prose 仍 unassessed；单个已见开发样本不是质量评估。
- 新增模型家族策略和归档复验回归。当前本地全量 420 tests（418 passed、2 环境跳过），15 项 P30 模型定向通过；隔离安装 12 协议场景/归档复验通过；Ruff、54-source mypy、57 schemas/76 bound/25 syntax-only、topology、pip check、compileall 均通过。
- 提示 0.8 的实现 `cb6294b8a9161647733c636ed07411b0975b1389` / [run `37733947430`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37733947430) 七 job 全部 success。下一项用新冻结问题配对 qwen3.5 与 qwen3-vl，再完成独立人工语义和资料适用性审阅；P30 继续 implementing。


### P30：提示 0.8 远端验收与六题已见回归（2026-10-08）

- 实现 cb6294b8a9161647733c636ed07411b0975b1389 / [run 37733947430](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37733947430) 七个 job 全部 success：runtime-currency 113169146393；core-contracts Windows 113169146725 / Ubuntu 113169146661；controlled-rejections Windows 113170820518 / Ubuntu 113170820559；runtime-evidence Windows 113170820597 / Ubuntu 113170820534。
- 全量 420 tests（418 passed、2 环境跳过）；15 项模型专项；隔离安装后 12 项协议场景及归档复验、Ruff、54-source mypy、57 schemas/76 bound/25 syntax-only examples、CI topology、pip check、compileall 通过。
- 新冻结 v2 全部题目明确为已见回归，共六个项目模式问题、一个历史 preflight 控制。qwen3-vl 六题中三题 structured pass、三题因 4096-token length 截断拒绝；gold recall 通过项为 1.0。7/7 行（含历史控制）归档复验 passed。初次从宿主 Ollama 地址运行一题因 DNS blocked，该失败另存，没有计为模型拒绝；正式运行在原 backend 容器网络完成。
- 一条 `diagnostic-affected-objects` 正式调用 25.7 秒、1129 prompt / 348 output tokens；schema 及两个 gold 引用通过。其中文解释没有经人工语义核对，仍为 unassessed。旧测试不是新未见评测，也不能替代人工 review。
- 下一项：冻结一批未参与提示调试的具体工程问题，做 qwen3.5 与 qwen3-vl 完整配对并记录结束原因/token/耗时；完成独立人工语义和资料适用性记录。P30 仍 implementing。
