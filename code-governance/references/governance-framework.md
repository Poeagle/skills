# Governance Framework 参考标准

语言无关的仓库治理框架标准，基于 [openclaw](https://github.com/Poeagle/openclaw) Agent-first Governance 模式。

## 目录结构规范

```
project-root/
├── AGENTS.md                 # 中央治理文件（必需）
├── CLAUDE.md                 # [可选] 项目级指令，与 AGENTS.md 互补
├── src/                      # 核心源码目录
│   └── AGENTS.md             # [可选] scoped 治理
├── packages/                 # [可选] monorepo 子包
│   └── <package>/
│       └── AGENTS.md         # [可选] scoped 治理
├── extensions/               # [可选] 扩展子系统
│   └── AGENTS.md             # [可选] scoped 治理
├── test/                     # 测试目录
├── docs/                     # 文档目录
├── scripts/                  # 工具脚本
├── .github/                  # CI/CD 与 GitHub 配置
│   ├── workflows/
│   │   └── ci.yml
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── CODEOWNERS
├── CONTRIBUTING.md           # 贡献指南
├── SECURITY.md               # 安全策略
├── CHANGELOG.md              # 变更日志
├── README.md                 # 项目介绍
├── LICENSE                   # 许可证
└── .gitignore                # Git 忽略规则
```

## AGENTS.md 必需章节

### `## Start`
项目入口信息，包含：
- 项目简介（1-2 句）
- 当前分支说明
- 首次使用的入口指令（clone、install、dev）

### `## Map`
目录到 agent 的映射关系。格式：

```markdown
## Map
- `src/core/` — 核心业务逻辑，agent 需特别注意模块边界
- `src/extensions/` — 扩展子系统，可独立演进
- `src/cli/` — CLI 入口，保持轻量
- `test/` — 测试目录，与 src 结构镜像
```

### `## Architecture`
架构约束，包含：
- 模块边界定义
- 依赖方向（core → 工具库，不允许反向引用）
- 导入规则（哪些模块可以 import 哪些模块）
- 设计模式约定

### `## Commands`
标准化命令清单：

```markdown
## Commands
- `pnpm dev` — 启动开发服务器
- `pnpm build` — 生产构建
- `pnpm test` — 运行测试
- `pnpm lint` — 代码检查
- `pnpm typecheck` — TypeScript 类型检查
```

### `## Code`
代码风格与约束，包含：
- 命名约定（camelCase, PascalCase, kebab-case）
- 类型系统要求
- 错误处理模式
- 文件拆分规则（~700 LOC）
- 注释规范

### `## Tests`
测试规范，包含：
- 测试框架与运行命令
- 测试文件命名约定（`*.test.ts`）
- 覆盖率要求
- mock 策略

### `## Git`
版本控制规范，包含：
- 分支策略（main / dev / feature branches）
- 提交信息格式（Conventional Commits）
- PR 流程

### `## Security`
安全考量，包含：
- 敏感信息处理（环境变量、密钥）
- 依赖安全（Dependabot / SCA）
- 输入验证要求
- 安全审计

## Scoped AGENTS.md 规则

子目录的 AGENTS.md 用于局部覆盖顶层规则：

```
顶层 AGENTS.md（fallback）
  └── src/AGENTS.md（覆盖 src 相关规则）
  └── extensions/AGENTS.md（覆盖 extensions 相关规则）
```

**优先级**：scoped AGENTS.md > 顶层 AGENTS.md

Scoped AGENTS.md 通常包含：
- 该模块特有的 Architecture 规则
- 该模块特有的 Code 规范
- 该模块的 Commands（如适用）

## CI/CD 工作流要求

最低要求 CI 包含：

| 阶段 | 命令 | 说明 |
|------|------|------|
| Lint | `pnpm lint` / `ruff check` | 代码风格检查 |
| Type Check | `pnpm typecheck` / `mypy` | 类型检查（如适用） |
| Test | `pnpm test` / `pytest` | 单元测试 |
| Build | `pnpm build` / `poetry build` | 构建验证 |

推荐 CI 触发器：`push` 到 main、`pull_request` 到 main。

## 所有权模型（CODEOWNERS）

```codeowners
# 默认所有者
* @team/core

# 核心模块
/src/core/ @team/core-owners

# 扩展模块
/extensions/ @team/extensions-owners

# CI/CD 配置
/.github/ @team/infra

# 文档
/docs/ @team/docs
```

## PR 流程规范

1. 创建 feature branch 从 main 分支
2. 提交使用 Conventional Commits 格式
3. 提交 PR 时使用 PR 模板
4. CI 必须全部通过
5. 至少 1 名代码所有者 approve
6. Squash merge 到 main

## 安全策略框架

```markdown
# Security Policy

## 支持的版本
| 版本 | 支持状态 |
|------|----------|
| 1.x  | ✅ 活跃支持 |
| <1.0 | ❌ 停止支持 |

## 报告漏洞
将漏洞报告到 security@example.com
预期 48 小时内回复。

## 安全实践
- 所有依赖定期通过 Dependabot 更新
- 敏感信息通过环境变量注入
- 输入验证在所有外部边界执行
```

## 测试策略要求

| 层级 | 类型 | 工具 | 目标覆盖率 |
|------|------|------|-----------|
| 单元测试 | 纯函数/组件 | vitest / jest | ≥ 80% |
| 集成测试 | 模块间交互 | vitest / supertest | ≥ 60% |
| E2E 测试 | 端到端流程 | playwright / cypress | 关键路径 |

## 文件命名规范（语言无关）

| 类型 | 命名 | 示例 |
|------|------|------|
| 源文件 | kebab-case | `user-service.ts` |
| 组件 | PascalCase | `UserProfile.tsx` |
| 测试文件 | 源文件名 + `.test` | `user-service.test.ts` |
| 工具脚本 | kebab-case | `build-docs.sh` |
| 配置文件 | kebab-case | `tsconfig.json` |
| 文档 | PascalCase | `CONTRIBUTING.md` |

## 环境变量管理

```
# .env.example（必须提交到仓库）
PORT=3000
DATABASE_URL=postgresql://localhost/mydb
API_KEY=your-api-key-here

# .env（不提交，gitignore 中排除）
DATABASE_URL=postgresql://user:pass@prod-host/mydb
API_KEY=sk-xxx
```

**规则**：
- 所有环境变量必须有 `.env.example` 模板
- 敏感环境变量永远不提交到仓库
- CI 环境变量通过 CI 平台的 secrets 管理

## Multi-Agent 兼容性

AGENTS.md 是唯一的治理源文件。其他 AI 编码平台的配置文件均为指向 AGENTS.md 的符号链接，确保**一处修改，处处生效**。

### 各平台配置文件名

| 平台 | 配置文件 | 符号链接命令 |
|------|----------|-------------|
| Claude Code | `CLAUDE.md` | `ln -s AGENTS.md CLAUDE.md` |
| Cursor | `.cursorrules` | `ln -s AGENTS.md .cursorrules` |
| Windsurf | `.windsurfrules` | `ln -s AGENTS.md .windsurfrules` |
| GitHub Copilot | `.github/copilot-instructions.md` | `mkdir -p .github && ln -s ../AGENTS.md .github/copilot-instructions.md` |
| Codex CLI | `CODEX.md` | `ln -s AGENTS.md CODEX.md` |

### 设计原理

- **单一事实源**：`AGENTS.md` 是仓库治理的权威定义。其他所有 agent 配置仅通过符号链接引用它
- **无需重复维护**：新增或修改治理规则时，只需编辑一个文件
- **平台无关内容**：`AGENTS.md` 使用纯 Markdown，不依赖任何特定平台的语法扩展，确保所有 agent 都能正确解析
- **Git 友好**：符号链接在 Git 中作为普通文件跟踪，clone 后自动恢复链接关系

### Windows 注意事项

在 Windows 上创建符号链接需要管理员权限或启用开发者模式：

```powershell
# Windows (管理员终端)
New-Item -ItemType SymbolicLink -Path "CLAUDE.md" -Target "AGENTS.md"
```

Git for Windows 需要配置 `core.symlinks=true`：

```bash
git config core.symlinks true
```
