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
| 模型回答质量 | 部分通过，继续 implementing | 用户已确认 v5/v6 qwen3-vl 简单状态文本；0.12 恢复 qwen3.5 输出。0.16 的 v7 开发集 6/6 精确字段任务通过，但引用由系统绑定、草稿只经开发者审读。一般解释、独立语义与资料适用性仍未验收 |

## 提示 0.9 局部事实选择修正（2026-10-08）

点名检查时上下文筛选原先漏掉嵌套 binding 值和明确点名的阶段状态。实现改为选择问题明确请求的嵌套字段/阶段状态，并将提示版本加入 schema；旧提示重放保持原预算和 thinking 行为。实现 `11361788108a8793d6b3808fe85ab506fa8e0b82` / [run `37742242675`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37742242675) 七 job 全部 success：runtime-currency `113195398856`；core-contracts Windows `113195398938` / Ubuntu `113195399041`；controlled-rejections Windows `113197537909` / Ubuntu `113197537982`；runtime-evidence Windows `113197538027` / Ubuntu `113197538036`。

新题 v3 复用 P29 已见归档，属于开发回归，不能作为未见工程集或独立 gold。最终提示 0.9 双模型、两题配对中，六项 gold 全部进入上下文；qwen3.5 0/2 结构化通过，qwen3-vl 1/2 通过并引用 3/3 gold，另三次调用因 4096-token length 截断被拒。4/4 实际调用归档离线复验 passed。自然语言语义与资料适用性仍 unassessed，P30 整体保持 implementing。

## 提示 0.10 阶段状态上下文范围（2026-10-08）

只问 overall/project 与具名阶段 status 时，0.9 会选入 24 条事实；0.10 将其约束为这两条目标事实。v4 使用 `integration` 和 `transmitter` 两个不同 P29 报告，是开发回归题；题目/证据不能当作独立 held-out 质量集。最终上下文 gold 覆盖 4/4，qwen3-vl 2/2 结构化通过且每题引用 2/2，qwen3.5 0/2（一次服务超时、一次 length 截断）。qwen3-vl 完整原始响应归档离线复验通过。该结果仅支持继续评估短状态汇总；自然语言、工程语义和独立审阅尚未验收。

提示 0.10 本地实现检查：422 tests（420 passed、2 环境跳过）；17 项 P30 模型专项通过；隔离 wheel 两项目、12 项模型 HTTP 合成场景与归档复验通过；Ruff、8-source mypy、57 schemas / 76 schema-bound / 25 syntax-only examples、topology、pip check、compileall 通过。实现 `0d9c3ba4bf4faae5fb7bda5af43241cd7287a3c2` / [run `37771946406`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37771946406) 七 job 全部 success：runtime-currency `113293415542`；core-contracts Windows `113293415264`、Ubuntu `113293415630`；controlled-rejections Ubuntu `113296212241`、Windows `113296212339`；runtime-evidence Windows `113296212256`、Ubuntu `113296212372`。后续纯文档状态提交不作为新的实现验收。

## 提示 0.10 不同证据配对（2026-10-08）

v5 在实现/CI 完成后冻结，复用未在 P30 先前 cohorts 出现的 `repeat`、`identity-mismatch` 报告。代理 gold 按报告中两个状态字段预先编写；不等于独立人工 gold。qwen3.5 两题均未结构化通过：repeat 135.8s 超时，identity-mismatch 70.6s 被拒；上下文均覆盖 2/2，但 gold 引用 0/2。qwen3-vl 的 repeat 题 68.0s 通过并引用 2/2；identity-mismatch 19.5s 结构化输出通过但只引用 1/2，故任务未通过。四份最终调用归档离线复验 passed；语义与人工可用性仍 pending。

2026-10-09 人工复核：用户对 qwen3-vl 两条状态文本逐题核对后确认内容均正确。此结论覆盖项目状态回答内容，不等价于引用门通过；identity-mismatch 的结构化 claims 仍缺项目 `/status` 事实 ID。一般工程解释、资料适用性和整体可用性未由这两题证明。

## 提示 0.11 引用完整性修正（2026-10-09）

0.11 将整体 + 具名阶段状态范围明确为两个必需的结构化 claim，JSON schema 限制至少两条，独立校验进一步要求完整匹配两条目标 fact ID。旧版重放保持。全量 423 tests（421 passed、2 环境跳过），18 项模型专项；Ruff、单文件 mypy、57 schemas/76 bound/25 syntax-only、topology、compileall、隔离 wheel 两项目与 12 个合成 HTTP 场景、2 份模型归档重放通过。wheel SHA-256：`4d754e66317837bb2587da56c944622c141cbaf19f4ca1fc18811344cc46d841`。

