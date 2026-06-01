# Xiaohongshu / Rednote Note Reading Patterns

This file documents the patterns for reading Xiaohongshu note content through OpenCLI adapters, including login-wall workarounds.

## Two Domains, Two Adapter Names

| Domain | Adapter name | Login needed? | Use for |
|---|---|---|---|
| `xiaohongshu.com` | `opencli xiaohongshu` | Usually works | Search (`search`), user profile (`user`) |
| `rednote.com` | `opencli rednote` | Often login-walled | Note reading (`note`), comments (`comments`) |

**Key insight:** The user's Chrome may be logged into `xiaohongshu.com` but NOT `rednote.com` (or vice versa). Always try both.

## Note URL Format

The `opencli rednote note` command requires:

```
https://www.rednote.com/explore/{note_id}?xsec_token={token}
```

NOT:
- `https://www.xiaohongshu.com/explore/...` (wrong domain) → ARGUMENT error
- `https://www.xiaohongshu.com/search_result/...` (search result URL, not note URL) → ARGUMENT error

**How to get the real note URL from search results:**
1. Run `opencli xiaohongshu search "keyword" -f json`
2. Extract the `url` field from each result
3. But the search result URL is a `search_result/...` path, NOT the note URL
4. The actual note URL is `https://www.rednote.com/explore/{note_id}?xsec_token={token}`
5. The `note_id` can be extracted from: the search result URL's path (e.g. `/search_result/69d3a4ae00000000230237ea` → note_id is the hex string)
6. Alternatively, navigate one of the search results in the browser to see the redirect target, which reveals the explore URL pattern

## Login Wall Behavior

When the user is NOT logged into `rednote.com`, `opencli rednote note` returns:

```json
{"field": "content", "value": "Log in with phone number"}
{"field": "content", "value": "Discover content curated for you"}
```

**Even behind the login wall, these fields are still readable:**
- `title` — the note title
- `author` — the poster's name
- `likes`, `collects`, `comments` — engagement counts
- `tags` — hashtag list (often contains specific restaurant names, brand names, locations)
- Comments (via `opencli rednote comments`) — commonly contain specific names, addresses, and opinions

**Workaround when content is login-walled:**
1. Read `tags` for specific named entities (e.g. `#春风食堂`, `#gaga鲜语`)
2. Read `comments` — users often ask "which store is this?" and others reply with the name/address
3. Search again with the specific names found in tags to get more detailed posts
4. Or ask the user to open the link in their browser (they're logged in on their phone)

## Error Code Reference

| Error | Likely Cause | Fix |
|---|---|---|
| `ARGUMENT: rednote note now requires a full signed URL` | Passed a `search_result` URL instead of `explore` URL, or wrong domain | Use `rednote.com/explore/...` format |
| `AUTH_REQUIRED` on `rednote search` | Not logged into rednote.com | Try `opencli xiaohongshu search` instead; or ask user to log in |
| Empty results from `xiaohongshu search` | Keyword too narrow, or adapter issue | Try broader keywords; or try `rednote search` |
