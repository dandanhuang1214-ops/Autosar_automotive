# P30 六类冻结问题评测

当前模型适配已通过双平台工程验收，但模型解释质量仍待验收。本轮在提示 0.4 之后冻结新问题，复用已经保存、可以离线复验的项目证据，不重新执行 ECU 或 CAN 实验。

## 问题与计量

问题清单位于 [p30-evaluation-cohort-v1.json](../research/p30-evaluation-cohort-v1.json)：配置保护拒绝、配置影响对象、CAN 超时、诊断负响应、物理 ECU 缺证据、历史运行替换。前四类 gold 是明确的 artifact/pointer/类型化值；缺证据要求模型返回结构化 unassessed；历史替换必须在推理前被工程复验拒绝。

这组问题由代理根据既有证据编写，与早先六次提示开发调用分开，在查看本组模型输出前冻结。它不是独立人工 gold，也没有用 P24 冻结题库调参。看到结果后不能继续宣称本组是未见测试；改提示或选事实策略应另建开发试验和后续验收组。

- 确定性事实：完整项目复验且 gold 唯一匹配，保存请求摘要。
- 上下文覆盖：gold 有多少实际进入 24 条事实窗口；漏选单独记录。
- 模型引用：通过原严格引用门后计算 gold recall，引用通过不代表答全。
- 缺证据：只有有效的模型 unassessed 才记为结构化拒答；校验器拒绝、服务不可用不计模型正确拒答。
- 检索：与无检索模式使用同题、同模型、同提示；记录来源数量、逐字摘录通过数及资料缺口。没有人工相关性 gold，不能将“有命中”称为检索准确。
- 历史替换：记录调用前拒绝，不放入模型准确率分母。
- 自然语言、因果解释、资料适用性和人工可用性保持 unassessed。

## 可重复入口

先具备清单引用的本地 P29 归档；它们不随公共仓库分发。路径变化时复制清单并显式更新路径，重新冻结，不能覆盖旧 manifest。完整模型评测需要工作台 CAN 可选依赖才能复验 CAN 项目。

```bash
PYTHONPATH=src .venv/bin/python scripts/assess_model_explanation.py --root . freeze \
  --spec docs/research/p30-evaluation-cohort-v1.json \
  --output output/p30-evaluation/frozen-v1.json \
  --model qwen3.5:2b \
  --model-digest 324d162be6ca5629ae4517c8710434d0bd2d665bc94dbad46e9af8fbf8a2f0df
```

冻结会复验每份项目，核对预先编写的 gold，保存完整 bundle 文件集合摘要、事实请求摘要、模型摘要、提示版本和适配/评分脚本摘要。将输出的 manifest_sha256 单独记录，再运行：

```bash
PYTHONPATH=src .venv/bin/python scripts/assess_model_explanation.py --root . run \
  --manifest output/p30-evaluation/frozen-v1.json \
  --manifest-sha256 <冻结时记录的摘要> \
  --output output/p30-evaluation/new-trial \
  --ollama-url <可达的Ollama源地址> \
  --knowledge-url <可达的知识助手源地址>
```

输出目录必须不存在。代码或证据变化先拒绝；每次推理归档均离线重放后才评分，中途失败保留原文件及已完成 partial，不伪造完整结果。省略 knowledge-url 只运行项目事实模式。最终 summary 保留逐题结果，不把工程保护、上下文覆盖和语义质量合并成一个“准确率”。

当前原 Docker backend 内部地址为 `http://ollama:11434` / `http://api:8000`，不向宿主机默认开放。现场复用原 API 镜像的 Python 3.12，同时只读挂载工作台现有 `.venv/lib/python3.12/site-packages`；首次未挂载依赖的启动因缺 cantools 失败且没有模型调用。依赖导入和 bitstruct 编解码实测后再运行，不安装新依赖或下载模型。不同机器必须重新验证解释器/本地扩展兼容性，不能假定任意虚拟环境均可复用。

本轮冻结摘要：`71d4396eb2913a6b0c1ec832d2eacba68e65a01376e4777b672793e8121ac6a4`。完整证据保存于 `output/p30-evaluation/`，资料原文留在本地忽略目录。实测结果和后续 CI 结论见 P30 验收表及完整报告。

## 本轮执行结论

