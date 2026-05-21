# Weibo Chat / Group Messages via Browser Driving

Weibo's opencli adapters (`opencli weibo search`, `feed`, `hot`, etc.) cover public content but have **no adapter for chat/group messages**. Use browser driving for this.

## Entry point

```bash
opencli browser <session> open "https://weibo.com/chat"
```

- The URL redirects to `https://api.weibo.com/chat#/chat` (SPA hash route).
- Requires the user to be **logged into Weibo in Chrome** (COOKIE strategy via extension).
- Page title: `微博聊天网页版`.

## Page structure (confirmed via live DOM)

The chat page is a two-panel SPA inside `<div id=app>`:

### Left panel — conversation list
- `<ul>` inside a scrollable `<div>`. Each `<li>` contains:
  - Avatar `<img>`
  - Conversation name `<div>` (e.g. `张疆machine的铁粉群`)
  - Conversation ID `<div>` below the name (e.g. `4874885341645117`)
  - Timestamp `<span>` (e.g. `05:58`, `05-19`)
  - Last message **preview**: in `<p>` with optional badge showing unread count
    - **Unread badge**: `<span>[398条]</span>` — the `[N条]` pattern is the key signal for unread conversations
    - **Sender prefix**: `<span>海贼lie人索隆:</span>` before the message text
    - **Empty preview with badge**: `<span>1</span>` without preceding text means 1 unread in a system/activity conversation
  - Badge count in a separate `<span>` (e.g. `398`)

### Right panel — message thread (appears after clicking a conversation)
- Each message is a `<li id=5300803309933940>` with a long numeric ID (≥10 digits).
- Structure by message kind:

  **User message:**
  ```
  <li id=...>
    <div>message_id</div>
    <div>
      [timestamp <p>]                    # only shows if it's a time-separator message
      <div><img=avatar_url></div>
      <div>
        <span>sender_name</span>
        <span><img=badge_icon /></span>   # optional: 管理员, 铁粉, 金粉 badges
        <div>
          <div></div>                     # decorative
          <div><div><p>message content</p></div></div>
        </div>
      </div>
    </div>
  </li>
  ```

  **System message** (no avatar/sender):
  ```
  <li id=...>
    <div>message_id</div>
    <div>
      <p />                                # empty
      <div>
        <span>恭喜xxx今日获得"百灵"标识</span>
      </div>
    </div>
  </li>
  ```

  **Fraud warning:**
  ```
  <li id=...>
    <text>涉及资金问题请务必提高警惕，谨防诈骗。查看案例</text>
  </li>
  ```

- Bottom of thread: input area with `#webchat-textarea` and an `<audio id=globaAudio>` marker element.
- "0条最新消息" indicator when reaching the bottom.

## Workflow — extracting messages

### 1. Open chat page
```bash
opencli browser weibo-chat open "https://weibo.com/chat"
```

### 2. Wait for SPA to load
```bash
opencli browser weibo-chat wait text "聊天" --timeout 15000
```

### 3. Identify unread conversations from state snapshot
Read the `state` output and look for the `[N条]` pattern in the left panel list:

```
[21]<p>
  [18]<span>[398条]</span>        ← unread count
  [19]<span>海贼lie人索隆:</span>  ← last sender
  [20]<span>[图片]</span>          ← last message preview (could be [图片], text, or empty)
```

Conversations with **no badge** or `[0条]` are already read.

### 4. Click a conversation to open its thread
```bash
# Use the <li> ref from state, not an inner element
opencli browser weibo-chat click 25
opencli browser weibo-chat wait text "铁粉群" --timeout 10000    # wait for thread to load
```

### 5. Extract messages via eval
`state` output is enormous on chat pages (50K+ chars). Always use `eval` with targeted selectors.

**Refined eval (works with actual Weibo chat DOM):**
```bash
opencli browser weibo-chat eval '(() => {
  const msgs = [];
  document.querySelectorAll("li[id]").forEach(li => {
    const id = li.id;
    if (!id || id.length < 10) return;  // skip conversation-list lis

    const nameEl = li.querySelector("span > span:first-child, span:first-of-type");
    const name = nameEl?.textContent?.trim() || "";

    const ps = li.querySelectorAll("p");
    let textParts = [];
    let time = "";
    ps.forEach(p => {
      const t = p.textContent?.trim();
      if (!t || t === "恭喜") return;
      if (/^\d{1,2}:\d{2}$/.test(t) || /^昨天\d{1,2}:\d{2}$/.test(t)) {
        time = t;
      } else if (t.startsWith("恭喜")) {
        textParts.push("[系统] " + t);
      } else {
        textParts.push(t);
      }
    });

    // Also check direct text for system messages (fraud warnings, rank-ups)
    const directText = li.textContent?.trim() || "";
    if (directText.includes("涉及资金") || directText.includes("谨防诈骗")) {
      textParts.push("[系统警告] " + directText);
    }

    const text = textParts.join(" | ");
    if (name || text) msgs.push({name, text, time});
  });
  return JSON.stringify({total: msgs.length, messages: msgs.slice(-40)}, null, 2);
})()'
```

**Faster alternative when you just want message text (less structured):**
```bash
opencli browser weibo-chat eval '(() => {
  const msgs = [];
  const lis = document.querySelectorAll("li[id]");
  lis.forEach(li => {
    if (li.id.length < 10) return;
    const t = li.textContent?.trim();
    if (t && t.length > 2) msgs.push(t);
  });
  return JSON.stringify({count: msgs.length, messages: msgs.slice(-30)}, null, 2);
})()'
```

### 6. Check additional conversations with unread
Repeat steps 4-5 for each unread conversation. Click the next `<li>` ref from the original state snapshot.

