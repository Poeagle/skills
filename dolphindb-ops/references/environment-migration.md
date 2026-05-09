---
kind: operation
---

# 环境迁移操作指南

> 触发: 集群机器迁移、元数据目录迁移、Redo Log 迁移、普通集群转高可用

## 规则

### 集群机器迁移
条件: 替换集群中一台或多台机器，保留现有数据
处置:
1. 停止所有任务，流表先持久化，共享内存表先保存；每台机器执行 `stopAllNode.sh`（无法退出优先 `kill -15`）
2. 更新 `controller.cfg`、`agent.cfg`、`cluster.nodes`（异步复制从集群也需同步更新）
3. 启动顺序：`startController.sh` → `startAgent.sh` → Web 控制台启动数据节点
4. 高可用额外步骤：controller shell 执行 `saveClusterNodes`，按实际 IP/端口/角色替换 sites
根因: 新机器与集群网络需互通；所有文件目录保持不变（绝对路径一致）；若路径无法一致改走 backup + restore 重部署

### 元数据目录迁移
条件: 调整 `dfsMeta/chunkMeta` 到新磁盘/路径
处置: 安全关机 → 拷贝 `dfsMeta/chunkMeta` 到新目录 → 修改配置文件路径 → 开机验证

### Redo Log 目录迁移
条件: 调整 `redoLogDir/TSDBRedoLogDir` 到新磁盘/路径
处置: 刷新 OLAP 和 TSDB 缓存到磁盘 → 查看 Redo Log GC 状态 → 强制回收 Redo Log → 安全关机 → 拷贝 `redoDir` 及同级 `TSDBMeta` 到新目录 → 修改配置文件 → 开机验证。`TSDBMeta` 与 `TSDBRedoLogDir` 必须保持同级关系

### 普通集群转高可用集群（⚠️ 高风险）
条件: 将普通集群改造为高可用集群（≥ 2.00.12.8 / 2.00.13.5 / 3.00.1.4）
处置:
1. 控制节点备份用户/权限/函数视图
2. 关集群 → 配置 HA 控制节点（别名与元数据目录不与原控制节点冲突）
3. 启动后从数据节点恢复控制节点元数据 → 触发节点重新上报状态 → 触发 master checkpoint
4. 恢复 ACL/用户/权限
根因: 可能导致分区丢失/不一致/垃圾分区，不推荐在生产环境直接执行。保留原普通控制节点配置作为回滚预案

## 验证
- 节点状态正常
- 库表读写正常
- 异步复制链路正常（如适用）
- 元数据完整性、分区一致性、副本状态正确