五题分别执行无检索/检索两种模式，共十次真实推理，均 refused；历史替换在推理前拒绝。所有十份调用归档离线复验通过。前三类问题的 gold 上下文覆盖为 0/2，诊断为 2/2；缺证据题没有有效模型拒答。此结果定位了上下文漏选与输出契约两个问题，不支持复杂工程解释已可用的结论。实现 `8735bc3b672bd4d95902fb5abcb431d88248efc1` / [run `37419810449`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37419810449) 七 job 全部 success 验收的是评测实现，具体质量结果见完整报告。


## 提示 0.5 后的新冻结集

[p30-evaluation-cohort-v2.json](../research/p30-evaluation-cohort-v2.json)包含五个新问题与两个明确标注的已见控制题：前后类型化值、诊断受影响对象、CAN ID 不匹配、诊断超时、生成来源缺失，加上负响应/历史替换控制。首次 gold 把 XML 数字文本写为 JSON 数字，冻结入口严格拒绝；核对原值为字符串后改正，模型尚未调用。此 gold 修正不用于修改解析器或放宽类型校验。

七题共 11 项目标事实，全部进入 0.5 上下文。模型和提示固定后分别冻结两个已安装模型，分开保存 manifest 摘要，不下载新权重。先运行 qwen3.5 的项目/检索配对，再运行 qwen3-vl 的同题对照，避免同时加载干扰延迟。原样保留所有失败；自然语言和资料相关性仍需人工评价。

## 冻结 v2 结果（2026-10-08）

`qwen3.5:2b`：12 次配对生成（6 有效问题 × 项目/检索），11 次输出截断拒绝、1 次服务超时，0 次通过；12/12 归档离线复验通过，gold 覆盖 11/11。历史替换控制在推理前拒绝。

`qwen3-vl:2b` 同一冻结清单有 11 份通过离线复验的归档：7 次请求超时、4 次 HTTP 400；第 12 份及 partial/summary 含空字节，原文件保留。没有有效完整 summary 或模型答复，不能与 qwen3.5 比通过率。模型适用性和资源限制见[适用性评估](p30-model-suitability.md)。P30 质量门未通过，阶段保持 implementing。

人工验收的执行顺序和逐题记录见[人工语义与资料适用性验收](p30-human-review-guide.md)；当前均待独立审阅，不由代理填报通过。

提示 0.7 绑定 8K / 4096-token 预算，已见问题正式 adapter 仍出现 `done_reason=length`，被拒绝且可离线复验。直接修改 payload 的一个请求虽完成，但不能视作该 adapter 门通过。下一轮保持每项记录响应终止原因、prompt/eval token 和时间；不将已见问题用于未见质量分。


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


### 提示 0.9 事实选择开发对照（2026-10-08）

新问题集 [v3](../research/p30-evaluation-cohort-v3.json) 要求诊断阶段状态、检查状态/reason 与嵌套 binding 数值。问题文本在调用前冻结；它们复用既有 P29 报告，因此属于新的提示开发题，不是未见工程证据或独立人工 gold。模型 digest 分别固定为 qwen3.5 `324d162be6ca5629ae4517c8710434d0bd2d665bc94dbad46e9af8fbf8a2f0df` 与 qwen3-vl `0635d9d857d497aeadba3d7d27485746c50554446f9f6ec01ef39788221adbe8`。提示 0.8 与 0.9 的冻结清单和原始证据留在本地 `output/p30-continuation-audit/`。

提示 0.8 初跑四条调用均未完成目标任务：三条被 4096-token length 截断；一条 qwen3-vl 响应在 schema 层通过，但没有引用任何 gold，不能计为正确。它揭示点名检查时会漏掉嵌套 `binding/request_id`、`response_id`、`did` 和明确询问的 `stages/ecuc/status`。

提示 0.9 修复这类嵌套/阶段字段选择，并把该版本加入模型输出 schema。以最终实现重冻后，两模型的目标事实覆盖均为 6/6。配对结果：qwen3.5 两题均因 `done_reason=length`、4096 输出 token 截断而拒绝；qwen3-vl 的诊断 backend 题同样截断拒绝，绑定数值题在 43.4 秒内 stop，1090 prompt / 372 output tokens，并引用 3/3 gold。四份最终归档全部离线复验通过。结构化成功只有一题，模型自然语言和工程语义仍未审；题目复用已见证据，不能代表 held-out 质量。

