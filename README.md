# claude-skills

个人 Claude Code 技能集合。将 `~/.claude/skills/` 作为 git 仓库统一管理，所有技能全局可用。

## 使用方式

```bash
# 克隆到全局技能目录
git clone git@github.com:ymchen/claude-skills.git ~/.claude/skills

# 更新
cd ~/.claude/skills && git pull
```

Claude Code 会自动加载 `~/.claude/skills/` 下的所有技能，无需额外配置。

## 技能列表

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
# 创建 SKILL.md
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
