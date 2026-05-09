---
kind: operation
---

# Core Dump 分析

> 触发: 节点崩溃后需要分析 core 文件、core 未生成需要开启、需要 gdb 分析堆栈

## core 文件定位

- 查看 core 输出配置：`cat /proc/sys/kernel/core_pattern`
- 检查 core 是否开启：`ulimit -c`（0 = 未开启，unlimited = 已开启）
- 常见搜索：`find / -maxdepth 4 -type f \( -name "core" -o -name "core.*" \) 2>/dev/null`
- 筛选条件：时间匹配宕机窗口 + 进程为 dolphindb + 主机一致

## core 未生成的常见原因

- `ulimit -c` 为 0（未开启）
- 目标目录不可写或磁盘满
- `kill -9`（SIGKILL）/ `kill -15`（SIGTERM）不产生 core
- Ubuntu 被 `apport` 接管（关闭：`systemctl disable apport`）
- Ubuntu `systemd-oomd` 杀进程（检查：`journalctl -u systemd-oomd`）

## 开启 core dump

```bash
# 临时开启
ulimit -c unlimited

# 设置路径与命名
echo "/data/coredump/core-%e-%p-%t" > /proc/sys/kernel/core_pattern
# %e=程序名 %p=pid %t=时间戳

# 永久生效：/etc/security/limits.conf
# <user> soft core unlimited
# <user> hard core unlimited
```

> 集群中 datanode 由 agent 拉起，开启 core 后需重启 agent 再重启 datanode。

## gdb 分析

```bash
# 基础命令
gdb /path/to/dolphindb /path/to/core

# 一键提取关键信息
gdb /path/to/dolphindb /path/to/core \
  -ex "set pagination off" \
  -ex "info threads" \
  -ex "thread apply all bt full" \
  -ex "frame 0" \
  -ex "info locals" \
  -ex "quit"
```

## 信号类型速查

| Signal | 编号 | 含义 | 常见原因 |
|--------|------|------|----------|
| SIGSEGV | 11 | 段错误 | 空指针、内存越界、野指针 |
| SIGABRT | 6 | 中止 | 断言失败、bad_alloc、主动 abort |
| SIGILL | 4 | 非法指令 | CPU 指令集不兼容（AVX） |
| SIGFPE | 8 | 浮点异常 | 除零 |
| SIGPIPE | 13 | 管道破裂 | 旧版本可能退出，新版本已忽略 |
| SIGKILL | 9 | 强制终止 | kill -9 / OOM killer（不生成 core） |
| SIGTERM | 15 | 终止请求 | 正常关闭（不生成 core） |

## 堆栈归因模式

| 堆栈特征 | 初步归因 | 置信度 |
|----------|----------|--------|
| SIGSEGV + 地址接近 0x0 | 空指针解引用 | 高 |
| SIGSEGV + 随机/已释放地址 | 野指针或内存破坏 | 中 |
| SIGABRT + assert/abort | 断言触发 | 高 |
| 重复递归帧 | 栈溢出 | 高 |
| malloc/free/new/delete 相关 | 堆损坏（越界/UAF/双重释放） | 中 |
| pthread_cond_wait 相关 | 并发问题（内存表并发写等） | 中 |
| sha1_block_data_order_shaext | OpenSSL 并发 bug（升级 2.00.11+） | 高 |
| UserDefinedFunctionView::Call | submitJobEx2 递归嵌套 | 高 |
