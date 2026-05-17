# YouTube DOM Extraction Patterns

YouTube uses custom Web Components (Polymer/lit-based). Standard CSS selectors work on them.
The `state` output on history/feed pages routinely exceeds 100K chars — always prefer `eval`.

## Prerequisites

User must have the target YouTube page open in Chrome, logged in.
Then bind: `opencli browser <session> bind`

## Watch History

Page: `https://www.youtube.com/feed/history`

Videos are grouped by date inside `ytd-item-section-renderer` elements.
Each video is a `yt-lockup-view-model`.

```javascript
(() => {
  const results = [];
  const sections = document.querySelectorAll("ytd-item-section-renderer");
  for (const sec of sections) {
    const h2 = sec.querySelector("h2#title");
    const dateText = h2 ? h2.textContent.trim() : "unknown";
    const vids = sec.querySelectorAll("yt-lockup-view-model");
    for (const v of vids) {
      const title = v.querySelector("h3")?.textContent?.trim() || "";
      const channel = v.querySelector("yt-content-metadata-view-model span:first-child")?.textContent?.trim() || "";
      const views = v.querySelector("yt-content-metadata-view-model span:last-of-type")?.textContent?.trim() || "";
      if (title) results.push({date: dateText, title, channel, views});
    }
  }
  return JSON.stringify(results, null, 2);
})()
```

### Key selectors

| Element | Selector |
|---------|----------|
| Date group header | `ytd-item-section-renderer h2#title` |
| Video entry | `yt-lockup-view-model` |
| Video title | `h3` (inside lockup) |
| Video link | `h3 a[href]` or `a[href*="/watch?v="]` |
| Channel name | `yt-content-metadata-view-model span:first-child` |
| View count | `yt-content-metadata-view-model span:last-of-type` |
| Duration badge | `yt-thumbnail-badge-view-model` or `badge-shape` |
| Thumbnail progress | `yt-thumbnail-overlay-progress-bar-view-model` |

### Notes

- Channel name sometimes has whitespace/newline artifacts — trim aggressively.
- The `state` output includes `[N]` ref numbers — useful for `click` actions but not needed for `eval` extraction.
- History page loads ~20 items. Scroll + re-eval for more.
- Date labels are relative ("昨天", "星期四", "5月10日").

## Subscriptions Feed

Page: `https://www.youtube.com/feed/subscriptions`

Same pattern, but videos are in `ytd-grid-video-renderer` or `ytd-video-renderer` depending on layout.

## Playlist

Page: `https://www.youtube.com/playlist?list=<id>`

Videos are in `ytd-playlist-video-renderer`.
Title: `#video-title`, Channel: `#byline`, Views: `#metadata`.
