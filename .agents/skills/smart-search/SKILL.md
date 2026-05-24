---
name: smart-search
description: 基于 opencli 命令的智能搜索路由器。当用户想要使用 OpenCLI、CLI 或 API 搜索、查询、查找或研究信息时，尤其是涉及指定网站、社交媒体、技术资料、新闻、购物、旅游、求职、金融或中文内容时，务必使用此 skill
---

# 智能搜索路由器

根据话题和场景，将查询路由到最佳的 opencli 搜索源。此 skill 的核心目标不是记忆命令，而是先定位数据源，再让 Agent 通过 `opencli` 自己读取实时帮助，避免文档漂移。

## 强制预检

每次使用前，必须先做下面两步：

- 运行 `opencli list -f yaml`
- 用 live registry 确认候选站点是否存在，并检查 `strategy`、`browser`、`domain`

选定站点后，必须再做下面两步：

- 运行 `opencli <site> -h` 查看该站点有哪些子命令
- 若已锁定某个子命令，再运行 `opencli <site> <command> -h` 查看参数、输出列、策略

不要在 skill 文档里硬编码参数或假设命令签名；以 `opencli ... -h` 的实时输出为准。

## 主路由规则

只使用这一条规则，不再维护多套优先级：

1. 当用户明确指定网站、平台或数据源时，直接使用对应网站。
2. 当用户没有指定网站时，优先只选择一个 AI 源：`grok`、`doubao`、`gemini` 三选一。
3. 当 AI 返回内容不足、缺少原始数据、需要权威佐证或需要垂直结果时，再补充 1-2 个专用源。

## 单题预算与频率限制

把“单个用户问题”理解为同一意图链路下的一次问题求解；同一轮追问、澄清、补充条件，若核心问题未变，仍算同一题。

先建立一份站点调用台账。每次真正执行搜索命令后，立刻更新：

- `site`
- `query`
- `count`
- `status`

计数规则：

- `opencli list -f yaml`、`opencli <site> -h`、`opencli <site> <command> -h` 属于预检与帮助，不计入搜索次数
- 一次真正的 `opencli <site> ...` 搜索/查询执行，计为该站点 1 次调用
- 同站点因为报错、超时、验证码、反爬、登录态异常而失败，也算 1 次调用，不要无限重试

频率上限：

- AI 站点硬限制：同一题内，每个 AI 站点最多调用 1 次
- 默认策略仍然是只选 1 个 AI 站点，不要把多个 AI 站点串成常规流程
- 只有当用户明确要求比较多个 AI 站点时，才可以额外调用其他 AI 站点；但每个被点名的 AI 站点仍然最多 1 次
- 非 AI 站点默认最多调用 2 次
- 非 AI 站点第 2 次调用必须有明确理由，例如第一次结果过宽，需要加时间、地区、类别、排序或关键词限定
- 非 AI 站点不要进行第 3 次调用；若信息仍不足，停止扩搜并明确说明缺口

触发限频后的处理：

- 记录：「已跳过：<site> 达到频率上限」
- 优先改用其他同类站点
- 若没有合适替代源，则直接基于已收集信息回答，并说明覆盖范围与缺口

## 浏览器 Session 清理（强制）

⚠️ 用户明确要求：**不能留下残余标签页影响正常浏览。**

`--window background` 只是不抢焦点，**标签页仍然会打开**。必须主动关闭。

规则：

- **COOKIE/INTERCEPT/UI 适配器搜索**：加 `--site-session ephemeral`，用完自动关标签
  ```bash
  opencli xiaohongshu search "关键词" --window background --site-session ephemeral -f json
  ```
- **`opencli browser <session> bind`**：用完后必须 `unbind`
  ```bash
  opencli browser yt-history bind
  # ... 读取数据 ...
  opencli browser yt-history unbind
  ```
- **`opencli browser <session> open`**：用完后必须 `close`
  ```bash
  opencli browser my-session open "https://..."
  # ... 操作 ...
  opencli browser my-session close
  ```
- **多个 session 时**：每个都要单独关闭，不要遗漏

错误示范（用户会投诉）：
```bash
opencli xiaohongshu search "xxx" --window background -f json
# 没有 --site-session ephemeral → 残留标签
```

## 查询结束汇报

