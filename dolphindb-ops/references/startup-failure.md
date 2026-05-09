---
kind: category
---

# 节点启动失败诊断

> 触发: 节点启动后无法访问、Web 界面显示节点红色、启动过程异常关闭或卡住

## 背景知识

### 节点启动流程（7个阶段）

1. 初始化内部基础模块
2. 解析配置和 License
3. 初始化 Server，执行 dolphindb.dos，加载 preloadModules
4. 启动功能模块（权限、元数据、事务回滚、redo log 回放、RAFT）
5. 执行 startup.dos
6. 初始化定时任务
7. 执行 postStart.dos

**启动完成标志日志**: `Job scheduler initialization completed.`

### 问题分类

通过进程状态和日志错误判断：
- **启动异常关闭**: 进程不存在
- **启动异常卡住**: 进程存在，持续刷 ERROR 日志
- **启动慢**: 进程存在，无 ERROR 日志，但未完成启动

## 规则

### License 过期
条件: 日志出现 `The license has expired`
处置: 更新 license 文件；参考 `license-update`
根因: License 已过期，需联系销售获取新 license

### 端口冲突
条件: 日志出现 `Failed to bind the socket on port <port> with error code 98`
处置: 
1. 确认端口占用情况
2. 停止占用端口的程序或等待上次节点完全关闭
3. 重启节点
根因: 配置的端口被其他程序占用或上次关闭未完成

### Redo Log 文件损坏
条件: 日志出现 `The redo log for transaction [<tid>] comes across error: Failed to unmarshall data`
处置:
1. 确认具体错误的 tid
2. 人工备份并移走 `<redoLogDir>/head.log` 和 `<TSDBRedoLogDir>/head.log`
3. 重启节点
4. 启动后检查数据完整性
根因: 磁盘满、宕机或 bug 导致 redo log 损坏

### 函数视图或定时任务包含不存在的方法
条件: 日志出现 `Can't recognize function: <function_name>` 或 `Failed to unmarshall the job`
处置:
1. 在配置文件中添加 `preloadModules=plugins::<plugin_name>` 或 `preloadModules=<module_name>`
2. 重启节点
根因: 使用了未配置自动加载的插件/模块的方法

### 函数视图或定时任务包含不存在的共享表
条件: 日志出现 `Failed to recognize shared variable <var_name>` 或 `Failed to deserialize update statement`
处置:
1. 对于定时任务：在 startup.dos 中添加建表语句，重启节点
2. 对于函数视图（普通集群）：人工移除 `<HOME_DIR>/<NodeAlias>/sysmgmt/acl*.meta` 文件，重启节点，重新添加权限和函数视图
3. 对于函数视图（高可用集群）：参考官方文档处理 RAFT 元数据
根因: 定时任务或函数视图中使用了未创建的共享表

### 定时任务文件损坏
条件: 日志出现 `Failed to unmarshall the job [<job_name>]` 且文件格式错误
处置:
1. 人工备份并移走 `<sysmgmt_path>/job*.meta` 文件
2. 重启节点
3. 启动后重新提交所有定时任务
根因: 磁盘满、宕机或 bug 导致定时任务文件损坏

### 权限与函数视图文件损坏
条件: 日志出现 `Failed to deserialize sql query object` 或 `CodeUnmarshall` 反序列化失败
处置:
1. 人工备份并移走 `<HOME_DIR>/<NodeAlias>/sysmgmt/acl*.meta` 文件
2. 重启节点
3. 启动后重新添加所有权限和函数视图
根因: 磁盘满、宕机或 bug 导致权限文件损坏

### RAFT 文件损坏
条件: 日志出现 `[Raft] incomplete hardstate file` 或 `failed to initialize with exception`
处置:
1. 确保已有另一个节点成为 RAFT 集群 leader
2. 人工备份并移走 `<dfsMetaDir>` 和 `<HOME_DIR>/<NodeAlias>/raft` 目录
3. 重启节点（会自动同步 leader 元数据）
根因: 磁盘满、宕机或 bug 导致 RAFT 文件损坏

### 集群间网络不通
条件: Web 管理界面白屏，或日志出现 `Connection timed out` 或 `IO error type 1`
处置:
1. 检查网络连接状态
2. 检查集群节点状态
3. 联系运维调通网络
根因: 集群间各节点 IP:端口号不通

