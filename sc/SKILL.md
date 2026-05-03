---
name: sc
description: 创建新 skill，修改和改进现有 skill，以及衡量 skill 性能。当用户想从头创建 skill、编辑或优化现有 skill、运行 eval 来测试 skill、通过方差分析评估 skill 的 benchmark 性能，或优化 skill 的描述以提高触发准确度时使用。
---

# Skill Creator

用于创建新 skill 并迭代改进它们的 skill。

总体而言，创建 skill 的流程如下：

- 确定你希望 skill 做什么，以及大致如何实现
- 编写 skill 草稿
- 创建一些测试提示词，然后在可以使用该 skill 的 Claude 上运行它们
- 帮助用户定性和定量地评估结果
  - 在后台运行的同时，起草一些定量 eval（如果没有的话）——如果有现有的，你可以直接使用，或者如果你觉得需要调整，也可以修改。然后向用户解释它们（如果已存在，则解释已有的）
  - 使用 `eval-viewer/generate_review.py` 脚本向用户展示结果供他们查看，同时也让他们查看定量指标
- 根据用户对结果的评估反馈，重写 skill（同时也要注意定量 benchmark 中暴露出的明显缺陷）
- 重复直到满意为止
- 扩展测试集，在更大规模上再次尝试

使用此 skill 时，你的任务是弄清楚用户处于此流程的哪个阶段，然后介入并帮助他们推进这些阶段。例如，用户可能会说"我想为 X 创建一个 skill"。你可以帮助他们明确需求、编写草稿、编写测试用例、确定评估方式、运行所有提示词，然后重复循环。

另一方面，如果他们已经有 skill 草稿，你可以直接进入评估/迭代环节。

当然，你应该始终保持灵活。如果用户说"我不需要跑一堆评估，跟我一起感受一下就好"，你也可以这样做。

skill 完成后（但顺序仍然可以灵活调整），你还可以运行 skill 描述优化器——我们有单独的脚本——来优化 skill 的触发效果。

明白了吗？很好。

## 与用户沟通

Skill creator 可能被各种技术背景的人使用。你可能还不知道（毕竟这是最近才开始的），现在有个趋势是 Claude 的强大功能正在激励水管工打开终端，父母和祖父母去谷歌搜索"如何安装 npm"。另一方面，大部分用户可能对计算机相当熟悉。

所以请注意上下文线索，来调整你的沟通方式！在默认情况下，给你一些参考：

- "evaluation（评估）"和"benchmark（基准测试）"属于边界词汇，但可以使用
- 对于"JSON"和"assertion（断言）"，你需要看到用户有明显的线索表明他们知道这些概念后，才可以在不解释的情况下使用

如果拿不准，简要解释一下术语是可以的。如果你不确定用户是否能理解，随时可以用简短的定义澄清术语。

---

## 创建 skill

### 捕获意图

首先理解用户的意图。当前对话可能已经包含了用户想要捕获的工作流程（例如，用户说"把这个变成 skill"）。如果是这样，先从对话历史中提取答案——使用的工具、步骤顺序、用户所做的修正、观察到的输入/输出格式。用户可能需要补充缺失的信息，并且应在进入下一步之前确认。

1. 此 skill 应使 Claude 能够做什么？
2. 此 skill 何时应触发？（什么用户短语/上下文）
3. 预期的输出格式是什么？
4. 我们是否应该设置测试用例来验证 skill 是否正常工作？具有客观可验证输出的 skill（文件转换、数据提取、代码生成、固定工作流步骤）受益于测试用例。具有主观输出的 skill（写作风格、艺术）通常不需要。根据 skill 类型建议适当的默认方案，但让用户决定。

### 访谈与研究

主动询问关于边界情况、输入/输出格式、示例文件、成功标准和依赖项的问题。在把这一部分敲定之前，先不要编写测试提示词。

检查可用的 MCP——如果对研究有用（搜索文档、查找类似 skill、查找最佳实践），如果可用的话可以通过 subagent（子代理）并行研究，否则内联进行。带着上下文来减轻用户的负担。

### 编写 SKILL.md

根据用户访谈，填写以下组件：

