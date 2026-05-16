---
create_time: 2026-05-01 18:15:23
update_time: 2026-05-02 00:35:44
aliases: null
tags: null
is_atomic: true
parentLinks: "[[Undone]]"
---

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 语言设定与核心角色

- **语言指令**：无论输入何种语言，你必须始终使用**简体中文**进行思考、回复和知识库的编写。
- **角色定义**：你正在维护一个 **LLM Wiki**（根据 [Karpathy 的规范](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)），你的任务是将碎片化的信息编译成结构化、高度相互链接的 Obsidian 知识库。

## 核心目录与权限边界

你必须严格遵守以下文件操作权限：

- **权限层级说明**：
  - 🔒 **只读 (Immutable)** — 禁止修改、删除、重命名
  - ✏️ **可写 (Writable)** — 创建、更新、组织内容的专属工作区

### Vault 根目录概览

```
assets/               📦 媒体资产 — 图片、PDF、附件（引用时使用 ![[文件.png]]）
raw/                  📥 原始资料收件箱（只读事实层，处理后归档）
  01-articles/        📄 网页剪藏、技术文章
  02-papers/          🎓 论文、PDF 文档
  03-transcripts/     🎙️ 视频/播客转录
  04-weread/          📱 微信读书划线笔记（自动同步，只读）
  05-coderepo/        💻 代码仓库工作区（待解构的源码目录）
  09-archive/         🗃️ 已归档（/ingest 执行后源文件自动移入）
template/             📋 Templater 模板
wiki/                 🧠 知识编译输出层（LLM 拥有写权限）
  code-design/        🔧 软件设计文档（基于 arc42 标准的仓库解构产出）
  concepts/           🏗️ 概念、框架、方法论
  entities/           👥 实体（被分析对象或独立知识生产者，非"知识管道"）
  sources/            🔍 来源摘要（针对 raw/ 文件的一对一核心观点提炼）
  syntheses/          💎 综合研究（复杂问题的深度分析报告）
  index.md            📑 全局内容字典
  log.md              📜 操作日志
```

### 权限细则

| 路径 | 权限 | 说明 |
|------|------|------|
| `raw/`（含子目录） | 🔒 只读 | 原始素材收件箱。禁止修改文件内容。`05-coderepo/` 中的代码仓库只读用于分析，不归档。`09-archive/` 禁止读取 |
| `template/` | 🔒 只读 | 模板文件，禁止修改 |
| `assets/` | ✏️ 可写 | 可添加新的媒体文件 |
| `wiki/` | ✏️ **可写 — 你的专属工作区** | 在此创建、更新、提炼知识 |

## Wiki 核心文件契约

在 `wiki/` 中工作时，必须维护以下内容：

### 1. `wiki/index.md`（总目录格式）

每次向 wiki 新增知识页后，必须同步更新此文件，按分类加入目录。

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
- **变更**: 新增 [[PageName]], [[PageName]]; 更新 [[index.md]]
- **冲突**: 无（或: 冲突 [[ConflictingPage]], 已标注）
```

### 3. 内容分类

| 分类 | 路径 | 命名规范 | 内容 |
|------|------|----------|------|
| 概念 | `wiki/concepts/` | TitleCase | 框架、方法论、理论 |
| 实体 | `wiki/entities/` | TitleCase | 被分析对象或独立知识生产者（非"知识管道"） |
| 来源 | `wiki/sources/` | kebab-case | raw/ 文件的一对一摘要 |
| 综合 | `wiki/syntheses/` | kebab-case | 深度问题分析报告 |

### 4. Syntheses 页面模板

完整模板（含 frontmatter，可直接复制使用，sources 路径在归档时更新）：

```markdown
---
title: "综述标题（纯主题描述，不含创作者名）"
type: synthesis
tags: [标签1, 标签2]
sources: [raw/03-transcripts/原始文件.md]
last_updated: YYYY-MM-DD
---

## 总纲/引言
[1-2段高度概括，点明该综合分析的底层逻辑或核心问题]

## 一、[主题一]
[使用 ### 划分子主题，配合列表/表格/引用块]
[每个主题独立成节，节内必须有清晰的结构]

## 二、[主题二]
...

## N、核心模型/总结
[可选，用一个框架、模型或图表把全文串起来]

## 关联连接
- [[RelatedConcept]] — 关联概念
- [[RelatedEntity]] — 关联实体
- [[摘要-source-slug]] — 来源
```

要求：
- **必须分层**：用 `##` 一级标题划分大主题，`###` 二级标题划分子主题
- **必须结构化**：每个节内使用表格（对比）、有序列表（流程/步骤）、无序列表（要点）、引用块（金句）等多种元素
- **避免平铺**：连续纯段落文字不超过 5 行，宁可分段、分条、分表
- **结尾模型**：鼓励在末尾提炼核心模型或框架图，便于记忆

### 5. 强制双向链接

每一个 wiki 页面必须包含 `## 关联连接` 区域，使用 `[[页面名称]]` 链接到其他相关页面。绝不能产生孤岛页面。

### 6. 矛盾处理原则

如果新摄入的知识与旧知识冲突，不要静默覆盖。在页面中新建 `## 知识冲突` 区块，将两种说法都保留并做对比。

### 7. 内容质量标准（所有 wiki 页面通用）

所有 wiki 页面正文必须遵循以下原则：

- **结构化优先**：每个节内至少使用以下 2-3 种元素——表格（对比）、有序列表（流程/步骤）、无序列表（要点提炼）、引用块（金句/关键洞见）
- **避免文字墙**：连续纯段落文字不超过 5 行。提示：如果一段话超过 100 字，考虑拆分为列表或用表格呈现
- **标题分层**：`##` 划分大主题，`###` 划分子主题，**禁止**跳过层级直接用 `####`
- **密度适中**：每个子主题下 3-8 个要点为宜，太多需要进一步拆分，太少则合并到上级
- **引用块用法**：`> 金句` 仅用于原文中高度凝练、值得单独突出的句子，不要大段使用

## 页面 Frontmatter 规范

所有 wiki 页面必须包含以下 YAML 头部：

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
- `/ingest code <路径>`：读取 `raw/05-coderepo/` 下的代码仓库，解析为 arc42 标准设计文档，输出到 `wiki/code-design/`。必须更新 index 和 log。
- `/query <问题>`：通过读取 `wiki/index.md` 寻找相关文件，进行深度阅读后综合回答，并在回答中必须使用 `[[wikilink]]` 标注引用来源。
- `/lint`：全局扫描 `wiki/` 目录，找出孤岛页面（没有双链）、死链（链接不存在的页面）以及存在逻辑冲突的地方。

> **写前确认原则**：主动命令（`/ingest`、`/ingest <path>`、`/ingest code`、`/query`）直接执行，无需逐条确认。隐式触发（如"帮我把这个收藏一下"）先展示规划再确认动手。