### RSA 密钥校验文件损坏
条件: 日志出现 `Failed to decrypt the message by RSA public key`
处置:
1. 人工删除所有控制节点的 `<HOME_DIR>/<NodeAlias>/keys` 目录
2. 重启集群（会重新生成 RSA 密钥）
3. 重新提交所有定时任务
根因: 磁盘满、宕机或 bug 导致 RSA 密钥文件损坏

### 正在回滚事务（启动慢）
条件: 日志有 `Will process pending transactions.` 但没有 `ChunkMgmt initialization completed.`
处置:
1. 检查事务状态
2. **建议等待事务回滚完成**（跳过会导致数据不一致）
3. 若必须跳过：人工移走 `<chunkMetaDir>/LOG` 和 `<volumes>/LOG` 目录，重启节点，启动后检查数据完整性
根因: 节点宕机时有未完成的写入事务

### 正在回放 Redo Log（启动慢）
条件: 日志有 `Start recovering from redo log` 但没有 `Completed CacheEngine GC and RedoLog GC`，持续刷 `applyTidRedoLog` 日志
处置:
1. 查看回放进度
2. **建议等待 redo log 回放完成**（跳过会导致数据不一致）
3. 若必须跳过：人工移走 `<redoLogDir>/head.log` 和 `<TSDBRedoLogDir>/head.log`，重启节点，启动后检查数据完整性
根因: 节点宕机时有已提交但未完成的事务需要回放

### 启动脚本运行慢或失败
条件: 日志显示 `Executing the startup script` 后长时间无 `execution completed` 或有脚本错误
处置:
1. 查看脚本错误详情
2. 检查集群分区状态是否完成初始化
3. 修正 startup.dos 或 postStart.dos 中的错误
4. 避免在启动脚本中访问分布式库表或执行耗时操作
根因: 启动脚本执行时分布式数据库可能未初始化完毕

### 配置文件错误
条件: 日志出现配置项相关错误或参数校验失败
处置:
1. 检查配置文件语法和参数值
2. 修正配置后重启节点
根因: 配置文件格式错误或参数值不合法

## 验证
- 确认进程状态正常
- 确认端口监听正常
- 确认无新的启动错误
- 确认节点状态为 running
- 确认副本恢复进度正常

## 重要日志关键字

| 阶段               | 开始日志                             | 完成日志                                    |
| ------------------ | ------------------------------------ | ------------------------------------------- |
| 用户权限初始化     | `Initializing AclManager`            | `Initialization of AclManager is completed` |
| 控制节点元数据     | -                                    | `Controller initialization completed.`      |
| 数据节点元数据     | -                                    | `ChunkMgmt initialization completed.`       |
| TSDB 元数据        | -                                    | `Restore TSDB meta successfuly.`            |
| Redo log 回放      | `Start recovering from redo log`     | `Completed CacheEngine GC and RedoLog GC`   |
| RAFT 初始化        | `DFSMaster ElectionTick is set`      | `DFSRaftReplayWorker started`               |
| 执行 startup.dos   | `Executing the startup script`       | `execution completed.`                      |
| 定时任务初始化     | `Job scheduler start to initialize.` | `Job scheduler initialization completed.`   |
| 执行 postStart.dos | `Executing the post start script`    | `execution completed.`                      |

## 相关配置项

| 配置项                 | 说明                   | 默认值                     |
| ---------------------- | ---------------------- | -------------------------- |
| `logFile`              | 节点运行日志路径       | `dolphindb.log`            |
| `dfsMetaDir`           | DFS 元数据目录         | `<HOME_DIR>/dfsMeta`       |
| `chunkMetaDir`         | 本地分区元数据目录     | `<HOME_DIR>/storage`       |
| `volumes`              | 数据卷路径             | `<HOME_DIR>/storage`       |
| `redoLogDir`           | OLAP redo log 目录     | `<HOME_DIR>/redoLog`       |
| `TSDBRedoLogDir`       | TSDB redo log 目录     | `<HOME_DIR>/TSDBRedoLog`   |
| `recoverLogDir`        | 恢复事务 redo log 目录 | `<HOME_DIR>/recoverLog`    |
| `preloadModules`       | 预加载的插件和模块     | -                          |
| `startup`              | 启动脚本路径           | `<HOME_DIR>/startup.dos`   |
| `postStart`            | 后启动脚本路径         | `<HOME_DIR>/postStart.dos` |
| `dfsReplicationFactor` | 副本数                 | `2`                        |

## 参考资料

- [DolphinDB 官方文档 - 节点启动流程简析与常见问题](https://docs.dolphindb.cn/zh/tutorials/node_startup_process_and_questions.html)
