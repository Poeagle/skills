---
kind: category
---

# 节点崩溃诊断（Signal / Core 分析）

> 触发: 日志中出现 Received Signal、segfault、core dump、进程已确认消失且需要分析崩溃原因

## 规则

### Signal 11 — 段错误 (SIGSEGV)
条件: 宕机关键日志出现 `Received signal 11` 或内核日志出现 `segfault`
处置: 需收集 core dump 文件（`coredumpctl list` 或检查 core_pattern 路径），使用 `gdb dolphindb core.<pid>` 分析堆栈
根因: 空指针解引用、内存越界、并发写内存表、低版本 bug、插件崩溃

### Signal 6 — 中止 (SIGABRT)
条件: 宕机关键日志出现 `Received signal 6`
处置: 通常为断言失败或主动 abort；收集 core 分析触发路径
根因: 内部断言触发、内存分配失败（bad_alloc）、数据结构损坏

### Signal 4 — 非法指令 (SIGILL)
条件: 宕机关键日志出现 `Received signal 4`
处置: 检查 CPU 指令集兼容性（AVX/SSE 支持）
根因: 二进制与 CPU 指令集不匹配（如旧 CPU 不支持 AVX）

### Signal 13 — 管道破裂 (SIGPIPE)
条件: 宕机关键日志出现 `Received signal 13`
处置: 旧版本可能触发退出；升级到新版本（已忽略该信号）

### OOM Kill（非 Signal 崩溃）
条件: 内核日志出现 `Out of memory: Killed process` 或 `oom_kill_process`
处置: 参考 `oom`（内核强制终止进程，不产生 core dump）

### 系统主动退出
条件: 宕机关键日志出现 `MainServer shutdown` 且无异常信号
处置: 检查控制节点日志中 `has gone offline` 记录；排查是否人为执行 stopDataNode / kill
验证: 历史命令 `history | grep dolphindb`、`history | grep kill`

### 前台启动导致退出
条件: 进程退出但无 signal、无 core、无 ERROR；Controller/Agent 退出而 datanode 存活
处置: 检查启动方式是否为前台 `./dolphindb`（而非后台脚本）；系统日志 `grep "remove session" /var/log/messages`。改为标准启动脚本或 systemd 服务化启动

### License 过期
条件: 宕机关键日志出现 `invalid license`
处置: 更新 license 文件；1.30.11+ / 1.20.20+ 支持在线更新；低版本需重启

### 插件依赖缺失
条件: 宕机关键日志出现 `Can't recognize function` 或 `CodeUnmarshall` 反序列化失败
处置: 在节点配置中添加 `preloadModules=plugins::<插件名>`；确保 HA 集群所有控制节点配置一致
验证: 重启后人工在控制台检查函数视图恢复正常

### 磁盘满导致退出（非 Signal 崩溃）
条件: 磁盘空间使用率 >95% 且日志出现写入失败
处置: 清理空间后重启 ⚠️（日志/数据/core 写满磁盘导致进程自行退出）

### 进程在但无响应（非崩溃）
条件: DDB进程存在但 cluster_perf 显示 offline 或无法连接
处置: 非崩溃场景，参考 `system-hang` 排查死锁或资源耗尽

## 验证
- 确认节点状态已恢复为 running
- 检查副本恢复进度是否正常
- 重启后日志是否有新的异常
- 内核日志是否有新的 segfault / OOM 记录

## 已知案例

### 并发写内存表
- **触发**: 多线程并发写同一内存表
- **core 特征**: `pthread_cond_wait@@GLIBC_2.3.2`
- **修复**: 内存表写入改为串行化或单写者模型；改用流表/分区落盘

### HA 函数视图缺插件
- **触发**: `addFunctionView` 使用插件函数，但非主控制节点未预加载该插件
- **特征**: HA 集群控制节点切换/恢复时崩溃
- **修复**: 所有控制节点统一配置 `preloadModules=plugins::<plugin_name>`

### 启动反序列化失败
- **触发**: 节点重启时，函数视图/定时任务引用的插件函数未加载
- **日志**: `CodeUnmarshall ... Can't recognize function xxx::connect`
- **修复**: 配置 `preloadModules` 预加载对应插件模块

### OpenSSL 并发崩溃
- **触发**: 并发场景下加密/摘要路径崩溃
- **core 特征**: `sha1_block_data_order_shaext`
- **修复**: 升级到 2.00.11 或更高版本

### submitJobEx2 递归嵌套
- **触发**: `submitJobEx2` 中递归提交同类任务
- **core 特征**: `UserDefinedFunctionView::Call`
- **修复**: 改为显式拆分任务链路，避免递归自提交

### 低版本 select 崩溃
- **触发**: 特定 select 语句在低版本稳定触发崩溃
- **确认**: 同一 SQL 在高版本无问题
- **修复**: 升级版本；临时规避触发 SQL 写法

### AMD 插件异步持久化
- **触发**: AMD 插件订阅异步持久化流表（`asyncWrite=true`）
- **修复**: 将 `asyncWrite` 设置为 `false`（同步写入）