- **name**：Skill 标识符
- **description**：何时触发、做什么。这是主要的触发机制——既包括 skill 做什么，也包括何时使用的具体上下文。所有"何时使用"的信息都放在这里，而不是正文中。注意：当前 Claude 有"触发不足"的倾向——在有用的情况下不去使用 skill。为了解决这个问题，请让 skill 描述稍微"主动"一些。例如，不要写"如何构建一个简单的快速仪表板来显示 Anthropic 内部数据"，而应该写"如何构建一个简单的快速仪表板来显示 Anthropic 内部数据。当用户提到仪表板、数据可视化、内部指标或想展示任何类型的公司数据时，即使他们没有明确要求'dashboard'，也请务必使用此 skill。"
- **compatibility**：所需的工具、依赖项（可选，很少需要）
- **skill 的其余内容 :)**

### Skill 编写指南

#### Skill 的结构

```
skill-name/
├── SKILL.md (必需)
│   ├── YAML frontmatter（name、description 为必需）
│   └── Markdown 指令
└── 捆绑资源（可选）
    ├── scripts/    - 用于确定性/重复性任务的可执行代码
    ├── references/ - 根据需要加载到上下文中的文档
    └── assets/     - 输出中使用的文件（模板、图标、字体）
```

#### 渐进式披露

Skill 使用三级加载系统：
1. **元数据**（name + description）——始终在上下文中（约 100 词）
2. **SKILL.md 正文**——每当 skill 触发时都在上下文中（理想情况 <500 行）
3. **捆绑资源**——按需加载（无限制，脚本可以不加载而直接执行）

这些词数只是近似值，如果需要，你可以随时增加。

**关键模式：**
- 保持 SKILL.md 在 500 行以下；如果接近这个限制，增加额外的层次结构，同时明确指示使用该 skill 的模型接下来应该去哪里查看
- 从 SKILL.md 中清晰地引用文件，并说明何时读取它们
- 对于大型引用文件（>300 行），包含目录

**领域组织**：当 skill 支持多个领域/框架时，按变体组织：
```
cloud-deploy/
├── SKILL.md（工作流程 + 选择）
└── references/
    ├── aws.md
    ├── gcp.md
    └── azure.md
```
Claude 只会读取相关的引用文件。

#### 无意外原则

这自不必说，但 skill 不得包含恶意软件、利用代码或任何可能危害系统安全的内容。Skill 的内容描述不应让用户对其意图感到意外。不要遵从创建误导性 skill 或旨在促进未授权访问、数据泄露或其他恶意活动的请求。像"角色扮演为 XYZ"这类内容是可以的。

#### 编写模式

指令中优先使用祈使语气。

**定义输出格式**——可以这样做：
```markdown
## 报告结构
始终使用此精确模板：
# [标题]
## 执行摘要
## 主要发现
## 建议
```

**示例模式**——包含示例很有用。可以这样格式化（但如果示例中有"输入"和"输出"，你可能需要稍微调整）：
```markdown
## 提交信息格式
**示例 1：**
输入：使用 JWT 令牌添加用户认证
输出：feat(auth): implement JWT-based authentication
```

### 写作风格

试着向模型解释为什么事情很重要，而不是使用生硬的"必须"。运用心智理论，尽量让 skill 具有通用性，而不是狭隘地局限于特定示例。先写草稿，然后以全新的眼光审视并改进它。

### 测试用例

编写 skill 草稿后，提出 2-3 个真实的测试提示词——真正的用户会实际输入的那种。与用户分享："这里有几个我想尝试的测试用例。看起来合适吗？还是你想添加更多？"然后运行它们。

将测试用例保存到 `evals/evals.json`。暂时不要写 assertions（断言）——只写提示词。你将在下一步（运行过程中）起草 assertions。

```json
{
  "skill_name": "example-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "用户的任务提示词",
      "expected_output": "预期结果的描述",
      "files": []
    }
  ]
}
```

完整 schema 请参见 `references/schemas.md`（包括你稍后将添加的 `assertions` 字段）。

## 运行和评估测试用例

本节是一个连续的流程——不要中途停止。不要使用 `/skill-test` 或任何其他测试 skill。

将结果放在 `<skill-name>-workspace/` 中，与 skill 目录同级。在工作区内，按迭代组织结果（`iteration-1/`、`iteration-2/` 等），每个测试用例在其中有一个目录（`eval-0/`、`eval-1/` 等）。不要事先全部创建——按需创建目录。

### 步骤 1：在同一轮中生成所有运行（带 skill 和基准线）