### 7. Close session
```bash
opencli browser weibo-chat close
```

## Workflow — sending a message

### ⚠️ Critical: `keys Enter` DOES NOT WORK for Weibo chat SPA

Weibo chat uses React's synthetic event system. The CDP-level `Input.dispatchKeyEvent` that `opencli browser keys Enter` uses dispatches a native OS-level key event that **React does not recognize**. The text stays in the textarea.

**Working approach:** Use `eval` to dispatch a real `KeyboardEvent` object in the page's JavaScript context.

### Step-by-step

```bash
# 1. Open the chat page
opencli browser weibo-chat open "https://weibo.com/chat"

# 2. Wait for load
opencli browser weibo-chat wait text "聊天" --timeout 15000

# 3. Click the target conversation (ref changes per session — get it from state)
opencli browser weibo-chat state | grep "铁粉群" -B10 | head -1
opencli browser weibo-chat click <li_ref>

# 4. Find the textarea ref
opencli browser weibo-chat state | grep -i textarea
# e.g. [462]<textarea id=webchat-textarea />

# 5. Type the message (use 'type' — it works for filling the textarea)
opencli browser weibo-chat type <textarea_ref> "各位大佬早上好"

# 6. Send by dispatching a real Enter KeyboardEvent via eval
opencli browser weibo-chat eval '(() => {
  const ta = document.querySelector("#webchat-textarea");
  if (!ta) return "textarea not found";
  const evt = new KeyboardEvent("keydown", {
    key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true
  });
  ta.dispatchEvent(evt);
  return "dispatched Enter";
})()'

# 7. Verify — textarea should now be empty
opencli browser weibo-chat get value <textarea_ref>
# {"value": "", "match_level": "exact"}  ← empty = sent successfully
```

### Full one-shot example (for automation)

```bash
opencli browser weibo-chat open "https://weibo.com/chat"
opencli browser weibo-chat wait text "聊天" --timeout 15000
sleep 2
opencli browser weibo-chat click 24     # click 铁粉群 (ref changes per session!)
sleep 2
# type + send in quick succession
opencli browser weibo-chat type 461 "各位大佬早上好"
opencli browser weibo-chat eval '(() => {
  const ta = document.querySelector("#webchat-textarea");
  ta.dispatchEvent(new KeyboardEvent("keydown", {
    key:"Enter", code:"Enter", keyCode:13, which:13, bubbles:true
  }));
  return "sent";
})()'
opencli browser weibo-chat close
```

### Alternative: click a send button

If the textarea approach fails, check for a visible "发送" button:

```bash
opencli browser weibo-chat state | grep -A3 -i "发送"
# If found, click it
opencli browser weibo-chat click <send_button_ref>
```

Note: the "发送" button may be inside a dialog that requires a separate action to open (e.g. clicking an expand/send icon first).

## Identifying conversations from state output (real example)

```
[25]<li />                               ← conversation 1 (铁粉群)
  [10]<img ... />                        ← avatar
  [13]<div>张疆machine的铁粉群</div>      ← name
  [14]<div>4874885341645117</div>        ← conversation ID
  [16]<span>05:58</span>                 ← timestamp
  [18]<span>[398条]</span>               ← **UNREAD** 398 new messages
  [20]<span>[图片]</span>                 ← last message was an image

[38]<li />                               ← conversation 2 (活动通知)
  [26]<img ... />
  [29]<div>活动通知</div>
  [30]<div>4771252927990411</div>
  [32]<span>05-19</span>
  [35]<span>1</span>                     ← **UNREAD** 1 new message (no [N条] wrapper, just the number)

[79]<li />                               ← conversation 3 (read)
  [69]<div>多听多看少说少买</div>
  [72]<span>03-11</span>
  [74]<span>[0条]</span>                 ← READ (0 unread)
  [75]<span>恭喜 liuxun1977 ...</span>
```

## Pitfalls

- **Generic selectors like `#chat-box` and `.chat-list` DON'T exist in the actual DOM.** The message thread is a flat list of `<li id=...>` elements inside a deep `#app > div > div > div...` tree. Always use `li[id]` with length check for message extraction.
- **`state` output on chat pages is enormous** (50K+ chars). Use `eval` with targeted selectors instead of parsing state for content.
- **Sender name extraction is tricky** — names are nested in `<span><span>name</span><span>badge_img</span></span>`. The parent `<span>` also contains the badge `<img>`, so `.textContent` gives both. Use the innermost span's text.
- **Timestamps** in messages appear as standalone `<p>` with time pattern (e.g. `03:28`, `昨天23:59`) interleaved between messages, not as attributes. They show at irregular intervals (not every message has a time).
- **System messages** (rank-ups, fraud warnings, group join notifications) have no sender name — they're just `<span>` text in the message li. Look for patterns like `恭喜...获得...标识`, `涉及资金...`.
- **Scrolling up/down may not load older messages** — the Weibo chat SPA loads messages in batches on scroll. Multiple scroll-up commands may be needed to reach the beginning of unread messages.
- **Chat list shows `[0条]` for muted conversations** — 0 unread, not 0 total.
- **SPA hash routing** means `state` may show a loading spinner if you snapshot too early. Always `wait text` for the page to settle.
- **`keys Enter` does NOT work for sending messages** in Weibo chat's React SPA. The CDP-level key event is not picked up by React's synthetic event system. Always use `eval` + `new KeyboardEvent("keydown", ...)` dispatch instead.
- **Textarea ref IDs change between sessions.** Always re-`state` or `eval` to find `#webchat-textarea` — don't hardcode the ref number.
- **Conversation `<li>` refs also change between sessions** (DOM shifts). Always re-`state` and recalculate.
- **Always `close` the session when done.** The browser tab persists until released.
