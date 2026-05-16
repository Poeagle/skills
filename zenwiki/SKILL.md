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