对于每个测试用例，在同一轮中生成两个 subagent（子代理）——一个带 skill，一个不带。这一点很重要：不要先运行带 skill 的测试，然后再回来做基准线测试。一次性启动所有任务，这样它们大约在同一时间完成。

**带 skill 的运行：**

```
执行此任务：
- Skill 路径：<path-to-skill>
- 任务：<eval prompt>
- 输入文件：<eval files if any, or "none">
- 保存输出到：<workspace>/iteration-<N>/eval-<ID>/with_skill/outputs/
- 要保存的输出：<用户关心的内容——例如 ".docx 文件"、"最终的 CSV">
```

**基准线运行**（相同的提示词，但基准线取决于上下文）：
- **创建新 skill**：不使用任何 skill。相同提示词，没有 skill 路径，保存到 `without_skill/outputs/`。
- **改进现有 skill**：使用旧版本。在编辑之前，快照 skill（`cp -r <skill-path> <workspace>/skill-snapshot/`），然后将基准线 subagent 指向快照。保存到 `old_skill/outputs/`。

为每个测试用例编写一个 `eval_metadata.json`（assertions 暂时可以为空）。根据测试的内容给每个 eval 起一个描述性名称——不要只是"eval-0"。目录也使用这个名称。如果本次迭代使用新的或修改过的 eval 提示词，为每个新的 eval 目录创建这些文件——不要假设它们会从之前的迭代继承。

```json
{
  "eval_id": 0,
  "eval_name": "descriptive-name-here",
  "prompt": "用户的任务提示词",
  "assertions": []
}
```

### 步骤 2：在运行进行期间，起草 assertions

不要只是等待运行完成——你可以高效地利用这段时间。为每个测试用例起草定量 assertions，并向用户解释。如果 `evals/evals.json` 中已经存在 assertions，请审查它们并解释它们检查什么。

好的 assertions 是客观可验证的，并且具有描述性名称——它们应该在 benchmark 查看器中清晰可读，以便浏览结果的人能立即理解每个 assertion 检查的是什么。主观性 skill（写作风格、设计质量）更适合定性评估——不要强行对需要人类判断的内容使用 assertions。

起草完成后，更新 `eval_metadata.json` 文件和 `evals/evals.json`，加入 assertions。同时向用户解释他们将在查看器中看到什么——包括定性输出和定量 benchmark。

### 步骤 3：随着运行完成，捕获计时数据

当每个 subagent 任务完成时，你会收到包含 `total_tokens` 和 `duration_ms` 的通知。立即将此数据保存到运行目录中的 `timing.json`：

```json
{
  "total_tokens": 84852,
  "duration_ms": 23332,
  "total_duration_seconds": 23.3
}
```

这是捕获此数据的唯一机会——它通过任务通知传递，不会在其他地方持久化。逐条处理每个通知，而不是尝试批量处理。

### 步骤 4：评分、汇总并启动查看器

当所有运行完成后：

1. **对每次运行评分**——生成一个 grader subagent（或内联评分），读取 `agents/grader.md` 并根据输出评估每个 assertion。将结果保存到每个运行目录的 `grading.json` 中。grading.json 的 expectations 数组必须使用字段 `text`、`passed` 和 `evidence`（而不是 `name`/`met`/`details` 或其他变体）——查看器依赖于这些确切的字段名。对于可以编程检查的 assertions，编写并运行脚本，而不是人工目测——脚本更快、更可靠，并且可以在迭代中重复使用。

2. **汇总到 benchmark**——从 skill-creator 目录运行汇总脚本：
   ```bash
   python -m scripts.aggregate_benchmark <workspace>/iteration-N --skill-name <name>
   ```
   这将生成 `benchmark.json` 和 `benchmark.md`，包含每次配置的通过率、时间和 token 数，带有均值 ± 标准差和差异值。如果手动生成 benchmark.json，请查阅 `references/schemas.md` 了解查看器所需的确切 schema。
   将每个 with_skill 版本放在其基准线版本之前。

3. **进行分析师检查**——阅读 benchmark 数据，找出汇总统计可能隐藏的模式。参见 `agents/analyzer.md`（"分析 Benchmark 结果"部分）了解要查找的内容——例如无论是否有 skill 总是通过的 assertion（非区分性）、高方差 eval（可能不稳定），以及时间/token 的权衡。

