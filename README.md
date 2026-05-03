# Skills

个人 Claude Code / Claw Code 技能集合，托管在 `~/.claude/skills/`。

```bash
git clone git@github.com:Poeagle/skills.git ~/.claude/skills
```

## 工作流

| 工作流 | 说明 |
|--------|------|
| [LLM Wiki](workflows/llm-wiki) | 将碎片化信息编译为结构化、高度相互链接的 Obsidian 知识库 |

> 每个工作流目录下有完整的项目模板（CLAUDE.md + 目录骨架）和使用指南。

## Skill 列表

| 命令 | 类别 | 功能 |
|------|------|------|
| `ingest` | 核心 | 将 raw/ 源文件编译到 wiki/（来源摘要、实体、概念），更新索引后归档 |
| `query` | 核心 | 知识库检索与综合回答，双链引用标注来源 |
| `lint` | 核心 | 健康扫描：死链检测、孤儿页面、未同步索引、知识冲突 |
| `obsidian-cli` | 工具 | 通过 CLI 与运行中的 Obsidian 交互（搜索、创建、管理笔记） |
| `obsidian-markdown` | 参考 | Obsidian 风味 Markdown 语法参考 |
| `obsidian-bases` | 工具 | 创建和编辑 .base 数据库视图 |
| `obsidian-canvas-creator` | 工具 | 从文本生成 Canvas 文件 |
| `excalidraw-diagram` | 工具 | 生成 Excalidraw 图形（Obsidian/标准/动画三种输出） |
| `mermaid-visualizer` | 工具 | 生成专业 Mermaid 图表 |
| `defuddle` | 工具 | 从网页提取纯净 Markdown |
| `notion` | 工具 | Notion API 页面和数据库管理 |

## 维护

```bash
# 新增 skill
mkdir -p ~/.claude/skills/<name>
# 创建 SKILL.md
# git add && git commit && git push

# 删除 skill
rm -rf ~/.claude/skills/<name>
# git add && git commit && git push
```

## 来源

部分 skills 来自社区开源项目：

- [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) — defuddle, obsidian-cli, obsidian-markdown, obsidian-bases
- [axtonliu/axton-obsidian-visual-skills](https://github.com/axtonliu/axton-obsidian-visual-skills) — excalidraw-diagram, mermaid-visualizer, obsidian-canvas-creator
