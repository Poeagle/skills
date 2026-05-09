---
kind: operation
---

# 插件问题案例

> 触发: 插件加载失败、插件函数未识别、ODBC 乱码、插件版本不兼容

## 规则

### ODBC 读取长字符串乱码
条件: 通过 ODBC 插件读取文本字段时，长字符串后半段出现乱码，短字符串正常
根因: ODBC 层将字符串列宽识别为 255（而非真实最大宽度），读取时截断导致编码异常
处置: 在 DSN 或连接串中增加参数 `MaxVarcharSize=0`（关闭固定上限）。驱动版本差异可能影响参数行为，记录驱动版本

### 插件加载失败 — 函数未识别
条件: 调用插件函数时报 `Can't recognize function`，或启动日志出现 `Failed to load plugin`
根因: 插件文件不在 `<server>/plugins/<pluginName>/` 目录下；`preloadModules` 配置缺失或拼写错误；插件依赖的系统库版本不匹配
处置: 确认插件文件存在且路径正确 → 检查 `preloadModules=plugins::<pluginName>` 配置 → 日志中具体错误信息（`undefined symbol`/`cannot open shared object`）→ `ldd` 检查动态库依赖 → 补全后重启。HA 集群需所有控制节点配置一致

### 插件版本与 Server 不兼容
条件: 升级 Server 后插件功能异常（调用报错、返回结果不正确、WARN 日志）
根因: 插件 ABI 与 Server 版本不匹配，DolphinDB 插件需与 Server 大版本对应
处置: 确认 Server 版本号 → 从官方仓库下载匹配版本的插件二进制文件 → 替换后重启节点

## 验证
- 插件函数调用正常
- 数据读取结果正确无乱码