4. **启动查看器**，包含定性输出和定量数据：
   ```bash
   nohup python <skill-creator-path>/eval-viewer/generate_review.py \
     <workspace>/iteration-N \
     --skill-name "my-skill" \
     --benchmark <workspace>/iteration-N/benchmark.json \
     > /dev/null 2>&1 &
   VIEWER_PID=$!
   ```
   对于第 2 次及以后的迭代，额外传入 `--previous-workspace <workspace>/iteration-<N-1>`。

   **Cowork / 无头环境**：如果 `webbrowser.open()` 不可用或环境没有显示器，使用 `--static <output_path>` 写入独立的 HTML 文件，而不是启动服务器。当用户点击"提交所有评论"时，反馈将作为 `feedback.json` 文件下载。下载后，将 `feedback.json` 复制到工作区目录中，供下一次迭代使用。

   注意：请使用 generate_review.py 创建查看器，无需编写自定义 HTML。

5. **告诉用户**类似这样的话："我已经在浏览器中打开了结果。有两个标签页——'输出'可以让你逐个查看每个测试用例并留下反馈，'基准测试'显示定量对比。完成后回到这里告诉我。"

### 用户在查看器中看到的内容

"输出"标签页一次显示一个测试用例：
- **提示词**：给出的任务
- **输出**：skill 产生的文件，尽可能内联渲染
- **之前的输出**（第 2 次及以后迭代）：折叠区域，显示上一次迭代的输出
- **正式评分**（如果运行了评分）：折叠区域，显示 assertion 通过/失败
- **反馈**：文本框，输入时自动保存
- **之前的反馈**（第 2 次及以后迭代）：用户上次的评论，显示在文本框下方

"基准测试"标签页显示统计摘要：每次配置的通过率、时间和 token 使用情况，以及每个 eval 的细分和分析师观察。

通过上一个/下一个按钮或箭头键导航。完成后，他们点击"提交所有评论"，将所有反馈保存到 `feedback.json`。

### 步骤 5：读取反馈

当用户告诉你他们完成后，读取 `feedback.json`：

```json
{
  "reviews": [
    {"run_id": "eval-0-with_skill", "feedback": "图表缺少坐标轴标签", "timestamp": "..."},
    {"run_id": "eval-1-with_skill", "feedback": "", "timestamp": "..."},
    {"run_id": "eval-2-with_skill", "feedback": "完美，非常喜欢", "timestamp": "..."}
  ],
  "status": "complete"
}
```

空反馈意味着用户认为没问题。将改进重点放在用户提出具体意见的测试用例上。

完成后关闭查看器服务器：

```bash
kill $VIEWER_PID 2>/dev/null
```

---

## 改进 skill

这是循环的核心。你已经运行了测试用例，用户已经审查了结果，现在你需要根据他们的反馈来改进 skill。

### 如何思考改进

1. **从反馈中概括。** 大局观是：我们正在努力创建可以被使用一百万次（也许真的有一百万次，甚至更多谁知道呢）的 skill，跨越许多不同的提示词。在这里，你和用户只在少数几个例子上反复迭代，因为这有助于加快速度。用户对这些例子了如指掌，他们可以快速评估新的输出。但如果你和用户共同开发的 skill 只适用于这些例子，那它就是无用的。不要做过于琐碎或过度拟合的改动，也不要添加压迫性的"必须"规则。如果遇到某个顽固问题，你可以尝试拓展思路，使用不同的隐喻，或推荐不同的工作模式。尝试的成本相对较低，也许你会找到很好的方案。

2. **保持提示词精简。** 删除那些没有发挥作用的内容。确保阅读对话记录，而不仅仅是最终输出——如果看起来 skill 让模型浪费了大量时间做无益的事情，你可以尝试删除导致这种情况的 skill 部分，看看效果。

3. **解释原因。** 尽力解释你要求模型做的每件事背后的**原因**。今天的 LLM 非常*聪明*。它们有良好的心智理论，当给予良好的引导时，它们可以超越死记硬背的指令，真正实现目标。即使来自用户的反馈很简短或带着挫败感，也要努力真正理解任务以及用户为什么写那些内容，他们实际写了什么，然后将这种理解传递到指令中。如果你发现自己在写全大写的 ALWAYS 或 NEVER，或者使用过于刻板的结构，那是一个警示信号——如果可能，重新组织并解释推理过程，让模型理解为什么你要求的事情很重要。这是一种更人性化、更强大、更有效的方法。

