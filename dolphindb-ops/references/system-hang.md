---
kind: category
---

# 系统卡死 / 无响应诊断

> 触发: 集群卡住、接口无响应、页面卡死、查询/写入挂起、任务无法取消

## 规则

### 资源瓶颈（非死锁）
条件: CPU/IO/内存指标异常高
处置: 识别大任务 → 取消大任务，如果运行的任务和排队的任务过多，则批量取消
根因: 查询/写入任务资源消耗超预期；分区设计不合理；一次性提交过多消耗资源的任务

### 作业队列堵塞
条件: 大量作业排队等待，系统响应缓慢但资源未打满
处置:
1. 查看同步作业队列
2. 查看批处理作业队列
3. 查看队列深度统计
4. 识别并取消异常的长时间运行作业
5. 检查 worker 线程数配置（workerNum、webWorkerNum、maxBatchJobWorker）
根因: worker 线程数不足；存在长时间运行的作业阻塞队列；大量并发作业提交

### Recovery 占用 Worker 卡住
条件: 关键错误日志出现 `Version Conflict` 持续重试
处置: 暂停 recovery → 删除异常分区 → 重启节点 → 恢复 recovery；查看是否有未完成的 recovery 任务

### TSDB LevelFileIndexCache 饱和
条件: 关键错误日志出现 `LevelFileIndexCacheInvalidPercent` 高占比
处置: 调大 `TSDBLevelFileIndexCacheSize`（翻倍起步）→ 重启数据节点
根因: 大时间窗口查询导致缓存置换跟不上

### Web 页面卡在 getClusterPerf
条件: cluster_perf 超时 + 仅 leader controller 页面可用
处置: 提升 controller `workerNum`（2→4）或调大 `maxConnectionPerSite`（10x）→ 重启
根因: RPC 连接争用形成逻辑死锁

### 网络分区导致连接卡住
条件: 关键错误日志出现 `timeout` / `refused` + 节点间网络不通
处置: 排查防火墙规则和网络策略变更；各节点间 IP:端口互通测试

### 工作线程全部阻塞（极端卡死）
条件: 所有操作无响应 + 采集线程栈显示全部 worker 阻塞
处置: 使用 `-attach` 紧急通道（2.00.16+ / 3.00.3+）执行清除缓存或取消作业操作
命令: `./dolphindb -attach 1 -target-pid <PID>`
要求: 使用与目标进程相同的系统用户

### Worker 线程全部处于 D 状态
条件: 线程诊断显示大量线程处于 Disk Sleep (D) 状态
处置:
1. 查看线程堆栈和状态分布，确认 D 状态线程数量
2. 检查堆栈是否显示 IO 阻塞
3. 查看磁盘 IO 状态
4. 检查是否有磁盘故障或 IO 瓶颈
5. 如果是 NFS 或网络存储，检查网络连接
根因: 磁盘故障、IO 瓶颈、NFS 挂载点无响应

### 线程死锁
条件: 线程堆栈显示多个线程卡在 `__lll_lock_wait` 或 `_L_lock_`
处置:
1. 采集线程堆栈（建议采集 2 次，间隔 3-5 分钟）
2. 对比两次堆栈，确认是否真正死锁（堆栈不变）
3. 如果确认死锁，重启节点
4. 保存堆栈信息，联系 DolphinDB 技术支持
根因: 内部锁竞争导致死锁（通常是 bug）

## 线程诊断方法

### 综合线程信息查看（推荐）
一次性获取完整线程诊断信息：
- **完整堆栈**: 所有线程的调用栈（用于死锁、阻塞分析）
- **基础信息**: PID、总线程数
- **高负载线程**: 按 CPU 时间降序，只显示活跃线程（CPU > 0）
- **状态分布**: 智能显示，有异常状态（D/Z/T）时详细展示

**重点关注**：
- 堆栈中的 `__lll_lock_wait` / `_L_lock_`：锁等待，可能死锁
- 堆栈中的 `CountDownLatch::wait()`：线程阻塞
- D 状态（Disk Sleep）：不可中断睡眠，通常是 IO 阻塞
- 高 CPU 线程：可能是性能瓶颈

**采集建议**：
- 至少采集 2 次，间隔 3-5 分钟
- 对比栈变化判断是否真正死锁（堆栈完全不变则可能是死锁）

### 栈特征速查
- `__lll_lock_wait` / `_L_lock_` — 锁等待
- `CountDownLatch::wait()` 持续不变 — 线程阻塞
- `dfsSaveChunkRemote` + FirstWorker — Recovery 占用关键工作线程
- `getClusterPerf` — RPC 连接争用

## 验证
- 所有节点状态恢复为 running 且响应正常
- 无异常长耗时任务
- Web 页面可正常访问
- CPU / IO 等系统资源利用率正常

## 已知案例

### Recovery 占用 FirstWorker（低核环境）
- **触发**: 低核环境（2 核）重启后数据节点持续卡住
- **特征**: 日志 `Version Conflict` 持续重试 + 栈卡在 `dfsSaveChunkRemote`（FirstWorker）
- **修复**: kill -9 停节点 → 暂停 recovery → 删除异常分区 → 重启 → 恢复 recovery → 补写数据

### TSDB 大查询卡住 GUI
- **触发**: 查询大时间窗口（如 1 个月）TSDB 数据后 GUI 卡住
- **特征**: 日志 `TSDBLevelFileIndexCacheInvalidPercent` 高占比 + 查询 LevelFile 索引缓存状态显示缓存已满
- **修复**: 调大 TSDBLevelFileIndexCacheSize（翻倍起步）→ 重启所有数据节点

### Web 页面卡在 getClusterPerf
- **触发**: HA 集群仅 leader controller 页面可用，其他节点页面打不开
- **特征**: 栈卡在 `getClusterPerf` + controller `workerNum` 偏小（如 2）
- **修复**: 调大 `workerNum`（→4）或 `maxConnectionPerSite`（→10x）→ 重启集群