因此 P30 仍 implementing。下一步冻结项目证据不同、且未参与本轮提示调试的问题集，先核对目标上下文覆盖后再做完整配对；同时由独立审阅者对唯一通过样本逐项审阅自然语言、证据边界和适用性。若没有独立审阅，语义门保持 pending。


### 提示 0.10 阶段状态范围开发对照（2026-10-08）

[v4 cohort](../research/p30-evaluation-cohort-v4.json)分别引用 P29 `integration` 与 `transmitter` 报告，问题要求 project 与 ECUC stage 的整体状态。该组用于开发 0.10 的阶段专属上下文筛选，证据不是独立 held-out 集；两模型清单摘要分别是 qwen3.5 `61d11e49286edf7ab6de7624c00c8706f79839f5a4e559aa65e9f4b671fb7356` 和 qwen3-vl `cf9c5540d5dd404e6b06fcc1f7635bf998368a73c01b9d5ca7d348f0dde8b88e`。实际冻结清单、服务输出和汇总仅在本机 `output/p30-continuation-audit/`。

0.9 每题提供 24 条事实，qwen3.5 一次超时、一次截断，qwen3-vl 两次截断。0.10 改为每题只向模型提供 project status 与具名 stage status 两条事实。qwen3.5 仍 0/2（一次超时、一次截断）；qwen3-vl 在 61.1 秒与 32.6 秒完成，两次均 stop、引用 2/2 gold。两个 qwen3-vl 归档均离线复验 passed。结果说明精确缩小上下文帮助 qwen3-vl 完成简单状态任务，但同一修改没有让 qwen3.5 达到任务门。

这两份答案的自然语言与可用性仍需独立审阅；不将结构化引用通过当作模型语义质量通过。后续题目应使用尚未调试过的工程证据，并先完成盲化语义 gold，再运行模型配对。


### v5 不同证据状态题（2026-10-08）

[v5 cohort](../research/p30-evaluation-cohort-v5.json) 在提示 0.10 实现和远端 CI 完成后冻结，使用此前 P30 cohorts 未出现的 `repeat`、`identity-mismatch` 报告。每题的两个 gold 是按报告字段预先写入的代理标注，不是独立人工 gold。qwen3.5 清单摘要 `763e4656252877a6a39afe7cbeee75afa46c4c07e86ffecc56870606a3b164ee`，qwen3-vl 清单摘要 `31b26c62df09e9ec5ff3ad34b0110daf18b2e007c836a3b537157bfb1d439772`；归档留在本机 `output/p30-continuation-audit/trial-v5-*`。

qwen3.5 两题均未通过：一条 135.8 秒超时，另一条 70.6 秒输出被严格校验拒绝；两题各有 2/2 gold 进入上下文，但引用均为 0/2。qwen3-vl 对 repeat 用时 68.0 秒，引用 2/2 并通过结构化任务；对 identity-mismatch 用时 19.5 秒，输出符合 schema，但只引用 1/2 gold，任务未通过。所有四份完整调用归档均通过离线重放。通过只说明结构化与引用门满足；语言语义和可用性仍须独立 review。

一次 qwen3.5 初始调用仅产生事实预检文件，没有模型响应；该不完整目录保留但未计入配对。正式调用在独立重试目录完成。

2026-10-09，用户独立审阅 qwen3-vl 两条回答并确认其中报告状态内容均正确。特别是 identity-mismatch：模型正文准确写出两个 `unassessed` 状态，但结构化 `project_claims` 只含 stage status，所以人工内容核对通过、机器要求的引用完整性仍失败。该样本已看过，后续不能再视为盲测。

### 提示 0.11 开发回归（2026-10-09）

0.11 为整体/具名阶段状态设置两个必需的项目引用，并由运行时检查完整覆盖。使用 v5 已见问题做开发回归：qwen3-vl 的 identity-mismatch 现 2/2 引用通过（21.5 秒），repeat 因 `done_reason=length` 用满 4096 输出 token 而拒绝（71.4 秒）；qwen3.5 两题分别 104.3 秒、72.1 秒均 length 拒绝。全部四份归档离线复验通过。由于题目已用于提示开发，本结果不算 held-out 验收，回答语义仍需按新证据评估。

### 提示 0.11 配对复验 v6（2026-10-09）

