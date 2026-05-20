# Lightweight Architecture Comprehension via Chain Tracing

When asked to "explain how X works in the codebase" or "analyze a subsystem's design", do NOT dive into a single file. The architecture is spread across layers. Follow the call chain.

## Method

### 1. Identify the Entry Point

Start from where the feature/error is **triggered**:
- Error messages → grep the error string
- User-facing behavior → grep the status message or log line
- Slash commands → grep the command handler
- API route → grep the route decorator

### 2. Trace the Forwarder → Orchestrator → Core Pattern

Layered Python codebases (Hermes, LangChain, etc.) commonly decompose work into:

| Layer | Role | What it contains |
|-------|------|-----------------|
| **Forwarder** | `run_agent.py` | Thin method (`def _compress_context(self, ...):`) that imports and delegates. Docstring says "Forwarder — see agent.foo.bar". Typically 3-8 lines. |
| **Orchestrator** | `agent/conversation_compression.py` | Calls the core algorithm, then handles side effects: DB writes, session rotation, plugin notifications, cache invalidation, token estimation, warnings. |
| **Core** | `agent/context_compressor.py` | The actual algorithm: data structures, heuristics, LLM calls, boundary calculations. Long methods, detailed comments. |

**How to identify each:**
- Read the top file's `from __future__ import annotations` + docstring to see if it declares itself as a "Forwarder" or "extracted from `run_agent`"
- Look for imports that resolve at call time (`from agent.some_module import something`) inside methods — that's the delegate pattern
- Search for `"""Forwarder — see` across the file

### 3. Read Each Layer Bottom-Up (Core → Orchestrator → Forwarder)

Read the **core** first to understand the algorithm, then the **orchestrator** to see what happens around it, then the **forwarder** only as a connecting point.

For each file, extract:

```
## File: path/to/file.py
### Role
One-sentence: what this layer contributes.

### Key Entry Points
- Function/method signatures that other layers call into.

### Design Decisions
- Why things are done this way, not alternatives.
- Edge cases handled (what happens when X fails?).
- Configuration knobs (what can the user tune?).

### Dependencies
- What other modules this layer imports (especially lazy imports).
```

### 4. Produce Structured Summary

Organize by **file**, then **phase/step**. For algorithms, document:

```markdown
### Phase 1 — Name
What happens, what's the cost (LLM call? pure logic?), what's protected.

### Phase 2 — Name
...
```

Include:
- Trigger conditions (when does this code path activate?)
- Failure modes (what happens if an LLM call fails? DB write fails?)
- Guard rails (max retries, cooldowns, minimum message counts)
- Design rationale comments from the code (developers leave these for a reason)

## Why This Works

Python codebases that grow beyond 10K lines tend to decompose via forwarder modules rather than deep class hierarchies. The forwarder pattern:
- Keeps the public API stable (`self._compress_context(...)` stays the same)
- Lets the core algorithm evolve independently
- Allows lazy loading (import inside method, not at module level)
- Makes testing easier (mock the forwarder, test the core separately)

By tracing the chain, you see both the **contract** (forwarder's signature) and the **implementation** (core's logic) in one pass.

## Pitfalls

- Forwarders sometimes inline logic instead of delegating — if a "forwarder" has 30+ lines, it's not really a forwarder
- The orchestrator may contain important state mutations (DB writes, session switches) that are invisible from the core alone — never skip the orchestrator
- Do NOT read .pyc files or __pycache__ — always read the source
- If the core has extracted methods in yet another module (helper files), follow those too — but only if they materially affect understanding. Don't go deeper than 4 levels unless asked.
