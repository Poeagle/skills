---
name: zenwiki
description: ⛔ 硬性流程入口 — LLM Wiki (zenWiki) 操作协议。凡是涉及 wiki 内容的问题（知识问答、人物、概念、设计文档、摄入、检查），必须先读 CLAUDE.md → 再加载对应 skill，缺一不可。此 skill 本身不包含 CLUADE.md 的规则，必须读 CLAUDE.md 原文。
---

# zenWiki — Hermes 适配备注

**规则源头：`/Users/ymchen/obsidian/zenWiki/CLAUDE.md`**

当话题与 wiki 相关时，执行流程：

```
1. 读 CLAUDE.md ← 拿规则（权限、质量、引用规范）
2. 强制加载对应 skill ← 拿详细步骤（不可跳过 step 2 直接凭记忆执行）
   - 查询类问题（人物、概念、知识问答）→ 必须加载 query skill
   - /ingest 或摄入 → 必须加载 ingest skill
   - /lint → 必须加载 lint skill
3. 执行 step 2 加载的 skill 中给出的步骤
```

本 skill 不重复 CLAUDE.md 的内容，仅记录 Hermes 特有的操作备注。

## 常见陷阱

### nvwa 示例文件 ≠ 独立 skill
`nvwa/examples/` 下的文件（如 `zhang-yiming-perspective`、`paul-graham-perspective`）是 nvwa skill 的产出示例，**不是可独立加载的 skill**。用 `skill_view(name='nvwa:zhang-yiming-perspective')` 会报 "not found"。
- **正确做法**：直接 `search_files()` 在 `wiki/` 或 `raw/` 中搜索相关内容
- **或者**：用 `skill_view(name='nvwa', file_path='examples/zhang-yiming-perspective.md')` 读取文件内容
- 如果以上都找不到，走 query skill 的降级路径

## Hermes 特有备注

### 搜索命令
```bash
# 搜索 wiki 内容
search_files("<关键词>", path="/Users/ymchen/obsidian/zenWiki/wiki/", file_glob="*.md")

# 查找页面
search_files("*.md", target="files", path="/Users/ymchen/obsidian/zenWiki/wiki/")
```

### 回答格式
- 使用 [[wikilink]] 标注引用来源
- 结构化优先：表格、列表、引用块
- 连续纯段落不超过 5 行
- 必须用简体中文

### wiki/index.md
总目录，回答问题时先读此文件找相关页面。

### wiki/log.md
操作日志，任何操作后必须追加记录。

## ⚠️ 常见违规模式（Pitfalls）

### 违规 1：「我觉得我已经知道了」→ 跳过协议直接回答
**触发场景**：用户问的问题涉及 wiki 中已有的人物/概念，而模型训练数据恰好也覆盖该话题。
**后果**：回答基于训练数据而非 wiki 实际内容，可能遗漏 wiki 中的独特视角、用户个人笔记、或微信读书划线等一手素材。
**正确做法**：即使确信知道答案，也必须走完 ①读 CLAUDE.md → ②加载 query skill → ③按 skill 检索 → ④综合回答。wiki 的价值在于它包含用户自己的整理和引用，不是通用知识的重复。
**已有违规记录**：2026-05-16（回答 aiGameAgent 设计跳过 skill）、2026-05-18（回答王阳明 vs 张一鸣直接用训练数据）。

### 违规 2：用 session_search 替代 wiki 检索
**触发场景**：想快速回答，觉得 session_search 能找到相关信息。
**后果**：session_search 搜的是历史对话记录，不是 wiki 知识库。对话记录是一次性的、未编译的、缺乏结构的；wiki 是经过 /ingest 编译的结构化知识。
**正确做法**：session_search 只用于回忆「之前做过什么」，不用于回答「wiki 里关于 X 是怎么说的」。