4. **寻找跨测试用例的重复工作。** 阅读测试运行的记录，注意 subagent 是否都独立编写了类似的辅助脚本，或者对某件事采用了相同的多步骤方法。如果所有 3 个测试用例都导致 subagent 编写了 `create_docx.py` 或 `build_chart.py`，这是一个强烈的信号，表明 skill 应该捆绑该脚本。编写一次，放入 `scripts/` 中，并告诉 skill 使用它。这可以节省未来每次调用时重新发明轮子的时间。

这项任务相当重要（我们正在努力创造数十亿美元的年经济价值！），你的思考时间不是瓶颈；慢慢来，仔细权衡。我建议编写一份修订草稿，然后重新审视并做出改进。尽最大努力站在用户的角度，理解他们想要什么、需要什么。

### 迭代循环

改进 skill 后：

1. 将你的改进应用到 skill 上
2. 将所有测试用例重新运行到新的 `iteration-<N+1>/` 目录中，包括基准线运行。如果你在创建新 skill，基准线始终是 `without_skill`（无 skill）——这在各次迭代中保持不变。如果你在改进现有 skill，根据你的判断来决定什么是合适的基准线：用户最初带来的原始版本，还是上一次迭代的版本。
3. 使用 `--previous-workspace` 指向上一次迭代来启动查看器
4. 等待用户审查并告诉你他们完成了
5. 读取新反馈，再次改进，重复

持续进行直到：
- 用户表示满意
- 反馈全部为空（一切看起来都不错）
- 你不再取得有意义的进展

---

## 高级：盲测对比

对于需要对两个 skill 版本进行更严格比较的情况（例如，用户问"新版本真的更好吗？"），有一个盲测对比系统。阅读 `agents/comparator.md` 和 `agents/analyzer.md` 了解详情。基本思路是：将两个输出交给一个独立的 agent，不告诉它哪个是哪个，让它评判质量。然后分析赢家为什么赢了。

这是可选的，需要 subagent，大多数用户不需要。人工审查循环通常就足够了。

---

## 描述优化

SKILL.md frontmatter 中的 description 字段是决定 Claude 是否调用 skill 的主要机制。在创建或改进 skill 后，主动提出优化描述以提高触发准确度。

### 步骤 1：生成触发 eval 查询

创建 20 个 eval 查询——混合应触发和不应触发的场景。保存为 JSON：

```json
[
  {"query": "用户提示词", "should_trigger": true},
  {"query": "另一个提示词", "should_trigger": false}
]
```

查询必须真实，并且是 Claude Code 或 Claude.ai 用户会实际输入的内容。不是抽象请求，而是具体、详细且信息量充足的请求。例如，文件路径、关于用户工作或情况的个人背景、列名和值、公司名称、URL。一点背景故事。有些可能是小写或包含缩写、拼写错误或口语化表达。使用不同长度的混合，并关注边界情况，而不是让它们显而易见（用户将有机会确认）。

不好的例子：`"格式化这些数据"`、`"从 PDF 提取文本"`、`"创建图表"`

好的例子：`"ok so my boss just sent me this xlsx file (its in my downloads, called something like 'Q4 sales final FINAL v2.xlsx') and she wants me to add a column that shows the profit margin as a percentage. The revenue is in column C and costs are in column D i think"`

对于 **应触发** 的查询（8-10 个），考虑覆盖率。你需要同一意图的不同措辞——有些正式，有些随意。包括用户没有明确提到 skill 名称或文件类型但显然需要它的情况。加入一些不常见的用例，以及此 skill 与另一个 skill 竞争但应胜出的情况。

对于 **不应触发** 的查询（8-10 个），最有价值的是那些"擦边球"——与 skill 共享关键词或概念但实际上需要不同内容的查询。考虑相邻领域、模糊措辞（天真的关键词匹配会触发但不应该触发）以及查询涉及 skill 能做的事情但上下文更适合其他工具的情况。

需要避免的关键点：不要让不应触发的查询明显不相关。对 PDF skill 来说，把"写一个斐波那契函数"作为负面测试太容易了——它测试不了什么。负面案例应该真正具有迷惑性。

### 步骤 2：与用户一起审查

使用 HTML 模板向用户展示 eval 集供审查：

