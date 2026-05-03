# LLM Wiki 工作流

基于 [Karpathy LLM Wiki 规范](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)，将碎片化信息编译成结构化、高度相互链接的 Obsidian 知识库。

## 效果

```
用户阅读/剪藏 → raw/ 收件箱
                  ↓
              /ingest 编译
                  ↓
              wiki/ 结构化知识
    ┌───────────┼───────────┐
    ↓           ↓           ↓
  来源摘要    实体/概念    综合研究
  (是什么)    (谁/什么)    (为什么)
```

## 需要的 skills

| skill | 用途 | 必需？ |
|-------|------|--------|
| `ingest` | 核心编译流水线：读取 raw/ → 提炼摘要 → 创建实体/概念 → 归档 | ✅ 必需 |
| `query` | 知识库深度检索与综合回答 | ✅ 必需 |
| `lint` | 健康扫描：死链、孤儿页面、未同步索引、知识冲突 | ✅ 必需 |
| `defuddle` | 从网页 URL 提取纯净 Markdown，用于外源采集 | 按需 |
| `excalidraw-diagram` | 将知识模型可视化为图表 | 按需 |
| `obsidian-markdown` | Obsidian 风味 Markdown 语法参考 | 按需 |

## 需要的工具

| 工具 | 用途 |
|------|------|
| Claude Code 或 Claw Code | AI agent 运行时 |
| Obsidian | 知识库前端（可视化浏览、编辑、图谱） |
| Obsidian Local REST API 插件 | 允许外部工具通过 HTTP 访问 vault |
| Obsidian Excalidraw 插件 | 在 Obsidian 中查看/编辑 Excalidraw 图表 |

## 使用方法

```bash
# 1. 复制工作流模板到新项目
cp -r ~/.claude/skills/workflows/llm-wiki /path/to/my-wiki
cd /path/to/my-wiki

# 2. 用 Obsidian 打开该目录作为 vault
# 3. 开始投喂资料
#    在 raw/01-articles/ 下放入文章
#    在 Claude Code 中运行 /ingest raw/01-articles/xxx.md
```

## 目录结构

```
llm-wiki/
├── CLAUDE.md              # 项目指令
├── raw/                   # 原始资料收件箱（只读，处理后归档）
│   ├── 01-articles/       # 网页剪藏文章
│   ├── 02-papers/         # 论文 PDF
│   ├── 03-transcripts/    # 视频/播客转录
│   ├── 04-weread/         # 微信读书划线笔记（自动同步）
│   └── 09-archive/        # 已处理文件归档（仅追加，不读取）
├── wiki/                  # 知识编译输出层
│   ├── sources/           # 来源摘要
│   ├── entities/          # 实体
│   ├── concepts/          # 概念
│   ├── syntheses/         # 综合研究
│   ├── index.md           # 全局内容字典
│   └── log.md             # 操作日志
└── assets/                # 媒体资产
```
