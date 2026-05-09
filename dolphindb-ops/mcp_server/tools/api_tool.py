"""callApi MCP 工具实现（通用 HTTP 客户端）

设计原则：与具体平台解耦。本工具只是一个受约束的 HTTP 客户端：
- 调用方传 method / path 或 url / headers / body
- yaml 提供 backend.base_url 默认值（path 形式时拼接）
- 调用方可用 headers.Authorization 自行注入认证；未传时若 yaml 配置了
  backend.token，自动注入 Bearer header
- 仍然保留"危险操作必须先加载 platform-api"的知识-权限绑定

平台用户身份（JWT）的两种来源：
  (1) 平台的 MCP wrapper 在 headers 里注入（backend 集成模式）
  (2) yaml backend.token 字段（外部 agent 模式，用户从平台前端登录后拿 token 填入）
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ..config import load_config

logger = logging.getLogger(__name__)

DEFAULT_API_RAW_TEXT_MAX_CHARS = 2000

SENSITIVE_KEYS = {
    "password", "encrypted_password",
    "key_file_name", "api_key", "secret",
}
_SENSITIVE_PATTERNS = {
    "pass", "password", "secret", "token",
    "key", "credential", "auth", "private",
}

_DANGEROUS_PATH_KEYWORDS = [
    "/stop", "/start", "/restart", "/shutdown", "/remove", "/delete",
    "/close", "/upgrade", "/restore", "/cancel", "/replace-license",
    "/cleanup",
]

_REQUIRED_OPERATION_REFS = {
    "dolphindb-ops:platform-api",
}


CALL_API_DESCRIPTION = """调用 HTTP API 获取数据或执行操作（通用 HTTP 工具）。
默认拼接 mcp-config.yaml 中 backend.base_url；也可直接传完整 url。
注意：涉及停止节点、删除资源等危险操作时，必须先加载
`loadRef(name='dolphindb-ops', ref='platform-api')` 了解操作规范。"""


CALL_API_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "method": {
            "type": "string",
            "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
            "description": "HTTP 方法",
        },
        "path": {
            "type": "string",
            "description": "API 路径（与 backend.base_url 拼接），如 /api/v1/clusters",
        },
        "url": {
            "type": "string",
            "description": "完整 URL（提供时优先于 path + base_url）",
        },
        "headers": {
            "type": "object",
            "description": "HTTP 请求头（如 Authorization）",
        },
        "params": {
            "type": "object",
            "description": "GET 请求的 query string，或 POST/PUT 的 JSON 请求体",
        },
        "timeout": {
            "type": "number",
            "description": "请求超时（秒），默认 30",
        },
    },
    "required": ["method"],
}


def _is_sensitive_key(key: str) -> bool:
    if key in SENSITIVE_KEYS:
        return True
    key_lower = key.lower()
    return any(p in key_lower for p in _SENSITIVE_PATTERNS)


def _sanitize(data: Any) -> Any:
    if isinstance(data, dict):
        return {
            k: ("******" if _is_sensitive_key(k) else _sanitize(v))
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [_sanitize(item) for item in data]
    return data


def _has_platform_api_loaded(session_state: dict[str, set[str]]) -> bool:
    refs = session_state.get("loaded_refs") or set()
    return bool(refs & _REQUIRED_OPERATION_REFS)


def _has_auth_header(headers: dict[str, str]) -> bool:
    return any(k.lower() == "authorization" for k in headers)


def _ensure_auth_header(headers: dict[str, str]) -> tuple[dict[str, str], str | None]:
    """注入 Authorization，返回 (headers, error)。

    HTTP 远程模式（有 token）：强制使用 call_api.service_account_jwt，无视
    client 传的 Authorization——避免外部 agent 用 MCP 借道伪造身份。
    stdio 模式：保留 client 头；缺失时回退到 yaml backend.token。
    """
    from .. import auth as _auth
    from ..config import get_call_api_config

    if _auth.get_current_token() is not None:
        sa_jwt = get_call_api_config().service_account_jwt
        if not sa_jwt:
            return headers, (
                "HTTP 远程模式下 callApi 需要在 mcp-config.yaml 配置 "
                "call_api.service_account_jwt"
            )
        return {**headers, "Authorization": f"Bearer {sa_jwt}"}, None

    if _has_auth_header(headers):
        return headers, None
    config = load_config()
    backend_cfg = config.get("backend") or {}
    token = str(backend_cfg.get("token") or "")
    if not token:
        return headers, None
    return {**headers, "Authorization": f"Bearer {token}"}, None


async def call_api(
    arguments: dict[str, Any],
    session_state: dict[str, set[str]],
) -> dict:
    method = str(arguments.get("method") or "GET").upper()
    path = str(arguments.get("path") or "")
    url_arg = str(arguments.get("url") or "")
    headers_arg = arguments.get("headers")
    params = arguments.get("params")
    confirm = bool(arguments.get("__confirm__", False))
    try:
        timeout = float(arguments.get("timeout") or 30.0)
    except (TypeError, ValueError):
        timeout = 30.0

    if method not in ("GET", "POST", "PUT", "DELETE", "PATCH"):
        return {"error": f"不支持的 HTTP 方法: {method}"}

    headers: dict[str, str] = {}
    if isinstance(headers_arg, dict):
        for k, v in headers_arg.items():
            headers[str(k)] = str(v)

    if url_arg:
        url = url_arg
    else:
        config = load_config()
        backend_cfg = config.get("backend") or {}
        base_url = str(backend_cfg.get("base_url") or "").rstrip("/")
        if not base_url:
            return {"error": "未配置 backend.base_url，且未传 url 参数"}
        if not path:
            return {"error": "缺少 path 或 url 参数"}
        url = base_url + (path if path.startswith("/") else f"/{path}")

    # 调用方未提供 Authorization 时，尝试从 yaml backend.token 注入
    headers, auth_err = _ensure_auth_header(headers)
    if auth_err:
        return {"error": auth_err}

    # 危险操作的知识-权限绑定（skill 层语义，跟用户权限无关）
    is_dangerous = (
        method == "DELETE"
        or any(kw in url.lower() for kw in _DANGEROUS_PATH_KEYWORDS)
    )
    if is_dangerous and not _has_platform_api_loaded(session_state):
        return {
            "error": "执行危险操作前，请先加载 platform-api 操作规范。",
            "hint": "请调用 loadRef(name='dolphindb-ops', ref='platform-api')",
        }

    # irreversible 等价物：危险路径 / DELETE 必须显式 __confirm__=true
    if is_dangerous and not confirm:
        return {
            "error": f"调用 {method} {path or url} 是 irreversible 级别，需要在调用方先取得用户确认。",
            "permission": "irreversible",
            "hint": "向用户描述要做的事 + 风险，得到确认后重发请求时附加 __confirm__=true",
        }

    api_raw_text_max_chars = DEFAULT_API_RAW_TEXT_MAX_CHARS

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if method == "GET":
                resp = await client.get(url, params=params, headers=headers)
            elif method == "DELETE":
                resp = await client.delete(url, params=params, headers=headers)
            else:
                body = params if params is not None else {}
                resp = await client.request(
                    method, url, json=body, headers=headers)

        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text[:api_raw_text_max_chars]}

        if resp.status_code >= 400:
            return {
                "error": f"API 返回 {resp.status_code}",
                "detail": data,
            }

        return _sanitize(data)

    except httpx.ConnectError as e:
        logger.error("call_api connect error: %s -> %s", url, e)
        return {"error": f"无法连接 {url}: {e}"}
    except httpx.TimeoutException:
        return {"error": f"API 调用超时: {url}"}
    except Exception as e:
        logger.error("call_api failed: %s %s, error: %s",
                     method, url, e, exc_info=True)
        return {"error": f"API 调用失败: {str(e)}"}
