# Xiaohongshu Content Extraction via OpenCLI

## The Two-Step Pattern

Direct note URLs (`/explore/ID` or `/search_result/ID`) **do not work** with `web read` or `browser open` — they redirect to login/404. The `xiaohongshu note` adapter also rejects bare URLs, requiring a signed URL with `xsec_token`.

**Correct workflow:**

### Step 1: Search to get signed URLs
```bash
opencli xiaohongshu search "关键词" --limit 10 --window background --site-session ephemeral -f json
```
Returns JSON array with `url` fields containing `xsec_token` parameters. These are the signed URLs the note adapter needs.

### Step 2: Extract each post with the note adapter
```bash
opencli xiaohongshu note "<signed-url-from-search>" --window background --site-session ephemeral -f json
```
Returns structured fields: `title`, `author`, `content`, `likes`, `collects`, `comments`, `tags`.

### Batch extraction
For multiple posts, run Step 2 in parallel with `execute_code` or sequential calls. Each needs its own `--site-session ephemeral` to avoid tab conflicts.

## Key Pitfalls

1. **Never use bare note IDs** — `opencli xiaohongshu note "69a136ce..."` fails with ARGUMENT error. Always pass the full signed URL from search results.

2. **`search_result` URLs without `xsec_token` fail** — the error is `url is invalid` (code 300017). The token is mandatory.

3. **`web read` doesn't work on Xiaohongshu** — returns "安全限制" / "url is invalid". The site blocks non-browser access.

4. **`browser open` on `/explore/ID` returns 404** — "Sorry, This Page Isn't Available Right Now" (code 300031). Xiaohongshu requires auth for note pages.

5. **Parallel browser sessions** — when extracting multiple posts, each `note` call opens its own ephemeral tab. Don't reuse session names across parallel calls.

## Available Adapter Commands

| Command | Purpose | Notes |
|---------|---------|-------|
| `xiaohongshu search <query>` | Search posts | Returns signed URLs with xsec_token |
| `xiaohongshu note <url>` | Get post content | Requires full signed URL |
| `xiaohongshu comments <url>` | Get post comments | Same URL requirement |
| `xiaohongshu user <url>` | Get user profile | — |
| `xiaohongshu creator-note-detail <id>` | Creator analytics | Needs creator login, different domain |

## Output Format

The `note` adapter returns flat JSON:
```json
[
  {"field": "title", "value": "..."},
  {"field": "author", "value": "..."},
  {"field": "content", "value": "..."},
  {"field": "likes", "value": "119"},
  {"field": "collects", "value": "101"},
  {"field": "comments", "value": "5"},
  {"field": "tags", "value": "#tag1, #tag2"}
]
```

Use `-f json` for machine-readable output. The `content` field contains the full post text with emoji and formatting intact.
