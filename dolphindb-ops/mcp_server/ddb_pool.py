"""mcp-server 内部 DolphinDB 会话池

简单实现：按 (host, port, username) 复用 session；调用前用一个轻量命令做存活
检查，连接断了就清理重建。无显式 TTL/LRU，进程关停时关闭所有连接。
"""

from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

# (host, port, username) → ddb.session
_sessions: dict[tuple[str, int, str], Any] = {}
_lock = threading.Lock()


def _new_session(
    host: str, port: int, username: str, password: str,
) -> Any:
    import dolphindb as ddb  # 延迟导入：dep 缺失时仅用到的工具会失败
    s = ddb.session()
    s.connect(host, port, username, password)
    return s


def get_session(
    host: str,
    port: int,
    username: str,
    password: str,
) -> Any:
    """获取 (host, port, username) 对应的会话；存活则复用，否则重建。

    每个 action 的 def body 由调用方（ddb_tool）按需注入；本模块不维护
    全局 startup 脚本，避免一次性注入所有 def 的隐式依赖问题。
    """
    key = (host, int(port), username or "")

    with _lock:
        cached = _sessions.get(key)
        if cached is not None:
            try:
                cached.run("1")  # 存活检查
                return cached
            except Exception as e:
                logger.info(
                    "Cached DDB session for %s:%s is dead (%s), recreating",
                    host, port, e)
                _sessions.pop(key, None)
                try:
                    cached.close()
                except Exception:
                    pass

        s = _new_session(host, port, username, password)
        _sessions[key] = s
        return s


def invalidate(host: str, port: int, username: str = "") -> None:
    """显式失效缓存会话（连接异常后调用）。"""
    key = (host, int(port), username or "")
    with _lock:
        s = _sessions.pop(key, None)
    if s is not None:
        try:
            s.close()
        except Exception:
            pass


def close_all() -> None:
    """关闭所有缓存会话（mcp-server 关停时）。"""
    with _lock:
        sessions = list(_sessions.values())
        _sessions.clear()
    for s in sessions:
        try:
            s.close()
        except Exception:
            pass
