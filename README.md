# Skills

个人 Claude Code / Claw Code 技能集合。将 `~/.claude/skills/` 作为 git 仓库统一管理，所有技能全局可用。

```bash
git clone git@github.com:Poeagle/skills.git ~/.claude/skills
```

---

## 工作流实践

以下是用这些 skills 搭建的完整工作流，每个工作流包含所需的 skills 和工具、项目模板骨架、以及从零搭建的步骤。

---

### LLM Wiki（知识库编译）

将碎片化信息编译成结构化、高度相互链接的 Obsidian 知识库。基于 [Karpathy LLM Wiki 规范](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)。

#### 需要的 skills 和工具

| 类型 | 名称 | 用途 |
|------|------|------|
| **skill** | `ingest` | 核心编译流水线：读取 raw/ 源文件 → 提炼摘要 → 创建实体/概念页面 → 归档 |
| **skill** | `query` | 知识库深度检索与综合回答，双链引用标注来源 |
| **skill** | `lint` | 知识库健康扫描：死链、孤儿页面、未同步索引、知识冲突 |
| **skill** | `defuddle` | 从网页 URL 提取纯净 Markdown，用于外源采集 |
| **skill** | `excalidraw-diagram` | 将知识模型可视化为 Excalidraw 图表 |
| **skill** | `obsidian-cli` | 与运行中的 Obsidian 交互（搜索/创建/管理笔记） |
| **skill** | `obsidian-markdown` | Obsidian 风味 Markdown 语法参考 |
| **工具** | Claude Code / Claw Code | AI agent 运行时 |
| **工具** | Obsidian | 知识库前端（可视化、浏览、编辑） |
| **工具** | Obsidian Local REST API 插件 | 外部工具通过 HTTP 访问 vault |

#### 工作流模板

```
llm-wiki/
├── CLAUDE.md              # 项目指令（Karpathy LLM Wiki 规范）
├── raw/                   # 原始资料收件箱（只读，处理后归档）
│   ├── 01-articles/       #   网页剪藏文章
│   ├── 02-papers/         #   论文 PDF
│   ├── 03-transcripts/    #   视频/播客转录
│   ├── 04-weread/         #   微信读书划线笔记（自动同步）
│   └── 09-archive/        #   已处理文件归档（仅追加，不读取）
├── wiki/                  # 知识编译输出层（AI 工作区）
│   ├── sources/           #   来源摘要（raw/ 一对一提炼）
│   ├── entities/          #   实体（被分析对象或独立知识生产者）
│   ├── concepts/          #   概念（框架、方法论、理论）
│   ├── syntheses/         #   综合研究（深度问题分析报告）
│   ├── index.md           #   全局内容字典
│   └── log.md             #   操作日志（追加写入）
├── assets/                # 媒体资产（图片、PDF、附件）
└── template/              # Obsidian Templater 模板
```

**CLAUDE.md 核心内容**（需放置在工作流根目录）：

```yaml
# 语言与角色
始终使用简体中文。你正在维护一个 LLM Wiki，将碎片化信息编译为高度链接的知识库。

# 目录权限
raw/（含子目录）    🔒 只读 — 原始素材，禁止修改内容。09-archive/ 禁止读取
wiki/              ✏️ 可写 — AI 专属工作区
assets/            ✏️ 可写
template/          🔒 只读

# 页面 Frontmatter 规范
---
title: "页面标题"
type: concept | entity | source | synthesis
tags: [知识标签]
sources: [关联的 raw 文件相对路径]
last_updated: YYYY-MM-DD
---

# 工作流指令
- /ingest <路径>  — 将 raw/ 文件编译到 wiki/
- /query <问题>   — 检索知识库并综合回答
- /lint           — 健康扫描
```

#### 搭建步骤

```bash
# 1. 安装 skills
git clone git@github.com:Poeagle/skills.git ~/.claude/skills

# 2. 创建项目目录
mkdir llm-wiki && cd llm-wiki
mkdir -p raw/{01-articles,02-papers,03-transcripts,04-weread,09-archive}
mkdir -p wiki/{sources,entities,concepts,syntheses}
mkdir -p assets template

# 3. 创建 CLAUDE.md
# 将上方的 CLAUDE.md 核心内容写入文件

# 4. 初始化 index.md 和 log.md
touch wiki/index.md wiki/log.md

# 5. 用 Obsidian 打开该目录作为 vault
# 安装插件：Excalidraw、Local REST API、Weread

# 6. 投喂第一条资料
# 在 raw/01-articles/ 下放入一篇文章
# 在 Claude Code 中运行 /ingest raw/01-articles/xxx.md
```

---

### 更多工作流

> 待补充：代码项目管理、写作系统、个人知识管理等。

---

## Skill 列表

### Wiki 知识管理

| 命令 | 说明 |
|------|------|
| `ingest` | 将 `raw/` 中的原始资料编译到 `wiki/`（来源摘要、实体、概念），更新索引后归档源文件 |
| `query` | 在本地 Wiki 知识库中检索并综合回答，使用双链引用标注来源 |
| `lint` | 扫描知识库健康状态：死链检测、孤儿页面、未同步索引、知识冲突 |

### Obsidian 增强

| 命令 | 说明 |
|------|------|
| `obsidian-cli` | 通过 Obsidian CLI 与运行中的 Obsidian 交互：搜索、创建、更新笔记、管理插件 |
| `obsidian-markdown` | Obsidian 风味 Markdown 语法参考，含 wikilink、callout、embed、properties |
| `obsidian-bases` | 创建和编辑 `.base` 数据库视图，含筛选、公式、摘要 |
| `obsidian-canvas-creator` | 从文本生成 Obsidian Canvas 文件，支持脑图和自由布局两种模板 |

### 可视化

| 命令 | 说明 |
|------|------|
| `excalidraw-diagram` | 从文本生成 Excalidraw 图形，支持 Obsidian/标准/动画三种输出模式 |
| `mermaid-visualizer` | 从文本生成专业 Mermaid 图表（流程图、架构图、脑图、时序图等） |

### 通用工具

| 命令 | 说明 |
|------|------|
| `defuddle` | 从网页提取纯净 Markdown，去除导航和广告，优先于 WebFetch 使用 |
| `notion` | 通过 Notion API 创建和管理页面、数据库、区块 |

## 维护

```bash
# 新增技能
mkdir -p ~/.claude/skills/<skill-name>
# 创建 SKILL.md，必要时在 scripts/ 下放辅助脚本
# git add && git commit && git push

# 删除技能
rm -rf ~/.claude/skills/<skill-name>
# git add && git commit && git push
```

## 来源

部分技能来自社区开源项目：

- [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) — defuddle, obsidian-cli, obsidian-markdown, obsidian-bases
- [axtonliu/axton-obsidian-visual-skills](https://github.com/axtonliu/axton-obsidian-visual-skills) — excalidraw-diagram, mermaid-visualizer, obsidian-canvas-creator
- 自定义 — ingest, query, lint, notion