v5 已见证据仅作开发回归：qwen3-vl identity-mismatch 现在引用 2/2、21.5 秒通过；repeat length 截断拒绝。qwen3.5 两题均 length 截断拒绝。四份本轮生成的归档均离线复验 passed。实现 `355955cf883e17b3adf2d77294041b220f8d9b00` / [run `37906579233`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37906579233) 七 job 全部 success：runtime-currency `113741384759`；core-contracts Windows `113741384479`、Ubuntu `113741384881`；controlled-rejections Ubuntu `113743605146`、Windows `113743605169`；runtime-evidence Windows `113743605179`、Ubuntu `113743605217`。提示 0.11 实现门 remote-accepted；v5 不作为新版本独立验收，模型语义与适用性范围仍有限。

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

## 提示 0.11 配对复验 v6（2026-10-09）

使用 `backend-blocked` 与 `wrong-response-id` 两份 P29 报告，测试 overall 与 ECUC stage 状态复述。两报告未用于 0.11 提示调整，但曾进入更早版本的问题组；结果只能说明 0.11 在这两个新样本上的表现，不能称为全新证据集或独立人工 gold。qwen3.5 冻结清单摘要为 `e18610adccdfb31598869e52920a35ff6b924d16555aa8f1e741b3b5a6114227`，qwen3-vl 为 `f3b492c570346fd73636920987c0699b77a1b8bf70387811dc7b33c879ca746f`。

qwen3-vl 两题均通过结构化任务，gold 引用 2/2，耗时 66.7 秒和 33.0 秒；qwen3.5 两题均因不完整或无效模型输出被严格校验拒绝，耗时 102.4 秒和 78.3 秒，引用 0/2。四份调用归档的离线复验均通过。这里的“通过”只代表 schema、引用及归档复验通过，不代表自然语言已经人工核实。qwen3-vl 的两条答案待人工检查；手册适用性、一般工程解释和整体模型适用性仍未验收。原始输出仅保留在本机 `output/p30-continuation-audit/trial-v6-*`。本轮只新增冻结评测文档，没有改运行代码；0.11 实现验收仍对应 `355955cf883e17b3adf2d77294041b220f8d9b00` / run `37906579233`。

2026-10-10 用户确认上述 qwen3-vl 两条回答文字准确且可用。人工结论只覆盖这两道状态复述；没有查询手册，也不证明复杂解释、因果诊断或跨项目泛化。

## 提示 0.12 qwen3.5 输出恢复（2026-10-10）

0.11 的两份 qwen3.5 原始响应均用满 4096 token、正文为空，thinking 字段分别约 16.6K/16.8K 字符。0.12 保留提示和严格引用规则，仅在服务身份明确为 family=`qwen35` 时设置 `think=false`；旧提示重放与 qwen3-vl 既有策略保持。

相同 v6 两题以新实现重冻后均通过：正常 stop、thinking 为空，prompt/output token 1017/324 与 1012/289，适配耗时 32.3/19.8 秒，目标事实引用均为 2/2，离线复验通过。清单摘要 `5eb332c0834a27103b2391010d76c36e40ef8305c2d0275fc7a7ffc6b6081801`。这是修复对照，不是新 held-out 质量结论。

本地 424 tests（422 passed、2 环境跳过）、19 项模型专项、12 类合成协议、schema/topology/Ruff/scoped mypy/compileall 和隔离 wheel 均通过；wheel SHA-256 `e001b22ada382b436b351070773f77719a30e38ebe64e1182339297a17284a26`。

实现 `656098b8b8dca8373ba3974ced45a317f25d05ec` / [run `38012423168`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/38012423168) 七 job 全部 success：runtime-currency `114095165644`；core-contracts Windows `114095165813`、Ubuntu `114095165919`；controlled-rejections Ubuntu `114096657670`、Windows `114096657681`；runtime-evidence Ubuntu `114096657716`、Windows `114096657724`。提示 0.12 实现状态 remote-accepted；后续纯文档状态提交不作为新的实现验收。下一项使用未参与本轮修复的问题分别计量 qwen3.5 与 qwen3-vl；一般解释、资料适用性和跨项目用途仍保持未验收。

## 提示 0.16 精确字段绑定（2026-10-10）

