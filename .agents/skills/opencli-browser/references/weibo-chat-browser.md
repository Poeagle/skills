# Weibo Chat / Group Messages via Browser Driving

Weibo's opencli adapters (`opencli weibo search`, `feed`, `hot`, etc.) cover public content but have **no adapter for chat/group messages**. Use browser driving for this.

## Entry point

```
opencli browser <session> open "https://weibo.com/chat"
```

- The URL redirects to `https://api.weibo.com/chat#/chat` (SPA hash route).
- Requires the user to be **logged into Weibo in Chrome** (COOKIE strategy via extension).
- Page title: `微博聊天网页版`.

## Page structure

The chat page is a two-panel SPA:
- **Left panel**: conversation list (`<ul>` inside a scrollable `<div>`). Each `<li>` contains:
  - Avatar `<img>`
  - Conversation name (`<div>` with group/user name)
  - Conversation ID (`<div>` below the name)
  - Timestamp (`<span>`)
  - Last message preview (`<p>` or `<span>`)
- **Right panel**: message thread (appears after clicking a conversation). Messages are `<li>` elements with:
  - Sender avatar, name, and optional badge (管理员, 铁粉, etc.)
  - Message content in `<p>` tags
  - Timestamps as `<p>` with relative time (e.g., `昨天21:13`, `05:46`)
  - System messages (rank-ups, fraud warnings) appear inline

## Workflow

```bash
# 1. Open chat page
opencli browser weibo-chat open "https://weibo.com/chat"

# 2. Snapshot to find conversation list
opencli browser weibo-chat state

# 3. Click a conversation (use numeric ref from state)
opencli browser weibo-chat click 23

# 4. Snapshot the message thread
opencli browser weibo-chat state

# 5. Extract messages via eval (state output is huge on chat pages)
opencli browser weibo-chat eval '(() => {
  const msgs = [];
  document.querySelectorAll("#chat-box li, .chat-list li").forEach(li => {
    const name = li.querySelector(".name, .nick")?.textContent?.trim();
    const text = li.querySelector("p")?.textContent?.trim();
    const time = li.querySelector(".time, .date")?.textContent?.trim();
    if (name || text) msgs.push({name, text, time});
  });
  return JSON.stringify(msgs, null, 2);
})()'

# 6. Close session when done
opencli browser weibo-chat close
```

## Pitfalls

- **`state` output on chat pages is enormous** (50K+ chars) because the message thread + conversation list are both in the DOM. Use `eval` with targeted selectors to extract just the messages you need.
- **Chat list shows `[0条]` for muted conversations** — this means 0 unread messages, not 0 total messages.
- **System messages** (rank-ups, fraud warnings, group join notifications) are interspersed with user messages. Filter by checking for sender name vs. system text patterns.
- **SPA hash routing** means `state` may show a loading spinner if you snapshot too early after `open`. Add `opencli browser <session> wait text "聊天" --timeout 10000` if needed.
- **`--window background` prevents focus-stealing but still opens a tab.** Use `--site-session ephemeral` on adapter commands; for manual browser sessions, always `close` when done.