1. 从 `assets/eval_review.html` 读取模板
2. 替换占位符：
   - `__EVAL_DATA_PLACEHOLDER__` → eval 项的 JSON 数组（周围不要加引号——它是一个 JS 变量赋值）
   - `__SKILL_NAME_PLACEHOLDER__` → skill 的名称
   - `__SKILL_DESCRIPTION_PLACEHOLDER__` → skill 的当前描述
3. 写入临时文件（例如 `/tmp/eval_review_<skill-name>.html`）并打开它：`open /tmp/eval_review_<skill-name>.html`
4. 用户可以编辑查询、切换应触发/不应触发、添加/删除条目，然后点击"导出 Eval 集"
5. 文件下载到 `~/Downloads/eval_set.json`——检查 Downloads 文件夹中最近的版本，以防有多个（例如 `eval_set (1).json`）

这一步很重要——糟糕的 eval 查询会导致糟糕的描述。

### 步骤 3：运行优化循环

告诉用户："这需要一些时间——我会在后台运行优化循环，并定期检查进度。"

将 eval 集保存到工作区，然后在后台运行：

```bash
python -m scripts.run_loop \
  --eval-set <path-to-trigger-eval.json> \
  --skill-path <path-to-skill> \
  --model <model-id-powering-this-session> \
  --max-iterations 5 \
  --verbose
```

使用系统提示词中的模型 ID（为当前会话提供算力的模型），以便触发测试与用户实际体验一致。

在运行时，定期查看输出，向用户更新当前处于哪次迭代以及分数情况。

这会自动处理完整的优化循环。它将 eval 集按 60% 训练和 40% 保留测试进行拆分，评估当前描述（每次查询运行 3 次以获得可靠的触发率），然后根据失败情况调用 Claude 提出改进建议。它会在训练集和测试集上重新评估每个新描述，最多迭代 5 次。完成后，它会在浏览器中打开一份 HTML 报告，显示每次迭代的结果，并返回包含 `best_description` 的 JSON——选择依据是测试分数而非训练分数，以避免过拟合。

### Skill 触发的工作原理

理解触发机制有助于设计更好的 eval 查询。Skill 以其名称 + 描述出现在 Claude 的 `available_skills` 列表中，Claude 根据描述决定是否查阅 skill。需要知道的重要一点是：Claude 只会在难以自行处理的任务上查阅 skill——简单的、一步到位的查询（如"读取这个 PDF"）即使描述完美匹配也可能不会触发 skill，因为 Claude 可以直接使用基本工具处理它们。复杂、多步骤或专业化的查询在描述匹配时能可靠地触发 skill。

这意味着你的 eval 查询应该足够充实，使 Claude 真正受益于查阅 skill。像"读取文件 X"这样的简单查询是糟糕的测试用例——它们不会触发 skill，无论描述质量如何。

### 步骤 4：应用结果

从 JSON 输出中获取 `best_description`，并更新 skill 的 SKILL.md frontmatter。向用户展示前后对比，并报告分数。

---

### 打包和展示（仅当 `present_files` 工具可用时）

检查你是否拥有 `present_files` 工具的访问权限。如果没有，跳过此步骤。如果有，打包 skill 并向用户展示 .skill 文件：

```bash
python -m scripts.package_skill <path/to/skill-folder>
```

打包后，将生成的 `.skill` 文件路径告知用户，以便他们安装。

---

## Claude.ai 专用说明

在 Claude.ai 中，核心工作流程相同（草稿 → 测试 → 审查 → 改进 → 重复），但由于 Claude.ai 没有 subagent，一些操作细节有所不同。以下是需要调整的地方：

**运行测试用例**：没有 subagent 意味着无法并行执行。对于每个测试用例，读取 skill 的 SKILL.md，然后按照其指令自行完成测试提示词。逐个进行。这比独立的 subagent 更不严谨（你编写了 skill 也在运行它，所以你拥有完整的上下文），但它是一个有用的合理性检查——而且人工审查步骤可以弥补。跳过基准线运行——只需使用 skill 按要求完成任务。

**审查结果**：如果无法打开浏览器（例如，Claude.ai 的 VM 没有显示器，或者你在远程服务器上），完全跳过浏览器查看器。相反，直接在对话中呈现结果。对于每个测试用例，显示提示词和输出。如果输出是用户需要看到的文件（如 .docx 或 .xlsx），保存到文件系统并告诉他们位置，以便下载和检查。内联征求反馈："这个看起来怎么样？有什么需要修改的吗？"