[v7 cohort](../research/p30-evaluation-cohort-v7.json) 的三个报告在冻结后被用于 0.13–0.16 调整，因此属于开发集。0.16 对点名检查的直接字段采用确定性完整绑定；模型生成的旧契约字段即使存在也被记录为偏差并忽略，只消费匹配 request ID 的非空说明草稿。精确字段问题不查询手册，避免把一般资料命中误当作项目字段依据。

qwen3.5 最终清单摘要 `ef165dc67f2a8dc441e64f974f24bf9f6240e0644ad30c56bb94f1ac93f4e497`；三题 × project/retrieval 共 6/6 结构任务通过，各 4/4 目标事实由系统绑定，6/6 归档离线复验通过。开发者审读确认六份草稿都覆盖 tx/rx status/reason，但不是独立人工验收，输出继续标记 prose/semantic unassessed。

本地 426 tests（424 passed、2 环境跳过）；12 个合成 HTTP 场景、Ruff、8-source mypy、57 schemas / 76 schema-bound / 25 syntax-only、CI topology、compileall、diff check 与隔离 wheel 验证通过。wheel SHA-256 `2b75cd50fcb844dbb1c11bd3b5dc22e487e1bbd375d83d5bd69e3da89856c05f`。实现 `7cca980e09423c1ac689c29e0ce914ff7fde2a6c` / [run `38038842587`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/38038842587) 七 job 全部 success：runtime-currency `114174869075`；core-contracts Windows `114174869188`、Ubuntu `114174869219`；runtime-evidence Ubuntu `114176095737`、Windows `114176095758`；controlled-rejections Windows `114176095745`、Ubuntu `114176095876`。提示 0.16 实现 remote-accepted；后续纯文档状态提交不作为新的实现验收。


文档/冻结题集提交 `e311512` 已推送；该提交的 [CI run `37912242301`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37912242301) 七项全部 success：runtime-currency `113759898063`；core-contracts Ubuntu `113759898327`、Windows `113759898606`；controlled-rejections Ubuntu `113761756218`、Windows `113761756282`；runtime-evidence Ubuntu `113761756289`、Windows `113761756308`。该 run 验证文档提交工作树满足 CI，不作为新的模型质量验收。

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


## 提示 0.22：复杂事实与资料适用性边界（2026-10-10）

提示 0.17–0.22 区分“只复述点名字段”和“解释/比较点名检查”。复杂问题所需的 status、reason、对象身份、字段定义和 before/after 值由确定性代码完整绑定；当前版本只消费模型的两字段草稿，并要求身份、定义和前后值逐字保留，缺失或改写即拒绝。标准/手册要求题不使用项目策略证明通用要求，实际模型输入移除 `project_status` 和项目事实；有无检索摘录都只能生成待审核的资料缺口说明，最终状态固定为 `unassessed`。提示 0.1–0.21 的归档重放语义保留。

[v8 cohort](../research/p30-evaluation-cohort-v8.json) 在冻结后用于 0.17–0.21 提示开发，最终 0.21 的三题、两模式共 6/6 达到机器边界，故明确不作为 held-out。随后在 0.22 实现不再变化后冻结 [v9 cohort](../research/p30-evaluation-cohort-v9.json)，清单摘要 `0fa1fec40c8a189db8683a89da0889d6fb037f545181b5315923a1efc960f701`。qwen3.5:2b 的六次 project/retrieval 调用中：资料适用性题 2/2 返回有效 `unassessed` 且没有项目或手册 claim；任务引用题 2/2 因模型漏掉定义路径开头 `/` 被拒；unsupported-field 题 2/2 因模型生成中文弯引号导致 JSON 解析失败。6/6 归档离线复验通过。最终为 2/6 结构任务成功、4/6 fail closed；拒绝不是正确回答，也不满足一般复杂解释质量门。

本地实现验收：431 tests（429 passed、2 环境跳过）；Ruff、62-source mypy、57 schemas / 76 schema-bound / 25 syntax-only examples、CI topology 和 diff check 通过；源码项目事实场景、12 个合成模型协议场景以及隔离 wheel 的两工程、12 个模型场景和归档重放通过。wheel SHA-256 `08fc3e6497da9f651a0dd5e741e1f6bc2b72fa56e39c6e69cb197426194c9042`。实现当前为 local-accepted，提交和远端 CI 待记录，不能标作 remote-accepted。

P30 保持 implementing。下一项是由独立审阅者核对 v9 两份资料缺口说明的准确性与可用性；一般复杂解释路径不在 v9 上继续调参，应在更强文本基线与确定性模板/语法约束之间作出实现选择，再用新的未见 cohort 复验。
