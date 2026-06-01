---
name: opencli-usage
description: Use at the start of any OpenCLI session — this is the top-level map of what `opencli` can do, how to discover adapters, what flags and output formats are universal, and which specialized skill to load next. Point here when an agent asks "what can opencli do?" or "how do I find the right command?".
allowed-tools: Bash(opencli:*), Read
---

# opencli-usage

OpenCLI turns any website, Electron desktop app, or external CLI into a uniform `opencli <site> <command>` surface that agents can drive without screen-scraping. This skill is the orientation layer — once you know what you want to do, load one of the specialized skills below.

## The three pillars

- **Adapter commands** — `opencli <site> <command> [...]`. Built-in adapters live in `clis/`, user adapters in `~/.opencli/clis/`. Each is backed by a strategy (`PUBLIC | COOKIE | INTERCEPT | UI | LOCAL`) that tells you whether a Chrome session is needed.
- **Browser driving** — `opencli browser *` subcommands (`open`, `state`, `click`, `type`, `select`, `find`, `extract`, `network`, …) for ad-hoc interaction and scraping when no adapter covers the task. See `opencli-browser`.
- **Current-tab binding** — `opencli browser <session> bind` attaches the Chrome tab the user already opened/logged into to that browser session. Follow-up commands use `opencli browser <session> ...`. See `opencli-browser` before using it; bound sessions still block tab mutation.
- **External CLI passthrough** — `opencli gh`, `opencli docker`, `opencli vercel`, etc. Managed via `opencli external install <name>` (auto-install from `external-clis.yaml`) or `opencli external register <name>` (bring your own).

## Install

```bash
# npm global
npm install -g @jackwener/opencli          # binary: opencli, requires Node >= 21
opencli doctor                              # run before browser-dependent work (see below)

# From source
git clone git@github.com:jackwener/OpenCLI.git
cd OpenCLI && npm install
npx tsx src/main.ts <command>               # same surface, no global install
```

`opencli doctor` prints a structured `DoctorReport` — daemon status, extension connection, version checks, and a live browser connectivity probe. Scope is narrow: it diagnoses the **browser bridge** (daemon + extension + Chrome wiring). `PUBLIC` / `LOCAL` adapters, `opencli list`, `validate`, `verify`, plugin commands, and external-CLI passthrough don't need it to be green — only `COOKIE` / `INTERCEPT` / `UI` adapters and the `opencli browser *` subcommands do. Flag: `-v` (verbose).

## Prerequisites by command type