每次查询结束后，回答末尾必须追加一段简短的“搜索摘要”，至少包含下面三项：

- 使用了什么网站搜索
- 每个网站搜了什么词
- 每个网站搜了几次

如果有被限频跳过的站点，也要明确写出。

建议使用下面的固定格式：

```md
搜索摘要
- 网站：<site1> | 查询词：<term1> | 次数：<n>
- 网站：<site2> | 查询词：<term2>；<term3> | 次数：<n>
- 已跳过：<site3>，原因：达到频率上限
```

## AI 源选择

- `grok`
  适合实时讨论、英文互联网舆论、Twitter/X 语境、热点追踪。
- `doubao`
  适合中文语境、字节抖音生态、生活方式内容、中文热点与泛中文问答。
- `gemini`
  适合全球网页、英文资料、通用信息检索、背景综述。

如果用户没有指定网站，默认先判断语言和语境，再从这三个里只选一个。

一旦某个 AI 站点已经执行过一次真实查询，就不要在同一题里改写关键词后再次调用该 AI 站点。若答案不足，优先补专用源，不要反复追打同一个 AI 站点。

## 实时性查询 / 服务状态检查

当用户询问 "现在 X 有问题吗"、"X 是不是挂了"、"目前 X 的情况" 等实时状态类问题时，遵循以下流程：

### 流程

1. **查官方状态页**（如有）— 这是最权威的实时运行状态
   - Anthropic/Claude: `status.claude.com`
   - OpenAI: `status.openai.com`
   - GitHub: `www.githubstatus.com`
   - 以此类推

2. **搜社交媒体** — 用户报告的作用域补充
   - X/Twitter: 搜 `"<service> down" 或 "<service> issue"`，关注最近 24h 帖子
   - 小红书: 搜 `"<服务名> 问题 故障 宕机"`，注意用发布时间过滤
   - Reddit: `opencli reddit search`，排在 `r/<service>` 内

3. **交叉验证** — 不要把单一平台的抱怨当作 "官方有问题"
   - 一条热帖 ≠ 大规模宕机
   - 如果官方状态页显示 Operational，但社交媒体大面积抱怨 → 可能是局部或 account-specific 问题
   - 如果官方状态页显示 Degraded/Major Outage → 确认信息

### 搜索词中的时间约束

"现在" 类查询的搜索词应 **明确包含时间维度**，不要只丢关键词：

- 加词：`"Claude Code 宕机 今天"`、`"Claude Code issue 2026"`、`"Claude Code bug 最近"`
- 主动按发布时间排序或过滤：从搜索结果中只看最近 1-3 天的
- 不要混合展示几周前的旧帖和新帖而不做区分

### 汇报结构

对于状态检查类查询，回答应包含三层：

1. **官方状态**：什么级别（Operational / Degraded / Outage）
2. **用户反馈**：社交媒体上多少人报类似问题、什么表现
3. **对你的影响评估**：简短判断是否是你会遇到的

## AI 查询词建议

当使用 AI 源时，不要只丢一个过短关键词。优先构造成“主题 + 目标 + 限定条件”的查询。

- 主题
  用户真正要查的对象、事件、产品、人物、公司、技术名词。
- 目标
  想要什么结果，例如总结、对比、原因、趋势、推荐、原始线索。
- 限定条件
  语言、地区、时间范围、平台范围、受众、价格带、岗位地点、是否要引用原始来源。

优先使用下面这种表达方式：

- `<主题> + <你要回答的问题>`
- `<主题> + <时间范围/地区/语言>`
- `<主题> + <平台或来源范围>`
- `<主题> + <输出要求>`

避免只输入：

- 单个名词
- 没有时间范围的热点问题
- 没有地区限制的购物、求职、旅游问题
- 没有平台限制的社交媒体问题

## 专用源补充时机

当出现以下任一情况时，再补充专用源：

- AI 给出的是摘要，但你需要原始帖子、原始视频、原始商品或原始职位结果
- AI 覆盖面不足，漏掉垂直站点信息
- 需要更高权威性或更强领域相关性
- 用户明确要求“从某个平台找”

单次查询通常控制在 1 个 AI 源 + 1 到 2 个专用源，避免结果过载。

## 处理不可用的源

当站点不可用时：

