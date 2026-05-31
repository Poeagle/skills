# DolphinDB Redo Log & dataSync 配置

发现于 2026-05-30 通过 DolphinDB 官方文档研究。

## 关键配置参数

| 参数 | 默认值 | 说明 | 作用域 |
|------|--------|------|--------|
| `dataSync` | **0** | 0=不强制刷盘，由OS决定；1=强制 fsync redo log+数据+元数据 | controller.cfg |
| `redoLogPurgeLimit` | **4 GB** | Redo Log 占用磁盘空间上限，超过后自动删除**已提交事务**的日志 | 单节点/数据节点 |
| `redoLogPurgeInterval` | **30 秒** | 每隔30秒扫描一次，清理已提交事务的 Redo Log | 单节点/数据节点 |
| `chunkCacheEngineMemSize` | **0 GB** | OLAP 引擎 Cache Engine 容量，0=不开启。开启后**必须** `dataSync=1` | 数据节点 |

## dataSync=0（默认）

- Cache Engine **不开启**（`chunkCacheEngineMemSize=0`）
- 无强制 fsync，写入到 OS page cache 后返回
- Redo Log 由 OS 自行刷盘
- 写入性能最高，宕机时可能丢数秒数据

## dataSync=1

- Cache Engine **开启**（OLAP + TSDB 各维护一个）
- 写入路径：数据 → Redo Log（fsync）+ Cache Engine（内存）→ 攒批写数据文件
- Redo Log、数据和元数据全部强制刷盘
- 每笔事务提交时 Redo Log fsync，保证持久性

## 依赖链

```
dataSync=1 → Cache Engine 开启 → Redo Log 机制启用
                    ↓
              chunkCacheEngineMemSize > 0 时必须 dataSync=1
```

## 引擎各自的 Redo Log 路径

| 引擎 | 默认路径 | 配置参数 |
|------|---------|---------|
| TSDB | `<HomeDir>/log/TSDBRedo` | `TSDBRedoLogDir` |
| OLAP | `<HomeDir>/log/redoLog` | `redoLogDir` |
| PKEY | `<HomeDir>/log/PKEYRedo` | `PKEYRedoLogDir` |

## 写入模型比较

| 模式 | 数据先写到 | 攒批机制 | fsync | 适合场景 |
|------|-----------|---------|-------|---------|
| dataSync=0 | 数据文件 | 无（直接写）| 无（OS决定）| 性能优先，能容忍少量丢数据 |
| dataSync=1 | Cache Engine（内存） | Cache Engine 攒批 | 每事务 fsync | 数据安全优先，时序数据批量写入 |

## 事务流程（dataSync=1）

```
① 协调者创建事务，申请 tid
② 协调者分发数据到数据节点
③ 各数据节点：数据 → Redo Log（fsync）+ Cache Engine（同时写入）
④ 协调者申请 cid → 第一阶段 COMMIT
⑤ 第二阶段 COMPLETE → 回收 Cache Engine 缓存 → 回收 Redo Log
```

崩溃时（dataSync=1）：Redo Log 已有 COMMIT 标记 → 重启回放（redo）→ 数据恢复。

来源：DolphinDB 官方文档 `db_distr_comp/cfg/function_configuration.html`, `db_distr_comp/db/transaction.html`
