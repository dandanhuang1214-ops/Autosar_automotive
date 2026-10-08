# P30 基于项目证据的本地模型解释（implementing）

P29 的配置、CAN 与独立诊断结果提供确定性事实。下一项能力是用自然语言说明这些结果、定位依据，并连接已审核的技术资料。现有本地知识助手承担资料检索和交互；汽车工作台保留检查、执行和接受判定。

## 最小交付

1. 固定只读解释请求：一个已复验项目报告、问题、允许引用的事实与来源。不直接向模型发送整个 ECUC 工程。
2. 适配现有本地 Ollama 服务，冻结模型身份、提示版本、输入摘要和原始输出；原确定性审查可独立运行，服务不可用时返回明确结果。
3. 分开项目事实与手册知识。无效引用和缺证据结论不得自动补成有效编号；事实支持不足时保留未验证。模型生成的检查建议不是已执行结果。
4. 采用结构化回答并校验来源、对象身份、数值、状态和严重度；模型不能覆盖 passed/failed/blocked/unassessed，也不具有配置写入或总线发送能力。
5. 用开发问题与独立验收问题分别评测确定性回答、检索增强和模型解释；记录事实正确性、引用支持、拒答、延迟及人工可用性。原 P24 冻结评测仅作为历史回归，不用于调参。
6. 至少覆盖配置拒绝、影响范围、CAN 超时、诊断负响应、缺证据、历史运行替换；完成安装、服务缺失和 Windows/Linux 路径验证。

## 进入条件与边界

P29 当前诊断关联验收结束后，P30 成为唯一主实现阶段。模型接入首先是小范围解释能力，不扩展自主执行、自动改配置或自动操控硬件。硬件台架按实际取得设备后的驱动/供电/固件记录单列条件验收；未购置设备不能算作物理 ECU 能力。

现有知识助手的引用后处理会修补缺失/非法编号，接入工程事实路径前必须解决，不能以编号存在代替事实受支持。小模型是否适用由固定任务评测决定，不以模型参数量、资料数量或界面完成度代替验收。

## 首轮事实门

[只读事实门指南](p30-fact-gate-guide.md)提供项目 0.6–0.9 的复验事实导出、严格结构化引用校验、安装与搬移验证。首轮由实现 `a82ee62` / [run `37183484781`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37183484781) 七 job success 完成远端验收，见[P30 验收表](p30-acceptance.md)。它只验证精确事实选取，模型和自由文本解释尚未接入。下一项是现有知识助手/Ollama 适配及服务缺失回退，随后按本计划完成独立问题验收。


## 模型适配与复用盘点

本轮实现[本地模型适配](p30-model-adapter-guide.md)及[现有 LLM / Docker 复用盘点](p30-reuse-inventory.md)：直接消费原知识助手原文检索和现有 Ollama；保存版本、输入、原始响应、来源、延迟和明确缺口。服务不可用、输出非法或截断时保留确定性回退，已有事实门不变。模型自然语言仍为未验证草稿。

六类冻结评测现已执行，工具由 `8735bc3` / run `37419810449` 七 job success 验收；10 次真实配对推理均未通过结构化引用门。下一项仍为 P30：版本化修正问题相关事实选择，优先纳入失败原因、精确影响对象与必要上下文；保留提示 0.1–0.4 的历史重放。随后针对结构化值、原文摘录和 unassessed 空引用约束改进输出，在新冻结问题上验收。当前六题已见，不再冒充后续未见测试；人工语义/资料适用性仍待验收。原服务已恢复，具体现场结果与磁盘影响另列于本轮验收记录。


## 当前实施补充（2026-10-08）

提示 0.5 远端实现验收通过（`c60d8af` / run `37646726266` 七 job success）。真实 qwen3.5 新冻结评测 12 次无结构化成功；qwen3-vl 的同题对照未完成。P30 当前缺口为小模型延迟/回答质量和独立人工语义/资料适用性，不据此宣称 XML 或图像工程分析能力，也不先做微调。下一项是在 120 秒适配器边界内补足有效模型对照，完成独立人工语义/资料适用性验收。见[模型适用性评估](p30-model-suitability.md)。


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