- 不要因为单个源失败而中止整个搜索
- 记录：「已跳过：<site> 不可用」
- 回退到同类其他站点，或回退到一个 AI 源
- 始终以 `opencli list -f yaml` 与 `opencli <site> -h` 的实际结果为准

不要假设任何站点“绝对可用”。即使是公开站点，也以当前环境中的 live help 和执行结果为准。

## 平台特定陷阱

### 微博热搜 Chrome Bridge 断连时的 API 回退

`opencli weibo hot` 依赖 Chrome Browser Bridge 扩展。若 `opencli doctor` 显示 Extension: disconnected，先尝试 `opencli daemon restart` + 在 `chrome://extensions/` 刷新扩展。若仍不可用，可直接调微博 Ajax API 作为回退：

```bash
curl -sL "https://weibo.com/ajax/statuses/hot_band" \
  -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" \
  -H "Referer: https://weibo.com/" \
  -H "X-Requested-With: XMLHttpRequest" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for item in data.get('data', {}).get('band_list', [])[:30]:
    print(f\"{item.get('rank')}. {item.get('word')} ({item.get('num', '')}) [{item.get('label_name', '')}]\")"
```

注意：另一个端点 `weibo.com/ajax/side/hotSearch` 已被禁止（返回 Forbidden），不要使用。

### 小红书 `feed` 返回的是个性化推荐，不是全站热搜

`opencli xiaohongshu feed` 基于当前登录账号的推荐算法，返回的是**个性化内容**而非全站热门榜单。向用户展示时必须说明这一点。如果用户要全站热搜，小红书没有公开热搜接口，可建议用关键词搜索替代。

### 小红书 `note` 命令需要完整签名 URL

`opencli xiaohongshu note <id>` 已不再接受纯 note-id。必须传完整的带 `xsec_token` 的 URL：

```bash
# ❌ 不行
opencli xiaohongshu note "69e37709000000001a024c9a"

# ✅ 从 search 结果中拿完整 URL
opencli xiaohongshu note "https://www.xiaohongshu.com/search_result/69e37709000000001a024c9a?xsec_token=AB-6RO...&xsec_source="
```

模式：先 `search` → 从结果中提取 `url` 字段 → 传给 `note`。

### Bilibili 字幕提取需 GBK 解码

Bilibili API 返回 GBK 编码。解析字幕/视频数据时：

```bash
opencli bilibili subtitle <bvid> -f json | python3 -c "
import json, sys
data = json.load(sys.stdin)
for item in data:
    print(item['content'])
"
```

### 视频内容获取：字幕 > 元数据

当用户问"这个视频讲了什么"时，优先拉字幕（`subtitle` 命令），而不是只看标题和简介。元数据只能告诉你视频*关于*什么，字幕才能告诉你视频*说了*什么。

## 多平台内容研究模式

当用户要求跨平台研究某个话题时：

1. 并行搜索各平台（`--window background --site-session ephemeral`）
2. 从搜索结果中识别最相关的内容
3. 对高价值视频，拉取字幕/转录文本
4. 综合各平台内容回答（每个平台有不同的内容文化：B站=深度，YouTube=vlog，小红书=生活方式）
5. 末尾附搜索摘要

## 参考文件

根据需要读取对应文件：

- **`references/sources-ai.md`** — AI 默认源
- **`references/sources-tech.md`** — 技术 / 学术
- **`references/sources-social.md`** — 社交媒体
- **`references/sources-media.md`** — 媒体 / 娱乐
- **`references/sources-info.md`** — 资讯 / 知识
- **`references/sources-shopping.md`** — 购物
- **`references/sources-travel.md`** — 旅游
- **`references/sources-other.md`** — 其他垂直源
- **`references/sources-real-estate.md`** — 房产/房价研究（中国房产平台自动化拦截严重，DuckDuckGo 是最可靠的回退方案）

只读与当前查询相关的文件，无需全部加载。

## Chrome 本地历史作为数据源

当需要跨平台用户行为分析、或某平台没有 opencli 适配器时，可以直接读取 Chrome 的本地 SQLite 历史数据库。详见 `references/chrome-local-history.md`。

典型场景：
- 用户问"看看我最近都看了什么"——聚合所有平台的浏览记录
- 用户性格/兴趣画像——基于真实浏览行为而非单一平台
- 验证某内容是否真的被用户看过——直接查 URL 记录
