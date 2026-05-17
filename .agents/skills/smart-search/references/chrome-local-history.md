# Chrome Local History as Data Source

Chrome stores browsing history in a SQLite database. This is a useful fallback when no opencli adapter covers a site, or when you need aggregated behavioral data across ALL sites (not just one).

## Database Location

```
~/Library/Application Support/Google/Chrome/Default/History
```

**macOS only.** On Linux/Windows the path differs.

## Access Pattern

```bash
# Step 1: Copy to avoid lock conflict (Chrome holds a lock on the live DB)
cp "$HOME/Library/Application Support/Google/Chrome/Default/History" /tmp/chrome_history.db

# Step 2: Query with sqlite3
sqlite3 /tmp/chrome_history.db "<SQL>"
```

Chrome must NOT be writing heavily during the copy, but a simple copy usually succeeds even while Chrome is running.

## Key Schema

- `urls` table: `id`, `url`, `title`, `visit_count`, `last_visit_time`
- `visits` table: `id`, `url` (FK), `visit_time`, `from_visit`, `transition`
- Timestamps are Chrome epoch: microseconds since 1601-01-01 UTC

## Conversion Formula

```sql
-- Last 7 days
WHERE last_visit_time > (SELECT MAX(last_visit_time) - 604800000000 FROM urls)

-- Last 30 days
WHERE last_visit_time > (SELECT MAX(last_visit_time) - 259200000000 FROM urls)

-- To readable datetime:
datetime((last_visit_time/1000000)-11644473600, 'unixepoch', 'localtime')
```

## Common Queries

### Platform visit frequency (last 30 days)
```sql
SELECT
  CASE
    WHEN url LIKE '%bilibili.com%' THEN 'Bilibili'
    WHEN url LIKE '%youtube.com%' THEN 'YouTube'
    WHEN url LIKE '%xiaohongshu.com%' THEN 'Xiaohongshu'
    WHEN url LIKE '%github.com%' THEN 'GitHub'
    -- add more patterns as needed
    ELSE 'Other'
  END as platform,
  COUNT(*) as visits,
  COUNT(DISTINCT url) as unique_urls
FROM urls
WHERE last_visit_time > (SELECT MAX(last_visit_time) - 259200000000 FROM urls)
GROUP BY platform
ORDER BY visits DESC;
```

### Recent browsing timeline
```sql
SELECT
  datetime((last_visit_time/1000000)-11644473600, 'unixepoch', 'localtime') as visit_time,
  url,
  title
FROM urls
WHERE last_visit_time > (SELECT MAX(last_visit_time) - 604800000000 FROM urls)
ORDER BY last_visit_time DESC
LIMIT 200;
```

## Limitations

- Only captures URLs visited, not time spent on each page
- Doesn't capture in-page interactions (scrolling, clicking within a SPA)
- Chrome profile must be the Default profile (or adjust path for other profiles)
- The copy may fail if Chrome is in the middle of a history write (rare, retry)
- Some SPA navigation doesn't create new URL entries

## Use Cases

- **User persona analysis**: aggregate visit patterns across all platforms
- **Research verification**: confirm what the user has actually browsed vs. what adapters captured
- **Behavioral pattern detection**: identify time-of-day patterns, platform switching habits, content consumption trends
