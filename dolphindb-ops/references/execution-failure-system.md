---
kind: category
---

# 系统/配置/连接错误案例

> 触发: 权限报错、License 报错、配置参数报错、连接失败、Shell 调用报错、作业调度失败

## 规则

### No privilege to xxx
条件: 报错 `No privilege to run function xxx` / `Not granted to xxx`
根因: 当前用户缺少目标函数/表/DB 的执行/读写权限
处置: 管理员执行 `grant` 或 `groupGrant` 授权；确认角色和组权限继承关系

### 只读节点上执行写入
条件: 写入相关 privilege 或 read-only 报错
根因: 向 `computenode` 或只读 `datanode` 执行写入
处置: 确认写入目标为可写 datanode 或通过 controller 路由

### License 过期
条件: 报错 `License has expired` / 无法启动报 license 错误
根因: License 文件到期
处置: 更换新 License 文件到各节点 licenseDir 目录；重启或在线更新 License（2.00.10+）

### License 节点数或 CPU 核数超限
条件: 启动报节点或 CPU 数量超出限制
根因: 实际部署节点/核数超过 License 授权
处置: 核对 License 授权范围；裁减节点配置或升级 License

### 配置参数拼写/格式错误
条件: 报错 `Invalid configuration parameter` 或参数不生效
根因: cluster.cfg / controller.cfg 中参数名拼写错误或格式不正确
处置: 对照官方文档逐项核对参数名和值格式；查询运行时配置验证是否生效

### Connection refused / 连接超时
条件: 报错 `Connection refused` / `Connection timed out`
根因: 目标节点未启动、端口未监听、防火墙拦截
处置: 检查节点进程 (`ps aux | grep dolphindb`) → 检查端口 (`ss -tlnp`) → 检查防火墙规则

### 节点间通信失败 (Controller / Agent)
条件: Agent/Datanode 无法注册到 Controller
根因: controllerSite 配置错误、网络不通、端口未开放
处置: 检查各节点配置中 controllerSite 一致性；ping / telnet 验证网络连通；检查端口占用

### Too many open files
条件: 报错 `Too many open files`
根因: 系统 ulimit 文件描述符限制过低
处置: `ulimit -n 1048576` 或修改 `/etc/security/limits.conf`；重启 DolphinDB 进程

### shell() 调用失败
条件: shell 函数返回空或报错
根因: 未启用 enableShellFunction=true；或命令本身返回非零退出码
处置: 确认 dolphindb.cfg 或 cluster.cfg 中 enableShellFunction=true；单独在 OS 终端验证命令正确性

### 后台进程被 OOM Killer 杀死
条件: 进程消失，`dmesg` 中出现 `oom-kill`
根因: 系统内存不足，DolphinDB 进程被内核 OOM Killer 终止
处置: 调大 maxMemSize 限制预留内存；或增加系统内存/swap；检查是否有内存泄漏

### scheduleJob 不执行
条件: 定时任务未按预期触发
根因: 时间格式错误、任务已过期、节点重启后任务丢失
处置: 查看定时作业列表确认任务状态；核对时间参数格式；确认持久化配置

### submitJob 异常堆积
条件: 查看最近作业显示大量失败或排队任务
根因: 并发提交过多、worker 线程被阻塞
处置: 检查 workerNum / localExecutors 配置；清理异常任务；调整提交频率

### cancelJob 无效
条件: 取消作业后任务仍在运行
根因: 任务处于不可中断状态（如长时间磁盘 IO）
处置: 等待当前 IO 操作完成；极端情况下可能需要 kill -9 重启节点

## 验证
- 重新执行报错操作确认成功
- 检查节点连接和权限状态
- 确认调度任务正常运行
