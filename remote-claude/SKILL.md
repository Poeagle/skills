---
name: remote-claude
description: >-
  通过 OctoAlly REST API 远程操控 Claude Code 编码会话。
  当需要远程调用 claude code 执行编码任务、在远程服务器上管理 AI 编程会话、
  通过 OctoAlly 仪表盘操控远程 agent、或跨机器执行代码任务时触发。
  也适用于需要将远程 claude 任务编排进自动化工作流的场景。
  包含完整的 API 交互流程、状态机说明、轮询模式和Session卡住的排查指南。
trigger: >-
  When the user mentions remote claude, OctoAlly, remote coding,
  running claude on another machine, or needs to automate/script
  claude code sessions via API.
---

# Remote Claude via OctoAlly API

通过 OctoAlly 的 REST API 远程调用 Claude Code 执行编码任务。

## API Base URL

```
BASE = http://localhost:42010/api
```

如果端口变了，从环境变量 `OCTOALLY_PORT` 获取，默认 42010。

## 前置条件

1. **SSH 隧道已开启**：本机 `localhost:42010` 转发到远程 OctoAlly 服务
2. **OctoAlly 服务在远程运行**：目标服务器上已启动 `octoally`
3. **tmux 已安装**（否则会话不持久）
4. **优先确保 `skip_permissions` 已开启**（见下节）

## 出发前检查（Pre-flight Check）⚠️

**在创建 session 之前**，先跑一遍检查，避免 session 卡在 pending：

```python
import requests
BASE = "http://localhost:42010/api"

# 1. 读能力文档（必须第一步）
caps = requests.get(f"{BASE}/agent/capabilities").json()
print(f"API v{caps['version']}")

# 2. 查项目，重点看 skip_permissions
projects = requests.get(f"{BASE}/projects").json()
for p in projects["projects"]:
    status = "✅" if p.get("skip_permissions") else "⚠️  skip_permissions=0"
    print(f"  {p['name']}: {status}")

# 3. 如果 skip_permissions=0，开启它
for p in projects["projects"]:
    if not p.get("skip_permissions"):
        r = requests.patch(f"{BASE}/projects/{p['id']}", json={"skip_permissions": 1})
        print(f"  → 已开启 {p['name']}: {r.status_code}")

# 4. 检查 session_claude_command
settings = requests.get(f"{BASE}/settings").json()["settings"]
cmd = settings.get("session_claude_command", "")
print(f"  session命令: {cmd}")

# 5. 查看已有 sessions
sessions = requests.get(f"{BASE}/sessions").json()
running = [s for s in sessions["sessions"] if s["status"] == "running"]
print(f"  已有 running session: {len(running)}个")
if running:
    print(f"  可以用 execute 直接发命令，不用新建")
```

## 关键概念

### 会话状态机

OctoAlly 的 session 有三种状态：

| 状态 | 含义 | 可以发输入吗？ |
|------|------|---------------|
| `busy` | Claude 正在工作/思考 | ❌ 等 |
| `idle` | 安静了 2 秒，没有提示符 | ✅ 可以 |
| `waiting_for_input` | Claude 正在等你输入 | ✅ 必须发 |

### Prompt 类型

当状态是 `waiting_for_input` 时，`promptType` 告诉你怎么回复：

| promptType | 含义 | 回复方式 |
|-----------|------|---------|
| `choice` | 选项列表（如 "1. 继续 2. 取消"） | 发对应的数字 |
| `confirmation` | 确认提示（如 "(Y/n)"） | 发 y 或 n |
| `text` | 自由文本输入（以 `>` 或 `?` 结尾） | 发文本 |

## Session 卡在 Pending 的处理（常见问题）

**症状：** `POST /api/sessions` 返回 session id，但 status 一直是 `"pending"`，`pid` 为 null，从未转为 `"running"`。

**最可能的原因（按频率排序）：**

### 1. skip_permissions = 0（最常见）
项目配置未开启权限跳过，claude 启动时卡在授权确认。

**检查：** `GET /api/projects` 看该项目的 `skip_permissions` 字段。
**修复：** `PATCH /api/projects/:id {"skip_permissions": 1}`

### 2. claude CLI 是 shell 别名
OctoAlly 的 worker 通过 execFile 启动进程，shell 别名不会在非交互 shell 中生效。

**检查：** `GET /api/settings` 看 `session_claude_command`；远程服务器上 `which claude`。
**修复：** 用绝对路径更新 setting：
```bash
PUT /api/settings
{"settings": {"session_claude_command": "/home/user/.local/bin/claude --dangerously-skip-permissions --effort=max"}}
```

### 3. OctoAlly worker 池已满
已经有 running 的 session 占用了 worker，新 session 排队。

**检查：** `GET /api/sessions` 看是否有 `running` 状态的 session。
**修复：** `DELETE /api/sessions/:id` 清理不用的 session。

### 4. tmux 未安装
OctoAlly 依赖 tmux 管理会话。

**检查：** 远程服务器上 `which tmux`。
**修复：** `sudo apt install tmux`（Debian）或 `brew install tmux`（macOS）。

### Workaround：复用已有 running session

如果新建 session 一直 pending，但已经有一个 running 的 session：

```python
sessions = requests.get(f"{BASE}/sessions").json()
running = [s for s in sessions["sessions"] if s["status"] == "running"]
if running:
    sid = running[0]["id"]
    result = requests.post(f"{BASE}/sessions/{sid}/execute", json={
        "input": "你的命令",
        "timeout": 60000,
        "quiescenceMs": 5000
    }).json()
    print(result["output"])
```

### 绕过：直接 SSH 到远程服务器验证

