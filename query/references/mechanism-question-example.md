# 机制类问题溯源示例：gbrain 到底是搜索原文还是 RAG

## 原始提问

用户问：gbrain 到底是搜索原文，还是 RAG，还是两者结合？并要求"看源码好好回答"。

## 正确做法

### 第 0 步：识别问题类型为"机制类"

这个问题不能用设计文档中的"混合搜索"一句话打发。用户要的是源码层面的实质性区分。

### 第 1 步：设计文档建立语境

从 `wiki/code-design/gbrain/` 的 README 和架构概览中获取：
- 项目定位：Postgres 原生知识库，混合 RAG
- 分层架构：CLI → Operations → BrainEngine → Search/Minions/Chunkers
- 粗线条数据流：hybridSearch 做向量+关键词融合

### 第 2 步：源码追溯（机制类必须执行）

**找到操作入口**：`src/core/operations.ts`

发现三个不同的操作：

1. **`name: 'search'`** (line 958) — 直接调 `engine.searchKeyword()`
   - 追溯 SQL：发现是纯 tsvector 全文检索，SELECT `cc.chunk_text`（原始文本块）

2. **`name: 'query'`** (line 1003) — 调 `hybridSearch()`
   - 追溯 `search/hybrid.ts`：并行跑 keyword（同上） + vector（embed → pgvector）
   - 通过 RRF 融合排序，boost compiled_truth 块 2x
   - **关键发现**：返回的是 `SearchResult[]`（原文块），不调 LLM
   - **进一步验证**：查看 `postgres-engine.ts` line 847 的 SQL SELECT，确认返回的字段是 `cc.chunk_text, cc.chunk_source` 等
   - **关键细节**：detail=low 时 SQL 有 `AND cc.chunk_source = 'compiled_truth'`（只有提炼后的知识）
     detail=medium 时所有都搜但 compiled_truth 权重 2x

3. **`name: 'think'`** (line 1250) — 调 `runThink()`
   - 追溯 `think/index.ts`：GATHER（4路并行检索）+ SYNTHESIZE（调用 Anthropic Claude API）
   - 真正的 RAG：检索到的证据组装成 prompt，LLM 生成带引用的综合回答
   - 还发现 Dream Cycle 会定时自动把 raw 数据用 Claude 蒸馏成 compiled_truth

**最终答案**：三层架构——search=纯搜索原文, query=混合检索原文（不调LLM）, think=真RAG

### 教训

- 设计文档说"混合搜索"时，可能意思只是向量+关键词混合，不包含 LLM 生成
- SQL 里的 WHERE 条件和权重系数是设计文档永远不会写到的关键细节
- 三个操作命令的存在本身就是最重要的答案——设计文档的"组件概览"不会告诉你哪个命令做什么
