# 中国房产/房价研究数据源

## 问题现象

中国房产平台（贝壳找房、安居客、房天下、58同城）对自动化访问非常敏感：
- **直接浏览器访问**：几乎全部被拦截（CAPTCHA、IP黑名单、滑块验证）
- **opencli ke (贝壳)** 适配器可用但**不能按小区名/关键词搜索**——只支持 `--city` 和 `--district` 地区过滤
- **Xiaohongshu 小红书**：`opencli xiaohongshu`（注意不是 `rednote`）可用——`search` + `note` + `comments` 三件套可获取真实市场数据和评论区讨论价格。需要浏览器 Cookie 登录态（即用户 Chrome 登录了小红书）。详情见下文"小红书补充数据"章节
- **微博**：搜索结果少且多为广告/售楼广告，时效性差

## 小红书（xiahongshu）补充数据（需浏览器 Cookie 登录）

```bash
opencli xiaohongshu search "<小区名> <城市>" --window background --site-session ephemeral -f json --limit 15
```

小红书的价值在于**评论区有真实买家和卖家的价格对话**，而非中介挂牌数据。

### 小红书房产研究流程

```bash
# 第一步：搜索相关帖子
opencli xiaohongshu search "台商 檀悦 房价" --window background --site-session ephemeral -f json --limit 15

# 第二步：从结果中提取完整 URL（含 xsec_token）
# 第三步：查看帖子正文
opencli xiaohongshu note "<完整_url>" --window background --site-session ephemeral -f json

# 第四步：查看评论区（这里是黄金数据）
opencli xiaohongshu comments "<完整_url>" --window background --site-session ephemeral -f json --limit 30
```

关键：`opencli xiaohongshu note` 不接受纯 note-id，必须传 search 结果中的完整 URL（带 xsec_token）。`comments` 同理。

### 小红书能获取的真实市场数据

| 数据类型 | 来源 | 价值 |
|---------|------|------|
| 买家发帖问价（如"预算80万买三房"） | search 结果 | 反映当前市场心理价位 |
| 评论区中介/业主报价（如"檀悦88平75万"） | comments | **真实成交锚点**，比挂牌价低20-35% |
| 业主直售帖（说"价格美丽"但不公开） | note 内容 | 可私聊询价，绕过中介 |
| 房东急售/降价帖 | search 关键词加"急售" | 代表市场底部 |
| 租房帖（如"89平三房1500/月"） | search 关键词加"租房" | 反映租售比 |

### 小红书 vs 传统房产平台价格差异

小红书上的真实买/卖讨论价通常比贝壳/58挂牌价低 **20-35%**。这是因为：
- 挂牌价是房东的理想价，挂高了慢慢等
- 小红书评论区的价格来自实际谈判中的买家和急着出手的卖家
- 抖音/小红书上的中介急售价更接近市场底部

### 搜索关键词建议

- `"<小区名> 房价"` + `"急售"` + `"降价"` — 找最低价锚点
- `"<小区名> 卖房"` + `"房东直售"` — 避开中介找业主
- `"<小区名> 88平"` 或具体户型名 — 精确匹配
- `"台商 买房"` + `"预算"` — 了解市场整体价位

## 最可靠的方案：DuckDuckGo（PUBLIC 策略，无需浏览器）

```bash
opencli duckduckgo search "<小区名> <城市> 房价" -f json --limit 10
```

DuckDuckGo 的 `search` 命令是 **PUBLIC** 策略，无需浏览器、无需登录、不会被拦截。它会返回多个中国房产平台的搜索摘要，包含关键价格数据。

典型示例：
```bash
opencli duckduckgo search "台商投资区 金茂阳光城檀悦 房价" -f json --limit 10
```

## DuckDuckGo 返回的内容覆盖

从 DuckDuckGo 搜索结果中可获取以下平台摘要：

| 平台 | 数据可用性 | 包含信息 |
|------|-----------|---------|
| 安居客 anjuke.com | 高 | 均价、环比/同比涨跌幅、区域对比 |
| 贝壳找房 ke.com | 高 | 具体房源标题、户型、面积、总价、单价 |
| 58同城 58.com | 高 | 具体房源信息（户型、面积、楼层、建造年份） |
| 房天下 fang.com | 高 | 小区均价、在售房源数、地址 |
| 楼盘网 loupan.com | 中 | 参考总价、开发商 |
| 抖音 douyin.com | 中 | 中介急售房源，价格可能低于市场价 |
| 乐居 leju.com | 中 | 新房参考价 |
| 吉屋 jiwu.com | 中 | 售楼信息 |

## 补充数据源

### 贝壳找房适配器（ke）

优点：可用、结构化输出
局限：
- 只支持 `--city` 城市代码 + `--district` 区域拼音，**不能按小区名搜索**
- 城代码示例：`quanzhou`, `bj`, `sh`, `gz`, `sz`
- 子命令：`ershoufang`（二手房）、`xiaoqu`（小区）、`zufang`（租房）、`chengjiao`（成交记录）

```bash
opencli ke xiaoqu --city quanzhou -f json        # 泉州小区
opencli ke ershoufang --city quanzhou -f json     # 泉州二手房
```

### 微博（weibo）

```bash
opencli weibo search "<小区> 房价" --window background --site-session ephemeral -f json --limit 10
```
注意：结果多为售楼广告和历史新闻，数据价值有限。

## 房价信息获取策略（优先级排序）

1. **DuckDuckGo 搜索**（首选，最稳定可靠）
   - 搜 `"<小区名> 房价"` 获取整体行情
   - 搜 `"<小区名> 最新成交价 2025"` 获取更具体的交易信息
2. **贝壳找房 ke 适配器**（补充，但无法按小区名搜索）
3. **微博搜索**（补充，值有限）
4. **不推荐**：直接浏览器访问中国房产平台（基本都会被拦截）

## 价格数据解读注意事项

- DuckDuckGo 返回的搜索摘要中的价格是**挂牌价**，实际成交价通常比挂牌低 5-10%
- 同一小区不同平台上价格差异正常（房源楼层、朝向、装修不同）
- 中介在抖音/快手上的急售价格（如"99万"）通常代表市场底部
- 新房（售楼处）价 > 二手房挂牌价 > 实际成交价
