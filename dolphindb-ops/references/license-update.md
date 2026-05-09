---
kind: operation
---

# License 更新与过期处理指南

> 触发: License 过期、License 替换不生效、授权信息不正确

## 规则

### License 过期导致节点宕机或无法启动
条件: 日志出现 `The license has expired` 或 `invalid license`
处置: 更新 license 文件到各节点；1.30.11+ / 1.20.20+ 支持在线更新 License；低版本需重启

### License 替换后不生效
条件: 替换新 license 后重启仍显示旧授权
根因: 高优先级路径中的旧 lic 覆盖了新文件。加载顺序：HomeDir → clusterDemo（启动路径）→ server 目录
处置: 全量扫描 server、clusterDemo、启动脚本目录与 HomeDir 中的 lic 文件；备份后移走高优先级路径中的旧 lic，仅保留目标版本；重启后复核

## 验证
- 各节点 License 有效期和资源规格正确
- 逐节点核对授权状态一致性
