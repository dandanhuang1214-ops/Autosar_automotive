# P5a 本地 Evidence Bundle Manifest 调研

## 动机

P4 已能一次生成静态校验、virtual CAN runtime 和组合通信证据，但交付目录仍只是文件集合。单份报告中的 SHA-256 可以绑定直接来源，却不能回答目录包含哪些文件、每个文件是什么类型，以及报告依赖 bundle 内哪个 artifact。

## 契约

`evidence-bundle-manifest-0.1` 使用 bundle 内 POSIX 相对路径作为 artifact ID，逐文件记录 media type、artifact type、schema version、字节数和 SHA-256。producer 是创建该 bundle 的显式调用方声明，不从文件名或 backend 猜测。

JSON 文件可以通过 `source_artifacts` 声明依赖。索引器将依赖分类为：

- `artifact`：来源位于同一 bundle，引用相对 artifact ID；
- `external`：来源位于调用方指定的 portable base，引用相对 base 的路径。

两类依赖都必须存在且实际 SHA-256 与报告声明一致，否则不生成 manifest。manifest 本身必须位于 bundle 外，避免把清单加入自身哈希集合。

## 安全与可移植边界

索引器拒绝符号链接、特殊文件、空 bundle、非对象 JSON、非法结构化依赖、哈希不符和逃出 portable base 的外部路径。manifest 不保存 bundle 或 base 的绝对路径，不复制输入，不执行报告内容，不访问网络。

P5a 只证明“生成清单时读取到的字节与显式依赖一致”。

## P5b 事后完整性验证

`verify-evidence` 先使用代码内闭合 loader 校验 manifest 的顶层、artifact 和 dependency 字段，要求 artifact identity/path 排序且唯一、汇总计数一致、内部依赖指向已登记 artifact 且哈希相同。manifest 结构错误是输入契约错误，CLI 返回 1，不生成看似正式的 verification result。

合法 manifest 对应的 bundle 状态变化则生成 `evidence-bundle-verification-0.1`：

- `EVIDENCE-FILE-MISSING` / `EVIDENCE-FILE-UNEXPECTED`；
- `EVIDENCE-SIZE-MISMATCH` / `EVIDENCE-SHA256-MISMATCH`；
- `EVIDENCE-SYMLINK-DETECTED` / `EVIDENCE-SPECIAL-FILE-DETECTED`；
- 内部依赖未验证以及外部依赖 missing/unsafe/SHA mismatch。

结果固定 manifest SHA-256，分别统计 artifact 和 dependency 验证数。存在任一 Finding 时状态为 `failed`，CLI 返回 2；JSON/Markdown 仍会物化，供 CI 留存失败证据。

## P5c 跨平台受控篡改演练

CI 先验证原 bundle，再复制 bundle 并只向 `runtime/can-runtime-report.json` 追加一个换行。真实 `verify-evidence` step 使用 `continue-on-error` 让后续检查和上传得以执行；检查器要求 step outcome 为 failure、verification 为 closed failed result，且固定路径存在 `EVIDENCE-SIZE-MISMATCH`。CLI 若意外成功或 Finding 不符，检查步骤会使 job 失败。

正常验证和拒绝验证使用独立目录与 artifact 名称。演练不修改 checked-in 文件或原始通信 bundle，也不把本地 SHA-256 描述成签名、attestation 或 producer 身份认证。
