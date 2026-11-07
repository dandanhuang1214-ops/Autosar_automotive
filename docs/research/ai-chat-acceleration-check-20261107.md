# AI 平台本机模型加速核查（2026-11-07）

目标：在 RTX 3050 Ti Laptop 4096 MiB 与现有 Ollama `0.31.1` 容器上，判断不改变工程证据来源和平台默认模型时，哪些措施值得进入下一轮实现。基线见[前一轮质量与速度实测](ai-chat-graph-quality-review-20261106.md)。

## 实测

| 配置 | 驻留 | 显存 | 速度与结果 |
|---|---|---:|---|
| `qwen3.5:4b`，8192 context | 74% GPU / 26% CPU | 3124 MiB 峰值 | 同题热态首字 1.17 秒、全答 6.05 秒、15.8 token/秒；固定三题非盲严格有据 2/3 |
| `qwen3.5:4b`，4096 context，原提示 | 78% GPU / 22% CPU | 3160 MiB 加载后 | 热态首字 1.40 秒、全答 5.50 秒、17.8 token/秒；单次输出 73 token，不能凭此判定稳定提速 |
| `qwen3:4b-instruct-2507-q4_K_M`，8192 context | 后续预加载于 4096 context 时为 73% GPU / 27% CPU | 三题试跑峰值 2288 MiB；4096 预加载后 2336 MiB | 三题流式输出 12.6–14.4 token/秒；后两题首字 3.96 / 2.57 秒。目标片段与编号均 3/3；Codex 非盲审阅三题内容均由引用片段直接支持 |

新候选是[官方 2.5 GB Q4 纯文本模型](https://ollama.com/library/qwen3/tags)，摘要 `0edcdef34593`，仅下载至现有 Ollama 模型卷。其[原模型卡](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)注明只支持非思考模式。真实试跑复用[固定三题](ai-chat-graph-quality-cohort-20261106.json)与站点 v5 已验证本地快照；原始 trace 和审阅包仅在本机忽略目录 `output/ai-chat-qwen3-4b-20261107/`。`ollama ps` 的 4096 context 驻留检查发生在单独空请求预加载后，不把它与 8192 试跑的显存峰值误当同一配置。下载文件大小、运行时驻留大小和显存占用是不同量；文件变小并未使模型完整驻留 GPU，也未带来明确速度优势。候选质量样本仅三题、非盲，不是独立人工验收。

## 资料核对与建议

1. 保持 `qwen3.5:2b` 为普通聊天默认。前轮同题热态首字 0.82 秒、全答 1.66 秒、70.1 token/秒；其工程图谱整段严格有据仅 0/3，因此工程事实继续显示可核对来源，不能把快速回答当已验证结论。
2. 优先改善冷启动体感：当前请求 `keep_alive="2m"`，可在连续聊天场景试 5–10 分钟或启动时预热。Ollama [FAQ](https://github.com/ollama/ollama/blob/main/docs/faq.mdx)说明 `keep_alive` 和预加载的行为；延长驻留会占用显存，**不会提高热态 token/秒**。
3. 图谱问答按题裁剪候选片段与历史长度，并逐项复验召回和无依据扩写；`num_predict=2048` 只是上限，缩小它只能限制过长回答，不能直接加快正常短回答。当前 8192→4096 context 的一次试验仍有 CPU 卸载，故不建议仅以此全局切换。[Ollama 上下文说明](https://github.com/ollama/ollama/blob/main/docs/context-length.mdx)指出上下文增大会增加内存，建议用 `ollama ps` 核对 CPU 卸载。
4. 若继续追求本机 4b，可在隔离容器配置下对照 Flash Attention 与 `q8_0` KV cache，再看 `ollama ps`、token/秒及新留出题内容。Ollama [FAQ](https://github.com/ollama/ollama/blob/main/docs/faq.mdx)说明 q8 KV 约用 f16 一半缓存内存，但这只作用于 KV cache，不保证 4b 完整上卡；该设置为服务全局选项，需受控重启和质量复验。
5. 若要求 4b 级别回答同时明显缩短生成时间，当前 4 GB 显存和部分 CPU 卸载是主要结构限制；更大显存的本机 GPU 或远端推理比继续盲调 `num_ctx` 更值得评估。该建议是根据本机试验和 Ollama 的[卸载说明](https://github.com/ollama/ollama/blob/main/docs/context-length.mdx)作出的推断，不承诺特定硬件的速度。

本轮没有修改平台代码、模型默认值或现有容器配置；仅下载候选模型文件并完成只读试跑，试跑后已卸载驻留模型。下一实现门仍是收紧无依据扩写，并用新留出题及独立人工审阅验证内容质量。
