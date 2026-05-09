"""HTTP 远程模式下的 token 鉴权 / 权限校验 / 审计。

stdio 模式（service.enabled=false）零侵入：所有函数允许 token_info=None，
`get_current_token()` 返回 None 则沿用旧的全局 `agent_can_operate` 语义。
"""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import (
    TokenConfig,
    get_service_config,
    get_token_info,
)

logger = logging.getLogger(__name__)


# ── 当前请求的 token 上下文 ──────────────────────────────────
# HTTP middleware 在每个请求开始时 set，工具内通过 get_current_token() 读取。
# stdio 模式不 set，永远是 None。
_current_token: ContextVar[TokenConfig | None] = ContextVar(
    "dolphindb_ops_current_token", default=None)

# client 通过 X-DolphinDB-Cluster / X-DolphinDB-Node header 配置的默认集群与节点
# （per-connection）。当工具调用 args 不带 cluster/node 时，server 会自动从这里取
_default_cluster: ContextVar[str | None] = ContextVar(
    "dolphindb_ops_default_cluster", default=None)
_default_node: ContextVar[str | None] = ContextVar(
    "dolphindb_ops_default_node", default=None)


def set_current_token(token_info: TokenConfig | None) -> None:
    _current_token.set(token_info)


def get_current_token() -> TokenConfig | None:
    return _current_token.get()


def set_default_cluster(cluster_name: str | None) -> None:
    _default_cluster.set(cluster_name or None)


def get_default_cluster() -> str | None:
    return _default_cluster.get()


def set_default_node(node_name: str | None) -> None:
    _default_node.set(node_name or None)


def get_default_node() -> str | None:
    return _default_node.get()


# ── Bearer token 解析 ────────────────────────────────────────


def authenticate_header(authorization: str | None) -> TokenConfig | None:
    """从 `Authorization: Bearer <token>` 头解析 token，找不到返回 None。"""
    if not authorization:
        return None
    parts = authorization.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return get_token_info(parts[1])


# ── 权限校验（工具内调用）────────────────────────────────────


def check_cluster_visibility(
    cluster_name: str,
) -> str | None:
    """返回错误消息（不可见）或 None（通过）。

    没有当前 token（stdio 模式）时跳过校验。
    """
    token_info = get_current_token()
    if token_info is None or not cluster_name:
        return None
    if not token_info.can_see_cluster(cluster_name):
        return (
            f"集群 '{cluster_name}' 对当前 token 不可见。"
            f"可见集群: {list(token_info.clusters)}"
        )
    return None


def is_operate_allowed(*, fallback: bool) -> bool:
    """当前 token 是否允许跑写操作（recoverable / irreversible）。

    stdio 模式无 token，使用 fallback（旧的全局 agent_can_operate）。
    """
    token_info = get_current_token()
    if token_info is None:
        return fallback
    return token_info.can_operate


def is_call_api_allowed() -> bool:
    """当前 token 是否允许调 callApi。stdio 模式总是允许。"""
    token_info = get_current_token()
    if token_info is None:
        return True
    return token_info.can_call_api


# ── 审计日志 ─────────────────────────────────────────────────


_audit_logger: logging.Logger | None = None
_audit_init_attempted = False


def _get_audit_logger() -> logging.Logger | None:
    global _audit_logger, _audit_init_attempted
    if _audit_init_attempted:
        return _audit_logger
    _audit_init_attempted = True
    svc = get_service_config()
    if not svc.audit_log:
        return None
    try:
        log_path = Path(svc.audit_log)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        al = logging.getLogger("dolphindb_ops.audit")
        al.setLevel(logging.INFO)
        al.propagate = False
        h = logging.FileHandler(log_path, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(message)s"))
        al.addHandler(h)
        _audit_logger = al
        logger.info("Audit log enabled: %s", log_path)
    except Exception as e:
        logger.warning("Failed to init audit log %s: %s", svc.audit_log, e)
    return _audit_logger


_REDACT_KEYS = {"password", "token", "authorization", "service_account_jwt"}


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: ("***" if k.lower() in _REDACT_KEYS else _redact(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def audit(
    *,
    tool: str,
    args: dict[str, Any],
    error: str | None = None,
) -> None:
    """记一行审计日志（jsonl）。仅当 `service.audit_log` 配置时生效。"""
    al = _get_audit_logger()
    if al is None:
        return
    token_info = get_current_token()
    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "token_name": token_info.name if token_info else None,
        "tool": tool,
        "args": _redact(args),
        "ok": error is None,
    }
    if error:
        entry["error"] = error
    try:
        al.info(json.dumps(entry, ensure_ascii=False, default=str))
    except Exception as e:
        logger.warning("Audit log write failed: %s", e)
