# AGENTS.md — 项目治理文件

本文件是项目的**中央治理契约**，适用于所有 AI 编码代理（Claude Code、GitHub Copilot、Cursor、Windsurf、Codex CLI 等）。

> 📌 **单文件原则**：`AGENTS.md` 是唯一需要维护的治理文件。各平台专用配置（`CLAUDE.md`、`.cursorrules`、`.github/copilot-instructions.md` 等）均为指向本文件的符号链接。修改治理规则时只需编辑此文件，无需重复更新多个位置。

---

## Karpathy 准则

> 以下准则用于约束 AI 代理的编码行为，减少常见错误。衍生自 Andrej Karpathy 对 LLM 编码陷阱的观察。

### 1. 先思考再编码

**不要假设。不要隐藏困惑。暴露权衡。**

实施前：
- 明确陈述你的假设。如果不确定，提问
- 如果存在多种解释，全部列出——不要默默选择一种
- 如果存在更简单的方法，说出来。在必要时反对
- 如果某些事情不清楚，停下来。说出困惑所在。提问

### 2. 简单优先

**写解决问题最少的代码。不做投机性编码。**

- 不做需求之外的特性
- 不为一次性用途创建抽象
- 不要添加未要求的"灵活性"或"可配置性"
- 不为不可能发生的场景写错误处理
- 如果你写了 200 行但它可以用 50 行完成，重写

问自己："高级工程师会觉得这过于复杂吗？"如果是，简化。

### 3. 精准修改

**只动必须动的。只清理自己的遗留问题。**

修改现有代码时：
- 不要"改善"相邻的代码、注释或格式
- 不要重构没坏的东西
- 匹配现有风格，即使你会有不同的做法
- 如果你发现无关的死代码，提出来——不要删掉

### 4. 目标驱动

**定义成功标准。循环直到验证。**

将任务转化为可验证的目标：
- "添加验证" → "为无效输入写测试，然后让它们通过"
- "修 bug" → "写一个能复现它的测试，然后让测试通过"
- "重构 X" → "确保测试前后都通过"

多步骤任务陈述简短计划：
```
1. [步骤] → 验证: [检查项]
2. [步骤] → 验证: [检查项]
3. [步骤] → 验证: [检查项]
```

---

## References

本项目的详细代码规范定义在以下参考文件中，agent 必须一并遵循：

- `references/{{lang}}` — 语言特定代码规范

> 如果 `references/` 目录不存在或以上文件缺失，则仅遵循本文件中的规则。

---

## Start

- **项目**: {{project_name}} — {{project_description}}
- **分支**: 当前在 `{{branch}}` 分支
- **首次使用**:
  ```bash
  git clone <repo-url>
  cd {{project_name}}
  {{install_command}}
  ```

## Map

```
{{directory_map}}
```

## Architecture

### 模块边界
- `src/core/` — 核心领域逻辑，零外部依赖
- `src/services/` — 业务编排层，可依赖 core
- `src/api/` — API / 接口层，可依赖 services + core
- `src/cli/` — CLI 入口层，可依赖 api + services + core
- `test/` — 测试目录，与 src 结构镜像

### 依赖方向
- 依赖只能单向流动：`core ← services ← api ← cli`
- **严禁**反向引用（如 api 依赖 cli）

### 导入规则
- 使用路径别名引用 `src/` 内部模块
- 禁止相对路径跨越模块边界（如 `../../core/`）
- 外部库统一在 `src/lib/` 或 `src/adapters/` 中封装适配层
- 仅类型导入使用 `import type` 语法

## Commands

```bash
{{install_command}}    # 安装依赖
{{dev_command}}        # 启动开发服务器
{{build_command}}      # 生产构建
{{test_command}}       # 运行测试
{{lint_command}}       # 代码检查
```

## Code

### 风格
- 遵循项目配置的 formatter
- 命名约定：
  - 变量/函数: camelCase
  - 类/类型/接口: PascalCase
  - 文件: kebab-case
  - 常量: UPPER_SNAKE_CASE

### 通用约束
- 函数不超过 50 行，文件不超过 700 行
- 使用具名导出（named exports），禁止 `export default`
- 禁止硬编码敏感信息

### 错误处理
- 使用显式错误类型（禁止 throw 裸值）
- 所有外部边界做输入验证（scheme 验证框架）
- 异步错误必须被处理

> **语言特定约束**（类型系统、`any` 禁令、ESM 规范等）详见 `## References` 引用的语言规范文件。

## Tests

- 测试框架: {{test_framework}}
- 运行: `{{test_command}}`
- 覆盖率目标: ≥ 80%
- 测试文件与源文件保持镜像结构:
  ```
  src/services/user-service → test/services/user-service.test
  ```

### 测试规范
- 使用 `describe` / `it` 组织测试
- 每个 `it` 只测试一个行为
- Mock 外部依赖，避免测试中的网络请求

## Git

### 分支策略
- `main` — 稳定分支，只接受 PR merge
- `dev` — 开发分支（可选）
- `feat/<name>` — 功能分支
- `fix/<name>` — 修复分支

### 提交规范
遵循 Conventional Commits:
```
<type>(<scope>): <description>

feat:    新功能
fix:     修复
chore:   杂项
docs:    文档
refactor:重构
test:    测试
```

### PR 流程
1. 从 main 创建 feature branch
2. 提交使用 Conventional Commits
3. 创建 PR（使用 PR 模板）
4. CI 必须全部通过
5. 至少 1 名 Code Owner approve
6. Squash merge 到 main

## Security

- 环境变量使用 `.env.example` 模板提交，真实值通过 CI secrets 或 `.env`（gitignored）注入
- 依赖定期通过自动依赖更新工具管理
- 外部输入必须在边界验证
- 禁止将敏感信息（API key、token、密码）硬编码到源码中
- 生产环境日志不能输出敏感字段

## Multi-Agent 兼容性

> 本节供仓库维护者参考。普通 agent 可跳过本节。

AGENTS.md 是唯一治理源。其他 agent 平台的配置文件均为指向本文件的符号链接：

| 平台 | 配置文件 | 链接方式 |
|------|----------|----------|
| Claude Code | `CLAUDE.md` | `ln -s AGENTS.md CLAUDE.md` |
| Cursor | `.cursorrules` | `ln -s AGENTS.md .cursorrules` |
| Windsurf | `.windsurfrules` | `ln -s AGENTS.md .windsurfrules` |
| GitHub Copilot | `.github/copilot-instructions.md` | `ln -s ../AGENTS.md .github/copilot-instructions.md` |
| Codex CLI | `CODEX.md` | `ln -s AGENTS.md CODEX.md` |

维护者只需编辑 `AGENTS.md`，所有代理配置自动同步。
