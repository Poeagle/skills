"""集群自动发现

通过 SSH 读取 DolphinDB 静态配置文件和目录结构，将最简的 mcp-config.yaml
扩展为包含完整节点信息的 resolved config。不依赖进程存活状态。
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── helpers ──────────────────────────────────────────────────────────


def _parse_properties(text: str) -> dict[str, str]:
    """解析 key=value 格式的配置文件，忽略注释和空行。"""
    props: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            props[key.strip()] = val.strip()
    return props


def _parse_cluster_nodes(text: str) -> list[dict[str, Any]]:
    """解析 cluster.nodes CSV 文件，返回节点列表。

    格式: localSite,mode,computeGroup,zone
    每行: host:port:name,mode,...
    """
    nodes: list[dict[str, Any]] = []
    reader = csv.reader(io.StringIO(text))
    for row in reader:
        if not row or not row[0].strip():
            continue
        first_col = row[0].strip()
        # 跳过标题行和注释
        if first_col.startswith("#") or first_col.startswith("localSite"):
            continue
        if ":" not in first_col:
            continue

        parts = first_col.split(":")
        if len(parts) < 3:
            continue
        host = parts[0]
        try:
            port = int(parts[1])
        except ValueError:
            continue
        name = parts[2].strip()

        node_type = ""
        if len(row) >= 2:
            node_type = row[1].strip()

        # 如果 mode 列为空，从端口后缀或节点名推断类型
        if not node_type:
            port_suffix = port % 10
            if port_suffix == 0:
                node_type = "controller"
            elif port_suffix == 1:
                node_type = "agent"
            elif port_suffix == 2:
                node_type = "datanode"
        if not node_type:
            name_lower = name.lower()
            if "controller" in name_lower:
                node_type = "controller"
            elif "agent" in name_lower:
                node_type = "agent"
            elif "dnode" in name_lower or "cnode" in name_lower:
                node_type = "datanode" if "dnode" in name_lower else "computenode"

        nodes.append({
            "name": name,
            "host": host,
            "port": port,
            "type": node_type,
        })

    return nodes


def _parse_single_node(dolphindb_cfg: str) -> dict[str, Any] | None:
    """从 dolphindb.cfg 解析单机模式节点信息。

    localSite=host:port:name 中提取 name/host/port。
    """
    props = _parse_properties(dolphindb_cfg)
    local_site = props.get("localSite", "")
    if not local_site:
        return None
    parts = local_site.split(":")
    if len(parts) < 3:
        return None
    return {
        "name": parts[2].strip(),
        "host": parts[0].strip(),
        "port": int(parts[1].strip()),
        "type": "single",
    }


def _match_server_by_host(
    host: str, servers: dict[str, dict[str, Any]]
) -> str | None:
    """按 host 匹配 servers 段中的 server 名。"""
    for srv_name, srv_cfg in servers.items():
        if isinstance(srv_cfg, dict) and srv_cfg.get("host") == host:
            return srv_name
    return None


# ── SSH file reader ──────────────────────────────────────────────────


async def _ssh_cat(
    host: str,
    port: int,
    user: str,
    path: str,
    key_file: str | None = None,
    timeout: float = 15.0,
) -> str | None:
    """SSH 到远程服务器读取文件内容。失败返回 None。"""
    try:
        import asyncssh
    except ImportError:
        logger.error("asyncssh not installed, cannot auto-discover")
        return None

    connect_kwargs: dict[str, Any] = {
        "host": host,
        "port": port,
        "username": user,
        "known_hosts": None,
    }
    if key_file:
        p = Path(key_file).expanduser()
        if p.is_file():
            connect_kwargs["client_keys"] = [str(p)]

    async def _connect_and_cat() -> str | None:
        async with asyncssh.connect(**connect_kwargs) as conn:
            result = await conn.run(f"cat {path}", check=False)
            if result.exit_status == 0:
                return result.stdout or ""
            logger.warning(
                "SSH cat %s@%s:%s exit=%d stderr=%s",
                user, host, path,
                result.exit_status, (result.stderr or "")[:200],
            )
            return None

    try:
        return await asyncio.wait_for(_connect_and_cat(), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("SSH read timeout %s@%s:%s", user, host, path)
        return None
    except Exception as e:
        logger.warning("SSH read failed %s@%s:%s: %s", user, host, path, e)
        return None


def _derive_home(
    mode: str, node_type: str, node_name: str, ddb_home: str,
) -> str:
    """推导节点的 HomeDir。

    单机: ddb_home / nodeName
    集群 controller/agent: ddb_home / clusterDemo / data
    集群 datanode/computenode: ddb_home / clusterDemo / data / nodeName
    """
    if mode == "single":
        return f"{ddb_home.rstrip('/')}/{node_name}"
    if node_type in ("controller", "agent"):
        return f"{ddb_home.rstrip('/')}/clusterDemo/data"
    return f"{ddb_home.rstrip('/')}/clusterDemo/data/{node_name}"


def _derive_node_paths(
    node: dict[str, Any],
    ddb_home: str,
    cluster_props: dict[str, str],
    ctrl_props: dict[str, str],
    single_props: dict[str, str],
    mode: str,
) -> dict[str, Any]:
    """为单个节点推导完整路径集合。

    优先级: 显式配置 > HomeDir 默认值

    Returns:
        完整的 node dict（含 exec_dir, log_file, meta_dir, plugin_dir, config）
    """
    node_type = node.get("type", "")
    node_name = node.get("name", "")
    home = _derive_home(mode, node_type, node_name, ddb_home)

    merged_props: dict[str, str] = {}
    merged_props.update(cluster_props)
    merged_props.update(ctrl_props)
    merged_props.update(single_props)

    # ── exec_dir ──
    exec_dir = ddb_home

    # ── log_file ──
    # 优先从配置读 logFile，否则按 DolphinDB 默认命名约定推导：
    #   controller / agent → 共用文件名（同台机器只跑一个该类型进程，不会冲突）
    #   datanode / computenode → <节点名>.log
    log_file = merged_props.get("logFile", "")
    if not log_file:
        if mode == "single":
            log_file = f"{home}/DolphinDBlog"
        else:
            log_dir = f"{ddb_home.rstrip('/')}/clusterDemo/log"
            if node_type == "controller":
                log_file = f"{log_dir}/controller.log"
            elif node_type == "agent":
                log_file = f"{log_dir}/agent.log"
            else:
                log_file = f"{log_dir}/{node_name}.log"

    # ── meta_dir ──
    if node_type == "controller":
        meta_dir = merged_props.get(
            "dfsMetaDir", f"{home}/dfsMeta"
        )
    elif node_type in ("datanode", "computenode"):
        meta_dir = merged_props.get(
            "chunkMetaDir",
            f"{home}/storage/CHUNK_METADATA",
        )
    else:
        meta_dir = ""

    # ── plugin_dir ──
    plugin_dir = merged_props.get("pluginDir", f"{ddb_home.rstrip('/')}/plugins")

    # ── config 透传 ──
    config: dict[str, str] = {}
    # 集群级配置
    config.update(cluster_props)
    # 控制节点配置（仅 controller）
    if node_type == "controller":
        config.update(ctrl_props)
    # 单机配置
    if mode == "single":
        config.update(single_props)

    # 注入推导出的路径到 config（shell_tool 会从中读取）
    if log_file and "logFile" not in config:
        config["logFile"] = log_file
    if exec_dir and "execDir" not in config:
        config["execDir"] = exec_dir

    return {
        **node,
        "exec_dir": exec_dir,
        "log_file": log_file,
        "meta_dir": meta_dir,
        "plugin_dir": plugin_dir,
        "config": config,
    }


# ── 主入口 ──────────────────────────────────────────────────────────


async def discover_clusters(raw_config: dict[str, Any]) -> dict[str, Any]:
    """将最简配置展开为包含完整节点信息的 resolved config。

    raw_config: load_config() 的原始返回（已展开环境变量）

    返回: 与 raw_config 同构，但 clusters.<name>.nodes 已填充完整路径。
    """
    servers: dict[str, dict[str, Any]] = raw_config.get("servers") or {}
    clusters: dict[str, dict[str, Any]] = raw_config.get("clusters") or {}

    resolved: dict[str, dict[str, Any]] = {}
    for cluster_name, cluster_cfg in clusters.items():
        mode = str(cluster_cfg.get("mode", "cluster")).strip().lower() or "cluster"
        username = str(cluster_cfg.get("username", "admin"))
        password = str(cluster_cfg.get("password", ""))
        ddb_home_map: dict[str, str] = cluster_cfg.get("ddb_home") or {}

        # 已展开形式：mcp-config.yaml 直接列出了 nodes（如生产 .43 上的 config），
        # 跳过自动发现，原样保留
        existing_nodes = cluster_cfg.get("nodes")
        if isinstance(existing_nodes, list) and existing_nodes:
            resolved[cluster_name] = {
                "username": username,
                "password": password,
                "nodes": existing_nodes,
            }
            logger.info(
                "Cluster '%s': using %d pre-declared nodes (skip discovery)",
                cluster_name, len(existing_nodes),
            )
            continue

        if not ddb_home_map:
            logger.warning("Cluster '%s' has no ddb_home, skipping", cluster_name)
            continue

        discovered_nodes: list[dict[str, Any]] = []

        if mode == "cluster":
            discovered_nodes = await _discover_cluster(
                cluster_name, ddb_home_map, servers,
            )
        elif mode == "single":
            discovered_nodes = await _discover_single(
                cluster_name, ddb_home_map, servers,
            )

        resolved[cluster_name] = {
            "username": username,
            "password": password,
            "nodes": discovered_nodes,
        }
        logger.info(
            "Cluster '%s': discovered %d nodes (mode=%s)",
            cluster_name, len(discovered_nodes), mode,
        )

    result = dict(raw_config)
    result["clusters"] = resolved
    return result


async def _discover_cluster(
    cluster_name: str,
    ddb_home_map: dict[str, str],
    servers: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """发现集群模式的全部节点。

    从任意一个有 ddb_home 的服务器上读 cluster.nodes + cluster.cfg + controller.cfg。
    """
    nodes: list[dict[str, Any]] = []
    cluster_props: dict[str, str] = {}
    ctrl_props: dict[str, str] = {}

    for server_name, ddb_home in ddb_home_map.items():
        server = servers.get(server_name)
        if not isinstance(server, dict):
            continue
        host = str(server.get("host", ""))
        user = str(server.get("ssh_user", ""))
        port = int(server.get("ssh_port", 22))
        key_file = str(server.get("ssh_private_key_path", ""))

        # 读 cluster.nodes
        nodes_text = await _ssh_cat(
            host, port, user,
            f"{ddb_home.rstrip('/')}/clusterDemo/config/cluster.nodes",
            key_file,
        )
        if not nodes_text:
            logger.warning("Cannot read cluster.nodes from %s, trying next", host)
            continue
        nodes = _parse_cluster_nodes(nodes_text)
        if not nodes:
            continue

        # 读 cluster.cfg
        cluster_cfg_text = await _ssh_cat(
            host, port, user,
            f"{ddb_home.rstrip('/')}/clusterDemo/config/cluster.cfg",
            key_file,
        )
        if cluster_cfg_text:
            cluster_props = _parse_properties(cluster_cfg_text)

        # 读 controller.cfg
        controller_cfg_text = await _ssh_cat(
            host, port, user,
            f"{ddb_home.rstrip('/')}/clusterDemo/config/controller.cfg",
            key_file,
        )
        if controller_cfg_text:
            ctrl_props = _parse_properties(controller_cfg_text)

        break  # 一台服务器成功就够

    if not nodes:
        logger.warning("Cluster '%s': no nodes discovered", cluster_name)
        return []

    # 为每个节点推导完整路径
    result: list[dict[str, Any]] = []
    for node in nodes:
        node_host = node.get("host", "")
        node_srv = _match_server_by_host(node_host, servers) or server_name

        # 确定该节点所在服务器的 ddb_home
        srv_ddb_home = ddb_home_map.get(node_srv, list(ddb_home_map.values())[0])

        full_node = _derive_node_paths(
            node, srv_ddb_home, cluster_props, ctrl_props, {},
            mode="cluster",
        )
        full_node["server"] = node_srv
        result.append(full_node)

    return result


async def _discover_single(
    cluster_name: str,
    ddb_home_map: dict[str, str],
    servers: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """发现单机模式的节点。

    读 dolphindb.cfg 获取 localSite，推导 HomeDir。
    """
    for server_name, ddb_home in ddb_home_map.items():
        server = servers.get(server_name)
        if not isinstance(server, dict):
            continue
        host = str(server.get("host", ""))
        user = str(server.get("ssh_user", ""))
        port = int(server.get("ssh_port", 22))
        key_file = str(server.get("ssh_private_key_path", ""))

        cfg_text = await _ssh_cat(
            host, port, user,
            f"{ddb_home.rstrip('/')}/dolphindb.cfg",
            key_file,
        )
        if not cfg_text:
            continue

        node = _parse_single_node(cfg_text)
        if not node:
            continue

        single_props = _parse_properties(cfg_text)
        full_node = _derive_node_paths(
            node, ddb_home, {}, {}, single_props, mode="single",
        )
        full_node["server"] = server_name
        return [full_node]

    return []
