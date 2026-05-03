---
name: code-governance
description: 仓库治理审计、初始化与代码生成约束。审计现有仓库治理健康度，按 openclaw Agent-first Governance 模式初始化新仓库，并在已治理仓库中约束 agent 代码生成行为。当用户提到"检查治理"、"审计仓库"、"初始化仓库"、"创建新项目"、"/governance init"、"/governance audit"时使用。
---

# code-governance

基于 [openclaw](https://github.com/Poeagle/openclaw) **Agent-first Governance** 模式的仓库治理技能。

提供三种工作模式：

| 模式 | 触发词 | 说明 |
|------|--------|------|
| **Init** | `初始化仓库`, `创建新项目`, `/governance init` | 交互式创建完整治理结构 |
| **Audit** | `检查治理`, `审计仓库`, `/governance audit` | 深度检测仓库治理健康度 |
| **Code-gen** | 被动触发（agent 生成代码时） | 在已治理仓库中遵循 AGENTS.md 规范 |

---

## 核心概念

### Agent-first Governance

治理结构以 **AGENTS.md** 为中央控制点。AGENTS.md 是**纯治理契约**，不嵌入语言特定细节，通过 `## References` 引用外部语言规范文件。

### AGENTS.md 完整章节结构

| 章节 | 用途 |
|------|------|
| `## Karpathy 准则` | 约束 AI 代理编码行为的 4 条原则（先思考、简单优先、精准修改、目标驱动） |
| `## References` | 指向语言特定规范文件 |
| `## Start` | 分支管理、入口指令 |
| `## Map` | 目录到 agent 的映射 |
| `## Architecture` | 模块边界与导入规则 |
| `## Commands` | 标准命令（dev/build/test/lint） |
| `## Code` | 代码风格与实现约束 |
| `## Tests` | 测试规范 |
| `## Git` | 提交规范与分支策略 |
| `## Security` | 安全考量 |
| `## Multi-Agent 兼容性` | 符号链接对照表（供维护者参考） |

### Multi-Agent 兼容性

AGENTS.md 是唯一的治理源文件。其他 AI 编码平台在启动时读取各自的配置文件，这些文件均为指向 AGENTS.md 的**符号链接**。只需维护一份文件，所有平台共享同一套治理规则。

必要时，在关键子目录中放置 **scoped AGENTS.md** 覆盖局部上下文，顶层规则作为 fallback。

### 架构分层

```
AGENTS.md                  ← 纯治理契约（语言无关）
  └── references/          ← 语言规范（按需引用）
      ├── ts-standards.md  ← TypeScript 特定规则
      ├── py-standards.md  ← Python 特定规则
      ├── go-standards.md  ← Go 特定规则
      └── rs-standards.md  ← Rust 特定规则
```

### 目录结构规范

```
project-root/
├── AGENTS.md                      # 中央治理文件（必需，唯一编辑源）
├── CLAUDE.md                      → AGENTS.md (符号链接)
├── .cursorrules                   → AGENTS.md (符号链接)
├── .windsurfrules                 → AGENTS.md (符号链接)
├── CODEX.md                       → AGENTS.md (符号链接)
├── .github/
│   └── copilot-instructions.md    → ../AGENTS.md (符号链接)
├── references/                    # 语言规范（Init 模式按需生成）
│   └── xx-standards.md
├── src/                           # 核心源码
│   └── AGENTS.md                  # [可选] scoped 治理
├── extensions/                    # [可选] 扩展子系统
│   └── AGENTS.md                  # [可选] scoped 治理
├── test/                          # 测试目录
├── docs/                          # 文档目录
├── scripts/                       # 工具脚本
├── .github/workflows/             # CI/CD 配置
├── CONTRIBUTING.md                # 贡献指南
├── SECURITY.md                    # 安全策略
├── CODEOWNERS                     # 所有权配置
├── CHANGELOG.md                   # 变更日志
└── README.md                      # 项目介绍
```

> 📌 **单文件原则**：`AGENTS.md` 是唯一需要编辑的治理文件。其他 agent 平台配置（`CLAUDE.md`、`.cursorrules`、`.github/copilot-instructions.md` 等）均为符号链接，无需单独维护。

---

## 模式一：Init（交互式仓库初始化）

### 流程

1. **收集信息**：通过交互式提问（AskUserQuestion）获取以下信息：

   | 参数 | 说明 | 默认值 |
   |------|------|--------|
   | 项目名称 | 英文短名称，用作包名 | — |
   | 项目描述 | 一行简述 | — |
   | 技术栈 | TypeScript / Python / Go / Rust / Other | TypeScript |
   | 包管理器 | pnpm / npm / yarn | pnpm |
   | 测试框架 | vitest / jest / pytest / go test / cargo test | vitest |
   | CI 提供商 | GitHub Actions / GitLab CI / None | GitHub Actions |

2. **生成 AGENTS.md**：中央治理文件，包含以下内容：
   - **Karpathy 准则** — 先思考、简单优先、精准修改、目标驱动
   - **References** — 引用语言特定规范文件
   - **Start / Map / Architecture / Commands / Code / Tests / Git / Security** — 8 个治理必需章节
   - **Multi-Agent 兼容性** — 符号链接说明

3. **创建符号链接**：为所有活跃使用的 agent 平台创建指向 AGENTS.md 的符号链接：

   | 平台 | 命令 |
   |------|------|
   | Claude Code | `ln -s AGENTS.md CLAUDE.md` |
   | Cursor | `ln -s AGENTS.md .cursorrules` |
   | Windsurf | `ln -s AGENTS.md .windsurfrules` |
   | GitHub Copilot | `mkdir -p .github && ln -s ../AGENTS.md .github/copilot-instructions.md` |
   | Codex CLI | `ln -s AGENTS.md CODEX.md` |

4. **生成语言规范** `references/`：
   - TypeScript → `references/ts-standards.md` + `assets/scaffolds/ts/*`
   - Python → `references/py-standards.md` + `assets/scaffolds/py/*`
   - Go → `references/go-standards.md` + `assets/scaffolds/go/*`
   - Rust → `references/rs-standards.md`

5. **生成配套文件**：

   | 文件 | 用途 |
   |------|------|
   | `CONTRIBUTING.md` | 贡献指南 |
   | `SECURITY.md` | 安全策略 |
   | `CODEOWNERS` | 代码所有权 |
   | `PULL_REQUEST_TEMPLATE.md` | PR 模板 |
   | `.gitignore` | Git 忽略规则 |
   | `.github/workflows/ci.yml` | CI 工作流（需按技术栈调整） |
   | `README.md` | 项目骨架 README |

6. **创建基础目录结构**：`src/`, `test/`, `docs/`, `scripts/`

7. **报告产出**：列出生成的所有文件（包括符号链接），解释每个文件的作用。

---

## 模式二：Audit（深度治理审计）

### 触发方式

- 用户说 `"检查这个仓库的治理"`、`"审计"`、`/governance audit`
- 如未提供路径，默认使用当前工作目录

### 审计引擎架构

审计系统采用**插件化架构**，以 `assets/scripts/` 中的 Python 包实现：

```
assets/scripts/
├── run_audit.py          # CLI 入口
└── audit/                # 审计包
    ├── __init__.py        # 自动注册所有语言检查器
    ├── base.py            # 检查器基类 + 插件注册表
    ├── report.py          # 报告数据结构和输出格式
    ├── structure.py       # 语言无关的结构检查
    ├── check_ts.py        # TypeScript 插件 (@register)
    ├── check_py.py        # Python 插件 (@register)
    ├── check_go.py        # Go 插件 (@register)
    └── check_rust.py      # Rust 插件 (@register)
```

新的语言检查器只需继承 `BaseLangChecker` 并添加 `@register` 装饰器即可自动生效。

### 审计维度

#### 层级一：结构完整性（语言无关）

| 检查项 | 合格标准 | 权重 |
|--------|----------|------|
| AGENTS.md 存在 | 文件存在且非空 | 🔴 红线 |
| AGENTS.md 章节完整性 | 包含全部 8 章 | 🔴 红线 |
| Scoped AGENTS.md | 子目录有 scoped 治理（如适用） | 🟡 重要 |
| 项目配置文件 | `package.json` / `pyproject.toml` / `go.mod` 等存在 | 🟡 重要 |
| 测试配置 | 测试框架已配置 | 🟡 重要 |
| 配套文件 | CONTRIBUTING, SECURITY, CODEOWNERS 等 | 🟢 建议 |

#### 层级二：代码语义（语言特定，插件化）

| 语言 | 检查项 |
|------|--------|
| **TypeScript** | `any` 使用率, `@ts-ignore`/`@ts-nocheck`, 文件 >700 LOC, 导入边界违规, exports 配置 |
| **Python** | `Any` 使用率, `# noqa`/`# type:ignore`, 文件 >500 LOC, 导入边界 |
| **Go** | `interface{}` 使用率（应替换为 `any`）, 文件 >500 LOC |
| **Rust** | `unsafe` 代码统计, 文件 >500 LOC |

#### 层级三：合规建议

- Linter 配置（ESLint / Ruff / golangci-lint / clippy 等）
- README 非空且有自定义内容
- LICENSE 文件存在

### 输出格式

```
🔴 红线违规
  - [AGENTS.md] 文件缺失
  - [AGENTS.md] 缺少章节: Architecture, Security

🟡 重要建议
  - [CODEOWNERS] 文件缺失
  - [Test] 未配置测试框架

🟢 良好实践
  - [CI] 已配置 GitHub Actions ✓
  - [README] 存在且有自定义内容 ✓

📊 总体评分: 6/10 (需要改进)
```

---

## 模式三：Code-gen（被动代码生成约束）

### 规则

1. **先读 AGENTS.md**：在写代码前检查项目根目录是否有 AGENTS.md（或指向它的符号链接 `CLAUDE.md` / `.cursorrules` 等）。如有，必须读取并遵循。
2. **遵循 Karpathy 准则**：先思考再编码、简单优先、精准修改、目标驱动。
3. **遵循 References 章节**：加载引用的语言规范文件。
4. **遵循 Architecture 章节**：模块边界和导入规则。
5. **遵循 Code 章节**：
   - 命名约定
   - 类型约束
   - 文件组织规则
6. **遵循 Tests 章节**：测试文件命名和覆盖率要求。
7. **自动补充提议**：如果检测到仓库没有 AGENTS.md，提示用户：
   > "此仓库尚未初始化治理结构。是否运行初始化？(`/governance init`)"

### 约束级别

| 级别 | 行为 |
|------|------|
| strict | 严格遵循，违反时报错 |
| warn | 先警告再继续 |
| info | 仅提醒，不阻断 |

默认使用 warn 级别，除非 AGENTS.md 中明确指定。

---

## 文件清单

```
~/.claude/skills/code-governance/
├── SKILL.md                         主技能文件
├── references/
│   ├── governance-framework.md      语言无关治理框架标准
│   ├── ts-standards.md              TypeScript 深度代码规范
│   ├── py-standards.md              Python 深度代码规范
│   ├── go-standards.md              Go 深度代码规范
│   └── rs-standards.md              Rust 深度代码规范
└── assets/
    ├── templates/                   初始化模板
    │   ├── AGENTS.md                纯治理模板（含 References）
    │   ├── CONTRIBUTING.md
    │   ├── PULL_REQUEST_TEMPLATE.md
    │   ├── CODEOWNERS
    │   ├── SECURITY.md
    │   └── gitignore
    ├── scaffolds/                   技术栈脚手架
    │   ├── ts/
    │   │   ├── tsconfig.json
    │   │   └── vitest.config.ts
    │   ├── py/
    │   │   ├── pyproject.toml
    │   │   └── pytest.ini
    │   └── go/
    │       └── go.mod
    └── scripts/
        ├── run_audit.py             CLI 入口
        └── audit/                   审计包
            ├── __init__.py          包初始化 + 插件注册
            ├── base.py              检查器基类 + 插件注册表
            ├── report.py            报告数据结构和输出
            ├── structure.py         语言无关结构检查
            ├── check_ts.py          TS 插件
            ├── check_py.py          Python 插件
            ├── check_go.py          Go 插件
            └── check_rust.py        Rust 插件
```

## 扩展指南

### 新增语言支持

1. **语言规范**：在 `references/` 下创建 `xx-standards.md`
2. **脚手架**：在 `assets/scaffolds/` 下创建 `xx/` 目录
3. **检查器插件**：在 `assets/scripts/audit/` 下创建 `check_xx.py`：

```python
from .base import BaseLangChecker, register
from .report import AuditItem

@register
class MyLangChecker(BaseLangChecker):
    marker_files = ["my-lang.toml"]  # 检测文件
    lang_name = "MyLang"

    def run(self) -> list[AuditItem]:
        return [...]  # 语义检查项
```

### 依赖说明

- **audit 包**：需要 Python 3.10+，使用标准库，零外部依赖
- 运行方式：`python run_audit.py <repo-path>` 或 `python -m audit <repo-path>`
- **权限需求**：读取仓库目录、写入目标目录（Init 模式）
