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

P5a 只证明“生成清单时读取到的字节与显式依赖一致”。重新验证已有 manifest、检测之后发生的 missing/unexpected/tampered 文件和受控拒绝证据属于 P5b。