| Strategy tag on `opencli list` | What it needs |
|--------------------------------|---------------|
| `PUBLIC` | Nothing — pure HTTP, no browser. |
| `COOKIE` | Chrome logged into the target site + **OpenCLI** extension installed from the [Chrome Web Store](https://chromewebstore.google.com/detail/opencli/ildkmabpimmkaediidaifkhjpohdnifk). Command captures the credential from your live session — no re-login. |
| `INTERCEPT` | Same as COOKIE, plus opencli opens an automation window to capture a signed request. |
| `UI` | Same as COOKIE, full DOM interaction. |
| `LOCAL` | No browser; talks to a local/dev endpoint. |

Electron desktop apps (cursor, codex, chatwise, discord-app, doubao-app, antigravity, chatgpt-app) route through CDP against the running app — same cookie-less flow as a logged-in browser. Make sure the app is running before invoking.

## Discover what's installed — don't read this file, run a command

```bash
opencli list                    # table, grouped by site
opencli list -f json            # machine-readable; pipe to jq or your agent
opencli list | grep -i twitter  # find commands for a specific site
opencli <site> --help           # see that site's commands + flags
opencli <site> <command> --help # see positional args and command-specific flags
```

Do not hard-code adapter lists — there are 100+ sites and the count moves every week. `opencli list -f json` is the source of truth; it emits one entry per command with `{site, name, aliases, description, strategy, browser, args, columns, ...}`. For an agent, that is always better than grepping a doc.

## Universal flags (work on every adapter command)

| flag | effect |
|------|--------|
| `-f, --format <fmt>` | `table` (default in TTY) · `yaml` (default in non-TTY) · `json` · `plain` · `md` · `csv`. Pass explicitly when you want a specific shape; agents almost always want `-f json`. |
| `-v, --verbose` | Debug logs + stack traces on failure; also sets `OPENCLI_VERBOSE=1` for the process. |

Command-specific flags (`--limit`, `--tab`, `--filter`, …) are not universal — consult `<site> <command> --help`.

## Output formats

- `json` — pretty-printed, 2-space indent. Default choice for agents.
- `plain` — prints a single primary field for chat-style commands (`response`/`content`/`text`/`value`). Useful for piping to another tool.
- `yaml` — fallback when output is not a TTY and `-f` is not explicit.
- `table` — color-coded, site-grouped; meant for humans.
- `md`, `csv` — straightforward tabular dumps.

A few commands override the default via `cmd.defaultFormat` (e.g. chat commands default to `plain`), so don't assume without reading `--help`.

## Environment variables

| variable | default | purpose |
|----------|---------|---------|
| `OPENCLI_DAEMON_PORT` | `19825` | Daemon ↔ extension bridge port. |
| `OPENCLI_BROWSER_CONNECT_TIMEOUT` | `30` | Seconds to wait for the browser bridge. |
| `OPENCLI_BROWSER_COMMAND_TIMEOUT` | `60` | Per-command timeout. |
| `OPENCLI_CDP_ENDPOINT` | — | Manual CDP endpoint override (dev / remote Chrome / Electron). |
| `OPENCLI_CACHE_DIR` | `~/.opencli/cache` | Network capture + browser-state cache. |
| `OPENCLI_WINDOW` | command-specific | `foreground` or `background` browser window mode. |
| `OPENCLI_VERBOSE` | `false` | Verbose logging (also triggered by `-v`). |

## Self-repair

When an adapter command fails because the site changed (selectors drifted, API rotated, response schema shifted), re-run with `--trace retain-on-failure`. The error envelope includes a `trace` block pointing at `summary.md`; patch only the `adapterSourcePath` from that summary and retry. Max 3 repair rounds. The full flow is in `opencli-autofix`.

## Writing your own adapter

Two-path storage:

- **Private**: `~/.opencli/clis/<site>/<command>.js` — no build step, hot-available, not visible in the public package.
- **Public / PR**: `clis/<site>/<command>.js` — for upstream contribution; requires build.

Scaffolding & verification:

```bash
opencli browser init <site>/<command>   # generates a skeleton
opencli validate [target]               # semantic checks on the loaded registry (description, domain, pipeline step names, func|pipeline|_lazy presence, arg duplicates) — no network, no browser
opencli verify [target] [--smoke]       # run the command with synthetic args
opencli browser verify <site>/<command> # end-to-end smoke inside the bridge
```

Adapters import only `@jackwener/opencli/registry` and `@jackwener/opencli/errors`. `columns` must align 1:1 (in name and order) with keys of the object returned by `func`. For the full workflow see `opencli-adapter-author`.

## Plugins

Plugins are third-party extensions pulled from git, separate from the main adapter registry:

```bash
opencli plugin install github:user/repo    # install
opencli plugin list [-f json]              # see installed
opencli plugin update [name] | --all       # keep current
opencli plugin uninstall <name>
opencli plugin create <name>               # scaffold a new plugin
```

## External CLI passthrough

Wraps external command-line tools so you can discover + invoke them through the same `opencli …` entrypoint:

```bash
opencli external install gh    # auto-install via brew/apt/npm per external-clis.yaml
opencli external register my-tool \
    --binary my-tool \
    --install "npm i -g my-tool" \
    --desc "My internal CLI"
opencli external list
opencli gh pr list --limit 5   # passthrough; stdio is inherited, exit code propagated
opencli docker ps
```

Built-in entries live in `src/external-clis.yaml`; user overrides and additions in `~/.opencli/external-clis.yaml`. Commonly shipped: `gh`, `docker`, `vercel`, `lark-cli`, `longbridge`, `dws`, `wecom-cli`, `obsidian`, `ntn`, `tg(tg-cli)`, `discord(discord-cli)`, `wx(wx-cli)`.

Some official CLIs use shell-script installers instead of a shell-free package-manager command. Entries without an `install` config, such as `ntn`, must be installed manually from their homepage before passthrough use.

## Shell completion

```bash
opencli completion bash   # also: zsh, fish
# -> script on stdout; source or save per your shell's convention
```

## Where to go next

| If you're about to… | Load this skill |
|---------------------|-----------------|
| Drive a live browser ad-hoc (no adapter available, or prototyping) | `opencli-browser` |
| Write a new adapter, or add a command to an existing site | `opencli-adapter-author` |
| Fix a broken adapter after a command failure | `opencli-autofix` |
| Route a search / lookup / research request to the right adapter | `smart-search` |

## Commands that used to exist

The following were removed in the PR #1094 consolidation — don't try to invoke them:

- `opencli explore <url>` — superseded by `opencli browser network` + `opencli browser find` for live API discovery, and by the `opencli-adapter-author` workflow for capture.
- `opencli record <url>` — removed; manual capture now lives in `opencli browser network --detail`.
- `opencli web read` / `opencli desktop *` as top-level groups — folded into their respective adapters (`opencli web read` still exists as the `web` adapter's `read` command, but there is no standalone `web` / `desktop` top-level group command).

## Session cleanup (mandatory)

⚠️ Users WILL complain about residual tabs. `--window background` only prevents focus-stealing — **tabs still open**. You must clean up.

| pattern | cleanup |
|---------|---------|
| `opencli <site> <cmd> --window background` (COOKIE/INTERCEPT/UI) | add `--site-session ephemeral` for auto-close |
| `opencli browser <session> bind` | `opencli browser <session> unbind` after done |
| `opencli browser <session> open` | `opencli browser <session> close` after done |
| Multiple sessions in one task | close/unbind EACH one, don't skip |

**Good:**
```bash
opencli xiaohongshu search "x" --window background --site-session ephemeral -f json
```
**Bad (leaves tab):**
```bash
opencli xiaohongshu search "x" --window background -f json
```

## ⚠️ FIRST RULE: Check adapter BEFORE browser tools

**For ANY web-related task** (search, scrape, video metadata, comments, user info, content extraction), the FIRST action MUST be:

```bash
opencli list | grep -i <keyword>
```

If an adapter exists → use `opencli <site> <cmd>` (faster, cleaner, no login, no anti-bot).
If no adapter exists → THEN fall back to browser tools.

**Why adapters bypass anti-bot:** The Hermes `browser_navigate` tool runs on a **cloud browser** (Browserbase). Google, Xiaohongshu, Cloudflare-protected sites all flag its IP range and show CAPTCHA/security pages. OpenCLI adapters (PUBLIC/COOKIE/INTERCEPT/UI) run via the **users local Chrome** on their own machine — real browser fingerprint, real cookies, users Clash proxy, residential IP. That is the architectural difference. When the cloud browser shows a security check or IP risk warning, OpenCLI adapter is the fix — not another cloud browser retry.

**Never skip this check.** The 5 seconds saved by jumping to the cloud browser costs 10+ minutes of CAPTCHAs, login walls, and anti-bot blocks. Verified incidents:
- 2026-05-17: Agent scraped Bilibili for 10+ minutes (login walls, could not get subtitles) when `opencli bilibili subtitle` returned full transcript in one call.
- 2026-05-25: Agent opened Xiaohongshu in cloud browser → IP-blocked → user asked why not use opencli.
- 2026-05-29: Agent hit Google CAPTCHA and Xiaohongshu security block in cloud browser. OpenCLI adapters (`opencli xiaohongshu search`) bypassed all — because they run on the users local Chrome with their Clash proxy.

⚠️ **This rule applies even when the task feels like browsing or exploring a social platform.** Do NOT fall back to cloud browser tools because a UI or COOKIE adapter seems inconvenient. Xiaohongshu (`opencli xiaohongshu search`) avoids all IP blocks. If the cloud browser returns an IP risk or login redirect, that is proof you should have used opencli first.

## Don't

- Don't paste this skill's command list into your plan; it will rot. Call `opencli list -f json` at the start of a task instead.
- Don't assume every adapter needs a browser — strategy `PUBLIC` and `LOCAL` don't. Check the `strategy` field.
- Don't silently fall back from a failing adapter to a hand-rolled `fetch` — `--trace retain-on-failure` gives you the browser evidence and adapter source path. Do that first.
- **Don't give up on an adapter after one failed attempt.** Some sites have multiple adapters under different names (e.g. `rednote` vs `xiaohongshu`). If one adapter name fails — regardless of the error code (AUTH_REQUIRED, empty results, connection refused) — run `opencli list | grep -i <site>` to check for alternative names before falling back to browser tools. The user's Chrome session may be logged into one domain but not the other. **Search is available on BOTH `xiaohongshu` and `rednote`** — prefer `opencli xiaohongshu search` first (less likely hit login wall), fall back to `opencli rednote search`.
- **AUTH_REQUIRED on one adapter does NOT mean the site is unavailable.** If `opencli rednote search` returns AUTH_REQUIRED, immediately try `opencli xiaohongshu search` with the same keyword — different domains, different login state. Only fall back to cloud browser tools after BOTH adapters failed.
- **`rednote note` requires a `rednote.com` explore URL, not `xiaohongshu.com`.** Format: `https://www.rednote.com/explore/{note_id}?xsec_token={token}`. The note_id comes from search result URL path (`/search_result/{note_id}`). The ARGUMENT error tells you exactly what's wrong — do not interpret it as 'blocked by anti-bot'. If content shows "Log in with phone number", read tags + comments instead.
- Don't skip `--site-session ephemeral` on COOKIE/INTERCEPT/UI commands. Users complain about residual tabs AND Chrome tab groups. The OpenCLI Chrome extension has `tabGroups` permission and auto-creates an "OpenCLI Browser" tab group for every CDP-opened tab. There is no Chrome flag to disable this in Chrome 148+ (the old `#tab-group-auto-create` flag was removed). ephemeral sessions prevent both issues by destroying the tab immediately after use. If groups already exist: right-click the group title → "Ungroup".