冻结问题见 [v6 cohort](../research/p30-evaluation-cohort-v6.json)。两个报告此前未用于 0.11 调整，但早先出现在其他提示开发评测中，因此本轮是版本复验，不是从未见过的证据集。清单摘要：qwen3.5 `e18610adccdfb31598869e52920a35ff6b924d16555aa8f1e741b3b5a6114227`，qwen3-vl `f3b492c570346fd73636920987c0699b77a1b8bf70387811dc7b33c879ca746f`。qwen3-vl 两题各 2/2 gold 进入上下文并引用，耗时 66.7s/33.0s；qwen3.5 两题均被输出校验拒绝，耗时 102.4s/78.3s，引用 0/2。四份归档离线复验通过。原始归档位于本机 `output/p30-continuation-audit/trial-v6-qwenvl/` 与 `trial-v6-qwen35/`，未进入仓库。人工语义和可用性仍待审阅；机器结构通过不等同答案正确。

2026-10-10 用户已确认 v6 两条 qwen3-vl 状态回答文字准确且可用；范围只限这两题。

### 提示 0.12 qwen3.5 输出恢复（2026-10-10）

对 v6 qwen3.5 原始响应的诊断显示：两题 `done_reason=length`、`eval_count=4096`、正文为空，thinking 分别约 16.6K/16.8K 字符。0.12 只对 identity family=`qwen35` 关闭 thinking，保留所有旧提示 payload 的重放语义。以相同 cohort 重冻后的清单摘要为 `5eb332c0834a27103b2391010d76c36e40ef8305c2d0275fc7a7ffc6b6081801`；两题均 stop、2/2 引用通过，适配耗时 32.3s/19.8s，离线复验通过。该结果验收输出路径修复，不计为新的语义质量样本。

### 提示 0.16 精确字段开发集 v7（2026-10-10）

[v7 cohort](../research/p30-evaluation-cohort-v7.json) 含三个报告、每题四个 `runtime.signal-tx/rx` status/reason gold。它最初在查看结果前冻结，但随后直接驱动 0.13–0.16 修正，因此最终只能作为开发回归。0.16 清单摘要 `ef165dc67f2a8dc441e64f974f24bf9f6240e0644ad30c56bb94f1ac93f4e497`；qwen3.5 在 project/retrieval 共 6/6 通过，四项事实均由确定性选择器完整绑定，真实归档均通过离线复验。`cited_required_facts=4` 表示最终结果绑定覆盖，不表示模型自行选择了四项引用。

检索模式对这类“复述报告中精确字段”的问题记录 `KNOWLEDGE_NOT_APPLICABLE`，不查询手册。六份草稿经开发者逐项审读均完整复述目标值；该题集已见且没有独立审阅者，语义契约仍保持 unassessed。下一组必须使用未参与本轮实现的复杂解释/资料适用性问题，并在看模型答案前写下人工预期。

### 提示 0.17–0.22 与 v8/v9（2026-10-10）

[v8 cohort](../research/p30-evaluation-cohort-v8.json) 在首次推理前冻结，但随后用于 0.17–0.21 的复杂事实选择、草稿契约和资料适用性边界开发，因此只算开发回归。0.21 最终六次调用均满足目标机器边界；这不能作为未见质量分数。

0.22 只进一步缩小资料题实际模型输入：删除 `project_status`，项目 facts 为空；检索模式仍保存来源，但在独立适用性审核前不得形成 manual claim。实现固定后冻结 [v9 cohort](../research/p30-evaluation-cohort-v9.json)，清单摘要 `0fa1fec40c8a189db8683a89da0889d6fb037f545181b5315923a1efc960f701`，并在查看结果后停止调整该版本。

v9 的三题在 project/retrieval 两模式共六次：任务引用解释 0/2（定义路径少了开头 `/`，触发字面锚点拒绝）；资料适用性 2/2 被适配器接受为 `unassessed`、零 project/manual claims；unsupported-field 解释 0/2（中文弯引号导致 JSON 解析失败）。所有归档离线复验通过。逐字复核显示两份被接受的资料草稿长度为 175/259，超过请求 schema 的 160；project 模式还使用了可能误示已执行检索的措辞。检索模式提到的 AUTOSAR Blockset User Guide R2024a、Start Page、Component Mapping 和诊断服务均存在于实际三个输入片段，且没有生成标准强制结论，但这不足以抵消格式与模式措辞偏差。评分必须同时报告 2/6 适配器接受、4/6 fail closed、0/6 内容验收；v9 不得再用于 0.22 调参，后续修正必须升级提示并使用新 cohort。
