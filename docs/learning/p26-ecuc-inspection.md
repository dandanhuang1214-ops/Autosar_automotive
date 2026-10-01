# P26：项目选择、引用范围与调度绑定

平台实现和个人掌握分别记录。先按[指南](../project/p26-ecuc-inspection-guide.md)运行合成工程，再独立解释以下问题：

1. DPA 的文件集合与 ECUC value collection 的模块集合为什么都需要读取？文件存在是否代表模块已被选中？
2. 为什么同名模块处于不同绝对路径时不能覆盖合并？路径重复与短名重复有何区别？
3. 为什么外部行为引用被标记 unassessed，而选定模块内不存在的对象可报 missing？
4. RTE event mapping 容器存在为什么仍不代表已经绑定 OsTask？绑定存在又为何不能证明周期正确？
5. 为什么 attention-required 的报告可以复验 passed？如何用来源文件和 XML 定位核对原值？

独立练习：在合成副本中分别删除任务引用、改成不存在任务、重复任务路径，记录三种发现和具体来源位置。移走原项目后复验快照。实际复跑、能否独立解释及剩余问题待操作者记录，不由代理自动填为掌握。

通信链练习：按[通信定位指南](../project/p26-ecuc-communication-guide.md)运行合成工程，独立沿 PacketA/PacketB 的 edge_ids 找到来源 XML。解释为什么 Tx 经过 Buffer/HTH，Rx 经过 HRH，以及两个不同 EcuC PDU 如何通过 PduR 连接。分别将硬件对象改为不存在路径、改为 Controller、改为外部路径，比较 missing/wrong-type/unassessed。再修改 CanObjectType，解释引用全部存在时为何仍可 partial。保留实际操作记录；平台自动通过不代表已独立掌握。
