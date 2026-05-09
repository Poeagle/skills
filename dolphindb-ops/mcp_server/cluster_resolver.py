"""集群拓扑查找（基于 mcp-config.yaml）

mcp-config.yaml 是集群信息的唯一来源；本模块负责按名称查找集群与节点，提供
给工具层使用，不做任何用户级权限检查（详见 docs/agent_generic_migration.md
"Skill 包通用化" 一节）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .config import load_config

logger = logging.getLogger(__name__)


@dataclass
class NodeInfo:
    name: str
    host: str
    port: int
    type: str = ""
    server_name: str | None = None
    log_file: str = ""
    exec_dir: str = ""
    meta_dir: str = ""
    plugin_dir: str = ""
    modules_dir: str = ""
    # 节点级配置参数（来自 mcp-config.yaml node.config 段）。shell_tool 的部分
    # action 用它来推导日志开关、目录结构等。
    config: dict[str, str] = field(default_factory=dict)
    config_explicit_keys: list[str] = field(default_factory=list)


@dataclass
class ClusterInfo:
    name: str
    username: str
    password: str
    nodes: list[NodeInfo]

    def find_node(self, node_name: str) -> NodeInfo | None:
        for n in self.nodes:
            if n.name == node_name:
                return n
        return None


@dataclass
class ServerInfo:
    """SSH 目标主机配置（来自 mcp-config.yaml `servers` 段）。"""
    name: str
    host: str
    ssh_user: str = ""
    ssh_port: int = 22
    ssh_private_key_path: str = ""


def _to_node(raw: Any) -> NodeInfo | None:
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name") or "").strip()
    host = str(raw.get("host") or "").strip()
    try:
        port = int(raw.get("port") or 0)
    except (TypeError, ValueError):
        port = 0
    if not (name and host and port):
        return None
    server_name_raw = raw.get("server")
    cfg = raw.get("config") if isinstance(raw.get("config"), dict) else {}
    return NodeInfo(
        name=name, host=host, port=port,
        type=str(raw.get("type") or ""),
        server_name=str(server_name_raw) if server_name_raw else None,
        log_file=str(raw.get("log_file") or ""),
        exec_dir=str(raw.get("exec_dir") or ""),
        meta_dir=str(raw.get("meta_dir") or ""),
        plugin_dir=str(raw.get("plugin_dir") or ""),
        modules_dir=str(raw.get("modules_dir") or ""),
        config={str(k): str(v) for k, v in (cfg or {}).items()},
        config_explicit_keys=sorted({str(k) for k in (cfg or {}).keys()}),
    )


def get_cluster(name: str) -> ClusterInfo | None:
    """从 mcp-config.yaml 查找集群定义。找不到返回 None。"""
    config = load_config()
    clusters = config.get("clusters") or {}
    if not isinstance(clusters, dict):
        logger.warning("mcp-config.yaml: 'clusters' must be a mapping")
        return None
    raw = clusters.get(name)
    if not isinstance(raw, dict):
        return None

    nodes_raw = raw.get("nodes") or []
    if not isinstance(nodes_raw, list):
        return None

    nodes = [n for n in (_to_node(item) for item in nodes_raw) if n is not None]
    return ClusterInfo(
        name=name,
        username=str(raw.get("username") or ""),
        password=str(raw.get("password") or ""),
        nodes=nodes,
    )


def list_cluster_names() -> list[str]:
    config = load_config()
    clusters = config.get("clusters") or {}
    if not isinstance(clusters, dict):
        return []
    return sorted(clusters.keys())


def get_server(name: str) -> ServerInfo | None:
    """从 mcp-config.yaml 查找 SSH 目标主机定义。

    顶层 `ssh:` 段提供 user/port/private_key_path 默认值，被 servers[name] 中
    的同名字段覆盖。找不到 servers[name] 时回落到 host=name 的默认 ServerInfo。
    """
    config = load_config()
    ssh_default = config.get("ssh") or {}
    if not isinstance(ssh_default, dict):
        ssh_default = {}

    default_user = str(ssh_default.get("user") or "")
    default_port = int(ssh_default.get("port") or 22)
    default_key = str(ssh_default.get("private_key_path") or "")

    servers = config.get("servers") or {}
    raw = servers.get(name) if isinstance(servers, dict) else None
    if isinstance(raw, dict):
        return ServerInfo(
            name=name,
            host=str(raw.get("host") or name),
            ssh_user=str(raw.get("ssh_user") or default_user),
            ssh_port=int(raw.get("ssh_port") or default_port),
            ssh_private_key_path=str(
                raw.get("ssh_private_key_path") or default_key),
        )

    # 没有显式定义 servers[name]：把 name 当 host 使用，套用默认 SSH 配置
    if not name:
        return None
    return ServerInfo(
        name=name,
        host=name,
        ssh_user=default_user,
        ssh_port=default_port,
        ssh_private_key_path=default_key,
    )
