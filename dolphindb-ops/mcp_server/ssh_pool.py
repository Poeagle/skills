"""mcp-server 内部 SSH 会话池（基于 asyncssh）

按 (host, port, user) 复用连接；每次取用前用 `is_closed()` 做存活判断，已断
则清理重建。`close_all` 在 mcp-server 关停时调用。
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    """与平台 ssh_client.run_command 返回值兼容的结构。"""
    returncode: int
    stdout: str
    stderr: str


_connections: dict[tuple[str, int, str], Any] = {}
_lock = asyncio.Lock()


def _resolve_key_path(raw: str) -> str | None:
    if not raw:
        return None
    p = Path(raw).expanduser()
    return str(p) if p.is_file() else None


async def _connect(
    host: str, port: int, user: str, private_key_path: str | None,
) -> Any:
    import asyncssh  # 延迟导入，便于环境缺失时给出明确错误
    options: dict[str, Any] = {
        "username": user or os.environ.get("USER", ""),
        "known_hosts": None,  # 默认信任目标主机；外部 agent 可在 yaml 里改
    }
    key = _resolve_key_path(private_key_path or "")
    if key:
        options["client_keys"] = [key]
    return await asyncssh.connect(host, port=port, **options)


async def _is_alive(conn: Any) -> bool:
    try:
        return not conn.is_closed()
    except Exception:
        return False


async def get_connection(
    host: str,
    port: int,
    user: str,
    private_key_path: str | None = None,
) -> Any:
    key = (host, int(port), user or "")
    async with _lock:
        cached = _connections.get(key)
        if cached is not None:
            if await _is_alive(cached):
                return cached
            logger.info("Cached SSH connection to %s@%s:%s is dead, reconnecting",
                        user, host, port)
            _connections.pop(key, None)
            try:
                cached.close()
            except Exception:
                pass

        conn = await _connect(host, port, user, private_key_path)
        _connections[key] = conn
        return conn


async def run_command(
    host: str,
    port: int,
    user: str,
    command: str,
    private_key_path: str | None = None,
    timeout: float = 30.0,
) -> CommandResult:
    conn = await get_connection(host, port, user, private_key_path)
    try:
        result = await asyncio.wait_for(
            conn.run(command, check=False),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        return CommandResult(
            returncode=124,
            stdout="",
            stderr=f"command timed out after {timeout}s: {command[:200]}",
        )
    except Exception as e:
        # 连接异常时清理缓存便于重连
        await invalidate(host, port, user)
        return CommandResult(returncode=255, stdout="", stderr=str(e))

    return CommandResult(
        returncode=int(getattr(result, "returncode", 0) or 0),
        stdout=str(getattr(result, "stdout", "") or ""),
        stderr=str(getattr(result, "stderr", "") or ""),
    )


async def invalidate(host: str, port: int, user: str = "") -> None:
    key = (host, int(port), user or "")
    async with _lock:
        conn = _connections.pop(key, None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass


async def close_all() -> None:
    async with _lock:
        items = list(_connections.values())
        _connections.clear()
    for conn in items:
        try:
            conn.close()
        except Exception:
            pass