```bash
ssh -J jump-host user@target-server "which claude && claude --version"
ssh -J jump-host user@target-server "which tmux && tmux -V"
# 看 OctoAlly 日志
ssh -J jump-host user@target-server "tail -50 ~/.octoally/octoally.log"
```

## 标准交互流程

### 第一步：读取 API 能力文档（必须）

每次先读能力文档，获取最新的端点信息和规则：

```
GET {BASE}/agent/capabilities
```

### 第二步：查看可用项目

```
GET {BASE}/projects
```

返回项目列表，每个包含 `id`、`name`、`path`。

### 第三步：创建会话

```
POST {BASE}/sessions
Content-Type: application/json

{
  "project_path": "/path/to/project",
  "task": "你的任务描述",
  "project_id": "可选的 project_id"
}
```

返回 `session.id`。如果返回的 `pid` 为 null 且 `status` 为 `"pending"`，参见上节排查。

### 第四步：轮询输出（推荐方式）

使用 display 端点，带 cursor 增量轮询：

```
# 首次：不加 since
GET {BASE}/sessions/{id}/display?lines=100

# 后续：传 cursor 只拿新内容
GET {BASE}/sessions/{id}/display?lines=100&since={cursor}
```

返回：
```json
{
  "sessionId": "...",
  "processState": "busy|idle|waiting_for_input",
  "promptType": "choice|confirmation|text|null",
  "choices": ["option1", "option2"],
  "output": "rendered terminal text",
  "cursor": 1234,
  "truncated": false
}
```

**轮询间隔建议：**
- `busy` 状态：每 5-10 秒轮询一次
- `idle`/`waiting_for_input`：立即处理

### 第五步：发送输入

当状态不是 `busy` 时，发送输入：

```
POST {BASE}/sessions/{id}/execute
Content-Type: application/json

{
  "input": "你的回复",
  "timeout": 60000,
  "quiescenceMs": 5000
}
```

返回：
```json
{
  "status": "completed|timeout|pattern_matched",
  "output": "claude 的响应文本",
  "state": { "processState": "...", ... }
}
```

**参数说明：**
- `timeout`：最长等待时间（毫秒），session 建议 60000
- `quiescenceMs`：输出安静多久认为完成（毫秒），session 建议 5000
- `input`：要发送的文本，**不能是空字符串、空格、纯换行**

### 第六步：重复 4-5 直到任务完成

## 完整交互示例流程

```python
import requests, time

BASE = "http://localhost:42010/api"

# 1. 查项目
projects = requests.get(f"{BASE}/projects").json()
proj = [p for p in projects["projects"] if "your-project" in p["name"]][0]

# 2. 创建会话
session = requests.post(f"{BASE}/sessions", json={
    "project_path": proj["path"],
    "project_id": proj["id"],
    "task": "重构 auth 模块"
}).json()["session"]

sid = session["id"]
cursor = None

# 3. 轮询
while True:
    url = f"{BASE}/sessions/{sid}/display?lines=100"
    if cursor:
        url += f"&since={cursor}"
    resp = requests.get(url).json()
    cursor = resp.get("cursor")
    
    if resp.get("output"):
        print(resp["output"])
    
    state = resp["processState"]
    if state == "busy":
        time.sleep(5)
        continue
    
    # 4. 决定输入
    if state in ("idle", "waiting_for_input"):
        # 判断是否需要继续
        if "任务完成" in resp.get("output", ""):
            break
        # 发输入
        result = requests.post(f"{BASE}/sessions/{sid}/execute", json={
            "input": "继续",
            "timeout": 60000,
            "quiescenceMs": 5000
        }).json()
        print(result.get("output", ""))
    
    time.sleep(2)
```

## 快捷操作

### 查看会话列表
```
GET {BASE}/sessions
```

### 查看单个会话状态
```
GET {BASE}/sessions/{id}/state
```

### 终止会话
```
DELETE {BASE}/sessions/{id}
```

### 取消卡住的执行
```
POST {BASE}/sessions/{id}/cancel
```

### 创建终端（非 AI，纯 shell）
```
POST {BASE}/sessions
{"project_path": "...", "mode": "terminal"}
```

### 创建 Agent（预定义角色）
```
POST {BASE}/sessions
{"project_path": "...", "task": "...", "mode": "agent", "agent_type": "code-reviewer"}
```

## 用 WebSocket 替代轮询（低延迟）

**注意：WebSocket 只对 `running` 状态的 session 有效。** `pending` 状态的 session 连上去会报 error。

```
WS ws://localhost:42010/api/sessions/{id}/agent
```

支持的消息：
- 发送：`{"type": "execute", "requestId": "1", "input": "..."}`
- 发送：`{"type": "get_state", "requestId": "1"}`
- 接收：`{"type": "connected", ...}` — 连接成功
- 接收：`{"type": "state_change", "processState": "...", ...}` — 状态变化
- 接收：`{"type": "output", "text": "..."}` — 实时输出
- 接收：`{"type": "execute_result", ...}` — 执行完毕
- 接收：`{"type": "state", ...}` — 状态快照

## 清理

任务完成后，用 DELETE 终止会话，避免资源泄漏。

## 注意事项

1. **永远先读 `/api/agent/capabilities`** — 这是最新的 API 权威文档
2. **不要发空输入** — 空字符串、空格、纯换行会导致无响应
3. **不要直接读 PTY 输出** — 总是用 display 或 execute 接口
4. **检查状态再发输入** — busy 时发输入会返回 409
5. **SSH 隧道必须保持** — 隧道断了 API 就不可用
6. **Python 示例中的 requests 库需要安装**：`pip install requests`
