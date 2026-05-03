# CLAUDE.md

This file provides guidance to Claude Code / Claw Code when working in this repository.

## 语言设定与核心角色

- **语言指令**：无论输入何种语言，必须始终使用**简体中文**进行思考、回复和知识库的编写。
- **角色定义**：你正在维护一个 **LLM Wiki**（根据 [Karpathy 的规范](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)），你的任务是将碎片化的信息编译成结构化、高度相互链接的 Obsidian 知识库。

## 核心目录与权限边界

### Vault 根目录概览

```
assets/               📦 媒体资产 — 图片、PDF、附件（引用时使用 ![[文件.png]]）
raw/                  📥 原始资料收件箱（只读事实层，处理后归档）
  01-articles/        📄 网页剪藏、技术文章
  02-papers/          🎓 论文、PDF 文档
  03-transcripts/     🎙️ 视频/播客转录
  04-weread/          📱 微信读书划线笔记（自动同步，只读）
  09-archive/         🗃️ 已处理文件的归档目录，禁止读取
wiki/                 🧠 知识编译输出层（AI 拥有写权限）
  concepts/           🏗️ 概念、框架、方法论
  entities/           👥 实体（被分析对象或独立知识生产者）
  sources/            🔍 来源摘要（针对 raw/ 文件的一对一核心观点提炼）
  syntheses/          💎 综合研究（复杂问题的深度分析报告）
  index.md            📑 全局内容字典
  log.md              📜 操作日志
```

### 权限细则

| 路径 | 权限 | 说明 |
|------|------|------|
| `raw/`（含子目录） | 🔒 只读 | 原始素材收件箱。禁止修改文件内容。`09-archive/` 禁止读取 |
| `assets/` | ✏️ 可写 | 可添加新的媒体文件 |
| `wiki/` | ✏️ **可写 — 你的专属工作区** | 在此创建、更新、提炼知识 |

## Wiki 核心文件契约

### 1. `wiki/index.md`（总目录格式）

每次向 wiki 新增知识页后，必须同步更新此文件，按分类加入目录：

```
## Sources
- [[摘要-source-slug]] — 该资料的核心主旨摘要。

## Entities
- [[EntityName]] — 该实体的身份定义或核心功能。

## Concepts
- [[ConceptName]] — 该概念或框架的核心定义。

## Syntheses
- [[synthesis-slug]] — 该页面回答的复杂问题。
```

### 2. `wiki/log.md`（操作日志）

只能追加写入（Append-only）。每次操作后记录：

```
## [YYYY-MM-DD] <动作: ingest|query|lint> | <操作简述>
- **变更**: 新增 [[PageName]]; 更新 [[index.md]]
- **冲突**: 无（或: 冲突 [[ConflictingPage]], 已标注）
```

### 3. 内容分类

| 分类 | 路径 | 命名规范 | 内容 |
|------|------|----------|------|
| 概念 | `wiki/concepts/` | TitleCase | 框架、方法论、理论 |
| 实体 | `wiki/entities/` | TitleCase | 被分析对象或独立知识生产者 |
| 来源 | `wiki/sources/` | kebab-case | raw/ 文件的一对一摘要 |
| 综合 | `wiki/syntheses/` | kebab-case | 深度问题分析报告 |

### 4. 强制双向链接

每一个 wiki 页面必须包含 `## 关联连接` 区域，使用 `[[页面名称]]` 链接到其他相关页面。绝不能产生孤岛页面。

### 5. 矛盾处理原则

如果新摄入的知识与旧知识冲突，不要静默覆盖。在页面中新建 `## 知识冲突` 区块，将两种说法都保留并做对比。

### 6. 内容质量标准

- **结构化优先**：每个节内使用表格（对比）、列表（要点/流程）、引用块（金句）等多种元素
- **避免文字墙**：连续纯段落文字不超过 5 行
- **标题分层**：`##` 大主题，`###` 子主题，禁止跳过层级
- **密度适中**：每个子主题下 3-8 个要点

## 页面 Frontmatter 规范

```yaml
---
title: "页面标题"
type: concept | entity | source | synthesis
tags: [知识标签]
sources: [关联的 raw 文件相对路径]
last_updated: YYYY-MM-DD
---
```

## 工作流指令

- `/ingest <路径>`：读取指定的 `raw/` 文件，将其核心价值提炼并整合到 `wiki/` 目录的相关概念/实体中。必须更新 index 和 log。
- `/query <问题>`：通过读取 `wiki/index.md` 寻找相关文件，进行深度阅读后综合回答，并在回答中必须使用 `[[wikilink]]` 标注引用来源。
- `/lint`：全局扫描 `wiki/` 目录，找出孤岛页面、死链以及存在逻辑冲突的地方。

> **写前确认原则**：所有创建/写入文件的操作（包括 source、entity、concept、synthesis），必须在收到用户明确指令后方可执行。
