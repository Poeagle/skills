---
kind: operation
---

# 平台管理 API 操作规范

> 加载本文档后，Agent 被允许通过 `callApi` 执行需要特殊权限的管理操作。
> **请严格遵守以下规范，每个危险操作必须在执行前告知用户风险并请求确认。**

## 操作分级

| 等级 | 说明 | 确认要求 |
|------|------|----------|
| 🟢 安全 | GET 只读查询 | 无需确认，直接执行 |
| 🟡 一般变更 | POST 创建资源、PUT/PATCH 更新配置 | 简要告知 |
| 🔴 危险 | 停止/删除/升级/还原 | **必须等待用户明确确认** |

## 🔴 危险操作详细规范

### 节点启停

| 操作 | 路径 | 风险 |
|------|------|------|
| 停止节点 | `POST /api/v1/instances/{cluster_name}/nodes/{node_name}/stop` | 运行中的查询/写入中断 |
| 启动节点 | `POST /api/v1/instances/{cluster_name}/nodes/{node_name}/start` | 低（需确认服务器可达） |

请求体格式：
```json
// 启动节点
{"timeout": 60}  // timeout: 超时秒数，默认 60，可传 {}

// 停止节点
{"timeout": 30, "force": false}  // force: 是否强制停止，默认 false，可传 {}
```

响应格式：
```json
{"success": true, "message": "Node start operation initiated", "operation_id": "uuid"}
```

操作状态轮询：`GET /api/v1/instances/operations/{operation_id}`

前置检查：确认节点当前状态、是否有运行中的任务、是否为 controller。

### 集群删除

- 路径: `DELETE /api/v1/clusters/{cluster_name}`
- 请求体: 无
- 风险: **极高** — 删除集群配置，不可逆
- 前置检查: 确认所有节点已停止
- 响应: `{"success": true, "message": "...", "data": null}`

### 集群升级

- 路径: `POST /api/v1/clusters/{cluster_name}/upgrade`
- 风险: **极高** — 节点停机 + 二进制替换
- 前置检查: 目标版本包已上传、已备份元数据
- 预览: `GET /api/v1/clusters/{cluster_name}/upgrade/preview?server_package_filename=<文件名>`

请求体：
```json
{
  "cluster_name": "集群名",
  "server_package_filename": "DolphinDB_Linux64_V3.00.2.zip",  // 必填
  "plugin_package_filenames": ["plugin1.zip"],  // 可选
  "restore_backup_id": null,  // 可选：回滚到某个备份
  "confirm_upgrade": true  // 必须为 true 才执行
}
```

响应: `{"upgrade_id": "uuid", "status": "pending|running|completed|failed", "message": "..."}`

### 元数据还原

- 路径: `POST /api/v1/metadata/restore/{cluster_name}`
- 风险: **极高** — 覆盖当前元数据
- 前置检查: 所有节点已停止
- 参数通过 query string 传递（不是 JSON body）

```
POST /api/v1/metadata/restore/{cluster_name}?backup_user_id=1&backup_timestamp=20260420_120000
```

响应: `{"restore_id": "uuid", "status": "pending|running|completed|failed", "message": "..."}`

### 插件备份与还原

| 操作 | 路径 |
|------|------|
| 备份 | `POST /api/v1/plugins/backup/{cluster_name}` |
| 还原 | `POST /api/v1/plugins/restore/{cluster_name}?backup_user_id=N&backup_timestamp=TS` |
| 备份进度 | `GET /api/v1/plugins/backup/{backup_id}/progress` |
| 还原进度 | `GET /api/v1/plugins/restore/{restore_id}/progress` |

备份请求体：
```json
{"selected_plugins": ["plugin1", "plugin2"]}  // 可选，null=全量备份，可传 {}
```

### 服务器/用户/资源删除

- `DELETE /api/v1/servers/{server_name}` — 删除服务器（无请求体）
- `DELETE /api/v1/users/{user_id}` — 删除用户（不可逆，无请求体）
- `DELETE /api/v1/packages/server/{filename}` — 删除 Server 安装包
- `DELETE /api/v1/packages/plugin/{filename}` — 删除插件包

## 常用查询端点

| 用途 | 路径 | 说明 |
|------|------|------|
| 集群列表 | `GET /api/v1/clusters` | 返回所有集群配置 |
| 节点状态 | `GET /api/v1/instances/{cluster_name}/nodes` | 返回节点在线状态 |
| 操作状态 | `GET /api/v1/instances/operations/{operation_id}` | 轮询异步操作进度 |
| 最近操作 | `GET /api/v1/instances/operations?limit=10` | 最近 N 个操作 |
| 节点堆栈 | `GET /api/v1/instances/{cluster_name}/nodes/{node_name}/stack` | 获取线程堆栈 |

## 通用执行规范

1. **先查后改**: 执行变更前用 GET 确认当前状态
2. **明确告知**: 说明操作、影响范围和风险等级
3. **等待确认**: 🔴 级别操作必须等待用户明确回复"确认"
4. **结果验证**: 操作后再次查询确认操作成功
5. **错误处理**: 失败时展示错误信息并建议排查方向
