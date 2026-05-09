"""dolphindb-ops MCP server entry

支持两种传输：
- stdio (默认)：backend 同机部署直接 spawn 子进程
- http：远程公开服务，Bearer token 鉴权 + 多租户

CLI:
    dolphindb-ops-mcp                          # stdio
    dolphindb-ops-mcp serve --transport http   # 显式 http
    dolphindb-ops-mcp serve                    # 读 yaml service.transport
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from typing import Any

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from . import auth, ddb_pool, ssh_pool
from .config import (
    get_service_config,
    load_config,
    set_runtime_config,
)
from .discovery import discover_clusters
from .script_registry import ActionDef, get_script_registry
from .tools.api_tool import (
    CALL_API_DESCRIPTION,
    CALL_API_INPUT_SCHEMA,
    call_api,
)
from .tools.ddb_tool import (
    call_ddb_exec,
    ddb_loader_description,
    ddb_loader_input_schema,
)
from .tools.shell_tool import (
    call_shell_exec,
    shell_exec_description,
    shell_exec_input_schema,
)
from .tools.skill_tool import (
    SKILL_LOADER_DESCRIPTION,
    SKILL_LOADER_INPUT_SCHEMA,
    call_skill_loader,
)

# 把日志输出到 stderr，避免污染 stdio JSON-RPC 通道
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

server: Server = Server("dolphindb-ops")
_config: dict[str, Any] = {}

# Session state: session_id → {"loaded_skills": set, "loaded_refs": set, "introduced_actions": set}
_session_states: dict[str, dict[str, set[str]]] = {}

# session_id 透传字段：调用方在 arguments 中带 __session_id__
SESSION_ID_KEY = "__session_id__"
DEFAULT_SESSION_ID = "default"


def _get_or_create_session(session_id: str) -> dict[str, set[str]]:
    if session_id not in _session_states:
        _session_states[session_id] = {
            "loaded_skills": set(),
            "loaded_refs": set(),
            "introduced_actions": set(),
        }
    return _session_states[session_id]


def _action_to_dict(a: ActionDef, *, include_body: bool = False) -> dict:
    """ActionDef → JSON-serializable dict（供 __describe_action__ / __list_actions__ / describeAction 用）。

    include_body=True 时附带 action 完整源码（body 字段）。describeAction 工具
    用此模式向用户展示代码实现；__list_actions__ 等批量查询不返 body 避免 payload 膨胀。
    """
    out = {
        "name": a.name,
        "description": a.description,
        "source": a.source,
        "permission": a.permission,
        "dangerous": a.dangerous,
        "file_path": a.file_path,
        "collect_categories": list(a.collect_categories),
        "collect_args": {
            cat: dict(args) for cat, args in a.collect_args.items()
        },
        "params": {
            pname: {
                "type": p.type,
                "required": p.required,
                "default": p.default,
                "pattern": p.pattern,
                "allow_chars": p.allow_chars,
                "max": p.max,
            }
            for pname, p in a.params.items()
        },
    }
    if include_body:
        out["body"] = a.body
    return out


# ── MCP 工具注册 ────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="loadRef",
            description=SKILL_LOADER_DESCRIPTION,
            inputSchema=SKILL_LOADER_INPUT_SCHEMA,
        ),
        types.Tool(
            name="execDdb",
            description=ddb_loader_description(),
            inputSchema=ddb_loader_input_schema(),
        ),
        types.Tool(
            name="execShell",
            description=shell_exec_description(),
            inputSchema=shell_exec_input_schema(),
        ),
        types.Tool(
            name="callApi",
            description=CALL_API_DESCRIPTION,
            inputSchema=CALL_API_INPUT_SCHEMA,
        ),
        types.Tool(
            name="describeAction",
            description=(
                "返回指定 action 的完整源码（body）+ 描述 + 参数 schema + 权限级别。"
                "**用于向用户展示『代码实现』而不真正执行**。\n\n"
                "典型场景：\n"
                "- 用户问『这个 action 怎么实现的 / 看代码 / 给我看下 forceCorrectVersion 的代码』\n"
                "- 用户想看修复方案的脚本但不想立即跑\n"
                "- readonly action 的源码展示（execDdb 调 readonly 会直接执行，拿不到 body）\n\n"
                "使用流程：\n"
                "1) 从 execDdb / execShell 的 catalog 找到目标 action 名\n"
                "2) 调 describeAction(name='<action_name>') 拿 body\n"
                "3) 把 body 用代码块展示给用户（按 SKILL.md 第五节模板）"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "action 名（从 execDdb / execShell 的 catalog 中选）",
                    },
                },
                "required": ["name"],
            },
        ),
        types.Tool(
            name="__list_actions__",
            description=(
                "内部工具：返回所有已注册 action 的元信息。"
                "外部 agent (Claude Code 等) 通常不需要使用 —— LLM 应通过工具的 enum"
                "和 description 了解可用 action。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "enum": ["ddb", "shell"],
                        "description": "可选过滤：只返回指定源的 action",
                    },
                },
                "required": [],
            },
        ),
        types.Tool(
            name="__describe_action__",
            description=(
                "内部工具：返回指定 action 的详细元信息（描述、参数 schema、危险标记、"
                "源文件路径、collect 标签等）。供宿主平台展示 action 详情时调用。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "action 名称",
                    },
                },
                "required": ["name"],
            },
        ),
        types.Tool(
            name="__restore_session_state__",
            description=(
                "内部工具：平台从消息历史恢复会话已加载的 SKILL 状态时调用。"
                "外部 agent (Claude Code 等) 通常不需要使用。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "loaded_skills": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "已加载的 skill_id 列表",
                    },
                    "loaded_refs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "已加载的 ref 列表，格式 'skill_id:ref'",
                    },
                    "introduced_actions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "已向 LLM 介绍过的 action 名称",
                    },
                },
                "required": [],
            },
        ),
    ]


_CLUSTER_AWARE_TOOLS = {"execDdb", "execShell", "loadRef"}
_AUDITED_TOOLS = {"execDdb", "execShell", "callApi"}


def _resolve_session_id(client_session_id: str) -> str:
    """HTTP 模式（有 token）下用 token_name 共享 session；stdio 走客户端 session_id。"""
    token_info = auth.get_current_token()
    if token_info is not None:
        return f"token:{token_info.name}"
    return client_session_id or DEFAULT_SESSION_ID


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    arguments = dict(arguments or {})
    raw_session_id = str(arguments.pop(SESSION_ID_KEY, "") or "")
    session_id = _resolve_session_id(raw_session_id)

    # 客户端通过 X-DolphinDB-Cluster / X-DolphinDB-Node header 配置的默认值：
    # 工具调用 args 没传时自动注入。显式传则不动。
    if name in _CLUSTER_AWARE_TOOLS:
        if not arguments.get("cluster"):
            dft = auth.get_default_cluster()
            if dft:
                arguments["cluster"] = dft
        if not arguments.get("node"):
            dft_node = auth.get_default_node()
            if dft_node:
                arguments["node"] = dft_node

    # ── 权限校验：cluster 白名单（仅 HTTP 模式 + token 限制时生效）─────
    if name in _CLUSTER_AWARE_TOOLS:
        cluster_name = str(arguments.get("cluster") or "")
        err = auth.check_cluster_visibility(cluster_name)
        if err:
            if name in _AUDITED_TOOLS:
                auth.audit(tool=name, args=arguments, error=err)
            return [types.TextContent(
                type="text",
                text=json.dumps({"error": err}, ensure_ascii=False),
            )]

    # ── 权限校验：callApi 开关 ────────────────────────────────────
    if name == "callApi" and not auth.is_call_api_allowed():
        err = "当前 token 无 call_api 权限（配置 can_call_api=true 后启用）"
        auth.audit(tool=name, args=arguments, error=err)
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": err}, ensure_ascii=False),
        )]

    state = _get_or_create_session(session_id)

    if name == "loadRef":
        result = await call_skill_loader(arguments, state)
    elif name == "execDdb":
        max_rows = int((_config.get("limits") or {}).get(
            "ddb_result_max_rows", 200))
        result = await call_ddb_exec(arguments, state, default_max_rows=max_rows)
    elif name == "execShell":
        limits = _config.get("limits") or {}
        result = await call_shell_exec(
            arguments, state,
            max_output_length=int(
                limits.get("shell_output_max_chars", 5000)),
            max_output_lines=int(
                limits.get("shell_output_max_lines", 100)),
        )
    elif name == "callApi":
        result = await call_api(arguments, state)
    elif name == "describeAction":
        target_name = str(arguments.get("name") or "").strip()
        if not target_name:
            result = {"error": "缺少 name 参数"}
        else:
            action_def = get_script_registry().get_action(target_name)
            if action_def is None:
                result = {
                    "error": f"action '{target_name}' 未注册",
                    "hint": "查看 execDdb / execShell 的 description 找正确的 action 名",
                }
            else:
                result = _action_to_dict(action_def, include_body=True)
    elif name == "__list_actions__":
        source_filter = arguments.get("source")
        actions = get_script_registry().get_actions(source=source_filter)
        result = {
            "actions": [_action_to_dict(a) for a in actions.values()],
            "total": len(actions),
        }
    elif name == "__describe_action__":
        target_name = str(arguments.get("name") or "").strip()
        if not target_name:
            result = {"error": "缺少 name 参数"}
        else:
            action = get_script_registry().get_action(target_name)
            if action is None:
                result = {
                    "error": f"Action '{target_name}' 未注册",
                }
            else:
                result = _action_to_dict(action)
    elif name == "__restore_session_state__":
        for s in arguments.get("loaded_skills") or []:
            state["loaded_skills"].add(str(s))
        for r in arguments.get("loaded_refs") or []:
            state["loaded_refs"].add(str(r))
        for a in arguments.get("introduced_actions") or []:
            state["introduced_actions"].add(str(a))
        result = {
            "session_id": session_id,
            "loaded_skills": sorted(state["loaded_skills"]),
            "loaded_refs": sorted(state["loaded_refs"]),
            "introduced_actions_count": len(state["introduced_actions"]),
        }
    else:
        result = {"error": f"Unknown tool: {name}"}

    if name in _AUDITED_TOOLS:
        err_msg = (
            result.get("error") if isinstance(result, dict) else None)
        auth.audit(tool=name, args=arguments, error=err_msg)

    text = json.dumps(result, ensure_ascii=False, default=str)
    return [types.TextContent(type="text", text=text)]


# ── 入口 ────────────────────────────────────────────────────────────


async def _bootstrap() -> dict[str, Any]:
    """加载配置 + 自动发现集群拓扑，返回最终运行时 config。"""
    global _config
    raw_config = load_config()
    try:
        _config = await discover_clusters(raw_config)
    except Exception as e:
        logger.warning("Auto-discovery failed, falling back to raw config: %s", e)
        _config = raw_config
    set_runtime_config(_config)
    logger.info(
        "dolphindb-ops MCP server starting (clusters=%d, skill_dir=%s)",
        len(_config.get("clusters") or {}),
        _config.get("skill_dir") or "(default)",
    )
    return _config


async def _shutdown() -> None:
    ddb_pool.close_all()
    try:
        await ssh_pool.close_all()
    except Exception as e:
        logger.warning("ssh_pool.close_all failed: %s", e)


async def _run_stdio() -> None:
    await _bootstrap()
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    finally:
        await _shutdown()


async def _run_http(host: str, port: int) -> None:
    """HTTP / streamable-http 模式：Bearer token 鉴权 + ASGI。"""
    await _bootstrap()
    svc = get_service_config()
    if not svc.enabled:
        logger.warning(
            "Starting HTTP transport but service.enabled=false in config — "
            "all requests will reject as no token table is loaded.")

    try:
        import uvicorn
        from mcp.server.streamable_http_manager import (
            StreamableHTTPSessionManager,
        )
        from starlette.responses import JSONResponse
    except ImportError as e:
        logger.error(
            "HTTP transport requires uvicorn + starlette + mcp[server]: %s", e)
        raise

    # session_idle_timeout 在较新 mcp 版本才支持
    import inspect as _inspect
    _mgr_kwargs: dict[str, Any] = {"stateless": False}
    if "session_idle_timeout" in _inspect.signature(
            StreamableHTTPSessionManager.__init__).parameters:
        _mgr_kwargs["session_idle_timeout"] = svc.session_idle_timeout
    else:
        logger.warning(
            "mcp version lacks session_idle_timeout support; "
            "configured value %ds is ignored", svc.session_idle_timeout)
    manager = StreamableHTTPSessionManager(server, **_mgr_kwargs)

    async def asgi_app(scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await manager.handle_request(scope, receive, send)
            return

        # 提取 Authorization + X-DolphinDB-Cluster + X-DolphinDB-Node 头
        auth_header = ""
        default_cluster = ""
        default_node = ""
        for k, v in scope.get("headers") or []:
            kl = k.lower()
            if kl == b"authorization":
                auth_header = v.decode("latin-1", errors="replace")
            elif kl == b"x-dolphindb-cluster":
                default_cluster = v.decode("latin-1", errors="replace").strip()
            elif kl == b"x-dolphindb-node":
                default_node = v.decode("latin-1", errors="replace").strip()

        token_info = auth.authenticate_header(auth_header)
        if token_info is None:
            resp = JSONResponse(
                {
                    "error": "Unauthorized",
                    "hint": "缺少或无效的 Authorization: Bearer <token>",
                },
                status_code=401,
            )
            await resp(scope, receive, send)
            return

        auth.set_current_token(token_info)
        auth.set_default_cluster(default_cluster or None)
        auth.set_default_node(default_node or None)
        try:
            await manager.handle_request(scope, receive, send)
        finally:
            auth.set_current_token(None)
            auth.set_default_cluster(None)
            auth.set_default_node(None)

    config = uvicorn.Config(
        asgi_app,
        host=host,
        port=port,
        log_level="info",
        access_log=False,  # 我们走自己的审计日志
    )
    uvi = uvicorn.Server(config)

    try:
        async with manager.run():
            from .config import _tokens_cache
            logger.info(
                "HTTP MCP server listening on %s:%d (tokens=%d)",
                host, port, len(_tokens_cache or {}),
            )
            await uvi.serve()
    finally:
        await _shutdown()


def _parse_argv(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="dolphindb-ops-mcp")
    sub = parser.add_subparsers(dest="cmd")

    # serve [--transport stdio|http] [--host] [--port]
    p_serve = sub.add_parser("serve", help="启动 server（默认根据 yaml 决定传输）")
    p_serve.add_argument("--transport", choices=["stdio", "http"], default=None,
                         help="覆盖 yaml service.transport（默认 stdio）")
    p_serve.add_argument("--host", default=None, help="HTTP 监听地址")
    p_serve.add_argument("--port", type=int, default=None, help="HTTP 监听端口")
    return parser.parse_args(argv)


def run() -> None:
    """pyproject.toml 入口点。

    无参数 = stdio（向后兼容）。
    `serve` 子命令读 yaml `service.transport`，CLI 参数可覆盖。
    """
    argv = sys.argv[1:]
    if not argv:
        # 向后兼容：无参直接 stdio
        try:
            asyncio.run(_run_stdio())
        except KeyboardInterrupt:
            pass
        return

    args = _parse_argv(argv)
    if args.cmd != "serve":
        # 未知子命令：fallback stdio
        try:
            asyncio.run(_run_stdio())
        except KeyboardInterrupt:
            pass
        return

    # 先 bootstrap config，才能读 service.transport
    # 但 bootstrap 在 _run_* 里做。这里只能先 load 一遍 yaml 拿 transport
    # （discovery 的结果不影响传输选择）
    raw = load_config()
    if raw:
        from .config import init_service_config
        init_service_config(raw)

    svc = get_service_config()
    transport = args.transport or (svc.transport if svc.enabled else "stdio")
    host = args.host or svc.host
    port = args.port or svc.port

    try:
        if transport == "http":
            asyncio.run(_run_http(host, port))
        else:
            asyncio.run(_run_stdio())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