**基准测试**：跳过定量基准测试——它依赖于基准线比较，而没有 subagent 的话基准线比较没有意义。专注于来自用户的定性反馈。

**迭代循环**：与之前相同——改进 skill，重新运行测试用例，征求反馈——只是中间没有浏览器查看器。如果你有文件系统，仍然可以将结果组织到迭代目录中。

**描述优化**：本节需要 `claude` CLI 工具（具体是 `claude -p`），该工具仅在 Claude Code 中可用。如果你在 Claude.ai 上，请跳过。

**盲测对比**：需要 subagent。跳过。

**打包**：`package_skill.py` 脚本可以在任何有 Python 和文件系统的地方运行。在 Claude.ai 上，你可以运行它，用户可以下载生成的 `.skill` 文件。

**更新现有 skill**：用户可能要求你更新现有 skill，而不是创建新的。在这种情况下：
- **保留原始名称。** 注意 skill 的目录名称和 `name` frontmatter 字段——保持原样。例如，如果已安装的 skill 是 `research-helper`，输出应为 `research-helper.skill`（而不是 `research-helper-v2`）。
- **在编辑前复制到可写位置。** 已安装的 skill 路径可能是只读的。复制到 `/tmp/skill-name/`，在那里编辑，然后从副本打包。
- **如果手动打包，先在 `/tmp/` 中暂存**，然后复制到输出目录——直接写入可能因权限而失败。

---

## Cowork 专用说明

如果你在 Cowork 中，主要需要了解以下几点：

- 你有 subagent，所以主工作流程（并行生成测试用例、运行基准线、评分等）都可以工作。（但是，如果遇到严重的超时问题，串行运行测试提示词也是可以的。）
- 你没有浏览器或显示器，所以在生成 eval 查看器时，使用 `--static <output_path>` 写入独立的 HTML 文件，而不是启动服务器。然后提供一个用户可以点击的链接，在浏览器中打开 HTML。
- 出于某种原因，Cowork 环境似乎会让 Claude 在运行测试后不生成 eval 查看器，所以重申一下：无论你在 Cowork 还是 Claude Code 中，在运行测试后，你应该始终生成 eval 查看器让人查看示例，然后才能自己评估 skill 并尝试做修正——使用 `generate_review.py`（而不是编写自己的特制 HTML 代码）。提前抱歉，但这里我要全大写强调：在你自己评估输入之前，*先*生成 EVAL 查看器。你要尽快把结果呈现在人面前！
- 反馈的工作方式不同：由于没有运行中的服务器，查看器的"提交所有评论"按钮会将 `feedback.json` 作为文件下载。然后你可以从那里读取它（你可能需要先请求访问权限）。
- 打包可以正常工作——`package_skill.py` 只需要 Python 和文件系统。
- 描述优化（`run_loop.py` / `run_eval.py`）在 Cowork 中应该可以正常工作，因为它通过子进程使用 `claude -p`，而不是浏览器，但请等到你完全完成 skill 制作并且用户确认状态良好后再进行。
- **更新现有 skill**：用户可能要求你更新现有 skill，而不是创建新的。遵循上面 Claude.ai 部分的更新指南。

---

## 引用文件

`agents/` 目录包含专用 subagent 的指令。当需要生成相关 subagent 时读取它们。

- `agents/grader.md` — 如何评估 assertions 与输出的匹配情况
- `agents/comparator.md` — 如何在两个输出之间进行盲测 A/B 比较
- `agents/analyzer.md` — 如何分析一个版本为何胜过另一个

`references/` 目录有额外的文档：
- `references/schemas.md` — evals.json、grading.json 等的 JSON 结构

---

再次强调这里的核心循环：

- 弄清楚 skill 是关于什么的
- 草稿或编辑 skill
- 在测试提示词上运行可以使用该 skill 的 Claude
- 与用户一起评估输出：
  - 创建 benchmark.json 并运行 `eval-viewer/generate_review.py` 帮助用户审查
  - 运行定量 eval
- 重复直到你和用户都满意
- 打包最终 skill 并返回给用户。

如果你有 TodoList 这样的工具，请将步骤添加到其中，以确保你不会忘记。如果你在 Cowork 中，请特别将"创建 evals JSON 并运行 `eval-viewer/generate_review.py` 以便人类可以审查测试用例"放入你的 TodoList 中，确保它被执行。

祝你好运！
