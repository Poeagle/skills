# Bilibili 视频转录采集

## OpenCLI 适配器

B 站有完整的 OpenCLI adapter，命令列表：

```bash
opencli list | grep bilibili
```

常用命令：
- `opencli bilibili video <BV号>` — 视频元数据（标题、播放量、点赞等）
- `opencli bilibili subtitle <BV号>` — 字幕/转录文案
- `opencli bilibili comments <BV号>` — 评论
- `opencli bilibili search <关键词>` — 搜索视频
- `opencli bilibili dynamic <UID>` — 用户动态

所有命令需要 COOKIE 策略（Chrome 已登录 B 站）。

## 标准用法

```bash
opencli bilibili subtitle <BV号> --window background --site-session ephemeral -f json
```

返回 JSON 数组，每条包含 `index`、`from`、`to`、`content` 字段。

## 转为纯文案

```bash
opencli bilibili subtitle <BV号> --window background --site-session ephemeral -f json | \
  python3 -c "import json,sys; [print(i['content']) for i in json.load(sys.stdin)]"
```

## 采集到 ingest 的流程

1. 确认 raw/ 中无重复文件
2. 用 OpenCLI 获取字幕 + 视频元数据
3. 保存到 `raw/03-transcripts/主题描述.md`（加 frontmatter）
4. 执行 ingest 流程（提炼 → 摘要 → 概念页 → index → log → lint → 归档）

## 注意事项

- 字幕需要 B 站登录（Chrome 已登录即可）
- `--site-session ephemeral` 防止标签页残留
- 搜索结果的播放量字段可能返回 0（adapter bug），用 `opencli bilibili video` 获取准确数据
