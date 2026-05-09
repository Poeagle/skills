"""Shell 执行工具（mcp-server 版本，白名单参数化动作模式）

模型只能从预定义的 action 列表选择操作，不能传入任意 shell 命令。
Action 定义来自 mcp-config.yaml.skill_dir 下 scripts/shell/*.sh，由
ScriptRegistry 自动发现。命令模板和参数校验由本工具完成。
"""

from __future__ import annotations

import csv
import io
import logging
import re
from pathlib import Path
from typing import Any

from .. import ssh_pool
from ..cluster_resolver import get_cluster, get_server, list_cluster_names
from ..config import load_config
from ..script_registry import get_script_registry

logger = logging.getLogger(__name__)

DEFAULT_MAX_OUTPUT_LENGTH = 5000
DEFAULT_MAX_OUTPUT_LINES = 100


def _get_action_names() -> list[str]:
    """获取所有可用的 Shell action 名称"""
    return get_script_registry().get_action_names(source="shell")


def _get_config_path(node_env) -> str:
    """根据节点类型推导配置文件路径"""
    exec_dir = node_env.exec_dir
    node_type = getattr(node_env, "type", "single")
    if node_type == "single":
        return f"{exec_dir}/dolphindb.cfg"
    elif node_type == "controller":
        return f"{exec_dir}/clusterDemo/config/controller.cfg"
    elif node_type == "agent":
        return f"{exec_dir}/clusterDemo/config/agent.cfg"
    else:
        # datanode / computenode
        return f"{exec_dir}/clusterDemo/config/cluster.cfg"


# 日志 action → 日志类型分发：
#   - getLogs / tailLogs 根据 params["log_type"] 动态分发
#   - 其它（已收口）action 直接写死 log_type
_LOG_DISPATCH_ACTIONS: set[str] = {"getLogs", "tailLogs"}

_DIRECTORY_ACTION_MAP: dict[str, str] = {
    "listTraceFiles": "trace",
    "tailTraceFile": "trace",
    "getTraceFile": "trace",
    "searchTraceFiles": "trace",
    "listBatchJobFiles": "batch_job",
    "tailBatchJobFile": "batch_job",
    "getBatchJobFile": "batch_job",
    "searchBatchJobFiles": "batch_job",
}


def _resolve_action_log_type(action: str, params: dict[str, Any]) -> str:
    """动态/静态解析 action 的日志类型。返回空字符串表示该 action 不属于日志类。"""
    if action in _LOG_DISPATCH_ACTIONS:
        log_type = str(params.get("log_type", "") or "").strip()
        if log_type:
            return log_type
    return ""

_LOG_TYPE_CAPABILITIES: dict[str, set[str]] = {
    "runtime": {"single", "controller", "agent", "datanode", "computenode"},
    "batch_job": {"single", "controller", "agent", "datanode", "computenode"},
    "trace": {"single", "controller", "agent", "datanode", "computenode"},
    "audit": {"single", "controller", "agent", "datanode", "computenode"},
    "acl_audit": {"single", "controller", "agent", "datanode", "computenode"},
    "raw_script": {"single", "controller", "agent", "datanode", "computenode"},
    "job": {"single", "datanode", "computenode"},
    "query": {"single", "datanode", "computenode"},
    "redo": {"single", "datanode", "computenode"},
}

_LOG_TYPE_ENABLE_CONDITIONS: dict[str, list[str]] = {
    "audit": ["enableAuditLog"],
    "acl_audit": ["enableAuditLog"],
    "query": ["perfMonitoring", "enableDFSQueryLog"],
    "raw_script": ["enableRawScriptLog"],
}

_LOG_TYPE_UNDEFINED_REASONS: dict[str, str] = {
}


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _node_home_dir(node_env: Any) -> str:
    exec_dir = str(getattr(node_env, "exec_dir", "") or "").rstrip("/")
    if not exec_dir:
        return ""
    node_type = getattr(node_env, "type", "single")
    node_name = str(getattr(node_env, "name", "") or "")
    if node_type == "single":
        return f"{exec_dir}/{node_name}" if node_name else exec_dir
    if node_type in {"controller", "agent"}:
        return f"{exec_dir}/clusterDemo/data"
    return f"{exec_dir}/clusterDemo/data/{node_name}" if node_name else f"{exec_dir}/clusterDemo/data"


def _resolve_config_path(raw_path: str, node_env: Any, node_name: str) -> str:
    import os

    path = str(raw_path or "").strip()
    if not path:
        return ""

    home_dir = _node_home_dir(node_env)
    replacements = {
        "<HomeDir>": home_dir,
        "${HomeDir}": home_dir,
        "<nodeAlias>": node_name,
        "nodeAlias": node_name,
        "<ALIAS>": node_name,
    }
    for old, new in replacements.items():
        path = path.replace(old, new)

    if os.path.isabs(path):
        return os.path.normpath(path)
    if home_dir:
        return os.path.normpath(os.path.join(home_dir, path))
    return os.path.normpath(path)


def _config_explicit_keys(node_env: Any) -> set[str]:
    keys = getattr(node_env, "config_explicit_keys", []) or []
    return {str(key) for key in keys}


def _get_capability_reason(log_type: str, node_type: str) -> str:
    return f"{node_type} 节点不产生 {log_type} 日志"


def _infer_runtime_log_path(node_env: Any, node_name: str) -> str:
    import os

    exec_dir = str(getattr(node_env, "exec_dir", "") or "").rstrip("/")
    if not exec_dir:
        return ""

    node_type = getattr(node_env, "type", "single")
    if node_type == "single":
        return os.path.normpath(os.path.join(exec_dir, "dolphindb.log"))
    if node_type == "controller":
        return os.path.normpath(os.path.join(exec_dir, "clusterDemo", "log", "controller.log"))
    if node_type == "agent":
        return os.path.normpath(os.path.join(exec_dir, "clusterDemo", "log", "agent.log"))
    return os.path.normpath(os.path.join(exec_dir, "clusterDemo", "log", f"{node_name}.log"))


def _resolve_runtime_log_path(node_env: Any, node_name: str) -> tuple[str, str, str]:
    log_file = str(getattr(node_env, "log_file", "") or "").strip()
    if log_file:
        return _resolve_config_path(log_file, node_env, node_name), "env.log_file", ""

    inferred = _infer_runtime_log_path(node_env, node_name)
    if inferred:
        return inferred, "inferred", ""
    return "", "default", "无法推导 runtime 日志路径"


def _resolve_directory_config(
    config_key: str,
    node_env: Any,
    node_name: str,
) -> tuple[str, str, str]:
    config = getattr(node_env, "config", {}) or {}
    explicit_keys = _config_explicit_keys(node_env)
    raw_path = str(config.get(config_key, "")).strip()
    if raw_path:
        source = f"config.{config_key}" if config_key in explicit_keys else "default"
        return _resolve_config_path(raw_path, node_env, node_name), source, ""
    return "", "default", f"缺少 {config_key} 配置"


def _resolve_job_log_path(node_env: Any, node_name: str) -> tuple[str, str, str]:
    import os

    config = getattr(node_env, "config", {}) or {}
    explicit_keys = _config_explicit_keys(node_env)
    job_log_file = str(config.get("jobLogFile", "")).strip()
    if job_log_file and "jobLogFile" in explicit_keys:
        resolved = _resolve_config_path(job_log_file, node_env, node_name)
        if os.path.isabs(job_log_file):
            return resolved, "config.jobLogFile", ""

        runtime_path, _, reason = _resolve_runtime_log_path(
            node_env, node_name)
        if not runtime_path:
            return resolved, "config.jobLogFile", reason or "无法推导 runtime 日志路径"

        base_dir = os.path.dirname(runtime_path)
        return os.path.normpath(os.path.join(base_dir, job_log_file)), "config.jobLogFile", ""

    runtime_path, _, reason = _resolve_runtime_log_path(node_env, node_name)
    if not runtime_path:
        return "", "default", reason or "无法推导 runtime 日志路径"
    base_dir = os.path.dirname(runtime_path)
    return os.path.normpath(os.path.join(base_dir, f"{node_name}_job.log")), "default", ""


def _resolve_query_log_path(node_env: Any, node_name: str) -> tuple[str, str, str]:
    import os

    job_path, _, reason = _resolve_job_log_path(node_env, node_name)
    if not job_path:
        return "", "default", reason or "无法推导 job 日志路径"
    base_dir = os.path.dirname(job_path)
    return os.path.normpath(os.path.join(base_dir, f"{node_name}_query.log")), "default", ""


def _resolve_raw_script_log_path(node_env: Any, node_name: str) -> tuple[str, str, str]:
    return _resolve_directory_config("traceLogDir", node_env, node_name)


def _resolve_redo_log_path(node_env: Any, node_name: str) -> tuple[str, str, str]:
    import os

    home_dir = _node_home_dir(node_env)
    if home_dir:
        return os.path.normpath(home_dir), "default", ""

    exec_dir = str(getattr(node_env, "exec_dir", "") or "").strip()
    if exec_dir:
        return os.path.normpath(exec_dir), "default", ""

    return "", "default", "无法推导 redo 日志目录"


def _resolve_runtime_sibling_log_path(
    suffix: str,
    node_env: Any,
    node_name: str,
) -> tuple[str, str, str]:
    import os

    runtime_path, _, reason = _resolve_runtime_log_path(node_env, node_name)
    if not runtime_path:
        return "", "default", reason or "无法推导 runtime 日志路径"
    base_dir = os.path.dirname(runtime_path)
    return os.path.normpath(os.path.join(base_dir, f"{node_name}{suffix}.log")), "default", ""


def _resolve_log_path(log_type: str, node_env: Any, node_name: str) -> tuple[str, str, str]:
    if log_type == "runtime":
        return _resolve_runtime_log_path(node_env, node_name)
    if log_type == "batch_job":
        return _resolve_directory_config("batchJobDir", node_env, node_name)
    if log_type == "trace":
        return _resolve_directory_config("traceLogDir", node_env, node_name)
    if log_type == "raw_script":
        return _resolve_raw_script_log_path(node_env, node_name)
    if log_type == "job":
        return _resolve_job_log_path(node_env, node_name)
    if log_type == "query":
        return _resolve_query_log_path(node_env, node_name)
    if log_type == "audit":
        return _resolve_runtime_sibling_log_path("_audit", node_env, node_name)
    if log_type == "acl_audit":
        return _resolve_runtime_sibling_log_path("_aclAudit", node_env, node_name)
    if log_type == "redo":
        return _resolve_redo_log_path(node_env, node_name)
    return "", "default", _LOG_TYPE_UNDEFINED_REASONS.get(log_type, f"不支持的日志类型: {log_type}")


def _resolve_log_target(log_type: str, node_env: Any, node_name: str) -> dict[str, Any]:
    supported = _LOG_TYPE_CAPABILITIES.get(log_type)
    if supported is None:
        return {"enabled": False, "path": "", "reason": f"不支持的日志类型: {log_type}", "source": ""}

    node_type = getattr(node_env, "type", "single")
    if node_type not in supported:
        return {
            "enabled": False,
            "path": "",
            "reason": _get_capability_reason(log_type, node_type),
            "source": "capability",
        }

    config = getattr(node_env, "config", {}) or {}
    failed_conditions = [
        condition for condition in _LOG_TYPE_ENABLE_CONDITIONS.get(log_type, [])
        if not _as_bool(config.get(condition))
    ]

    path, source, reason = _resolve_log_path(log_type, node_env, node_name)

    if failed_conditions:
        return {
            "enabled": False,
            "path": path,
            "reason": "未满足启用条件: " + ", ".join(failed_conditions),
            "source": source,
        }

    if not path:
        return {
            "enabled": False,
            "path": "",
            "reason": reason or "无法推导日志路径",
            "source": source,
        }

    return {"enabled": True, "path": path, "reason": "", "source": source}


def _dedupe_paths(paths: list[str]) -> list[str]:
    import os

    seen: set[str] = set()
    result: list[str] = []
    for raw_path in paths:
        normalized = os.path.normpath(str(raw_path or "").strip())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _resolve_node_storage_paths(node_env: Any, include_exec_dir: bool = False) -> list[str]:
    paths: list[str] = []

    if include_exec_dir:
        exec_dir = str(getattr(node_env, "exec_dir", "") or "").strip()
        if exec_dir:
            paths.append(exec_dir)

    meta_dir = str(getattr(node_env, "meta_dir", "") or "").strip()
    for raw_path in meta_dir.split(";"):
        candidate = raw_path.strip()
        if candidate:
            paths.append(candidate)

    config = getattr(node_env, "config", {}) or {}
    node_name = getattr(node_env, "name", "")

    volumes_raw = str(config.get("volumes", "") or "").strip()
    if volumes_raw:
        for raw_volume in volumes_raw.split(","):
            volume_path = _resolve_config_path(
                raw_volume.strip(), node_env, node_name)
            if volume_path:
                paths.append(volume_path)

    batch_job_dir = str(config.get("batchJobDir", "") or "").strip()
    if batch_job_dir:
        resolved_batch_job_dir = _resolve_config_path(
            batch_job_dir, node_env, node_name)
        if resolved_batch_job_dir:
            paths.append(resolved_batch_job_dir)

    return _dedupe_paths(paths)


def _resolve_all_allowed_dirs(node_env: Any, node_name: str) -> list[str]:
    """收集节点的所有已知目录（用于 list_dir_usage / clean_file 路径安全校验）"""
    import os

    dirs: list[str] = []

    # 部署目录
    exec_dir = str(getattr(node_env, "exec_dir", "") or "").strip()
    if exec_dir:
        dirs.append(os.path.normpath(exec_dir))

    # 日志目录
    runtime_path, _, _ = _resolve_runtime_log_path(node_env, node_name)
    if runtime_path:
        dirs.append(os.path.normpath(os.path.dirname(runtime_path)))

    # 存储路径（meta、volumes、batchJobDir）
    storage_paths = _resolve_node_storage_paths(
        node_env, include_exec_dir=True)
    for p in storage_paths:
        dirs.append(os.path.normpath(p))

    return _dedupe_paths(dirs)


def _is_path_allowed(target_path: str, allowed_dirs: list[str]) -> bool:
    """检查目标路径是否在允许的目录范围内（禁止 .. 路径穿越）"""
    import os

    normalized = os.path.normpath(target_path)
    if ".." in normalized:
        return False

    for allowed_dir in allowed_dirs:
        if normalized == allowed_dir or normalized.startswith(allowed_dir + os.sep):
            return True
    return False


def _resolve_core_dump_search_paths(node_env: Any, node_name: str) -> list[str]:
    import os

    paths: list[str] = []

    home_dir = _node_home_dir(node_env)
    if home_dir:
        paths.append(home_dir)

    runtime_path, _, _ = _resolve_runtime_log_path(node_env, node_name)
    if runtime_path:
        paths.append(os.path.dirname(runtime_path))

    exec_dir = str(getattr(node_env, "exec_dir", "") or "").strip()
    if exec_dir:
        paths.append(exec_dir)

    meta_dir = str(getattr(node_env, "meta_dir", "") or "").strip()
    for raw_path in meta_dir.split(";"):
        candidate = raw_path.strip()
        if not candidate:
            continue
        paths.append(candidate)
        parent = os.path.dirname(candidate)
        if parent:
            paths.append(parent)

    return _dedupe_paths(paths)


def _build_log_action_result(
    action: str,
    node: str,
    params: dict[str, Any],
    result: Any,
    stdout: str,
    stderr: str,
) -> dict[str, Any]:
    log_type = _resolve_action_log_type(action, params)
    path = str(params.get("path", "") or "")
    path, stdout = _extract_selected_path(stdout, path)

    if stdout.startswith((
        "log file not found: ",
        "raw script log not found: ",
        "raw script log not found in directory: ",
        "redo log not found: ",
        "redo log not found in directory: ",
    )):
        payload = {
            "success": False,
            "action": action,
            "node": node,
            "log_type": log_type,
            "path": path,
            "reason": stdout.strip(),
        }
        if stderr:
            payload["stderr"] = stderr
        return payload

    if log_type == "audit":
        payload = _build_audit_log_result(
            action=action,
            node=node,
            path=path,
            stdout=stdout,
            stderr=stderr,
            success=result.returncode == 0,
        )
        return payload

    if log_type == "job":
        payload = _build_job_log_result(
            action=action,
            node=node,
            path=path,
            stdout=stdout,
            stderr=stderr,
            success=result.returncode == 0,
        )
        return payload

    if log_type == "query":
        payload = _build_query_log_result(
            action=action,
            node=node,
            path=path,
            stdout=stdout,
            stderr=stderr,
            success=result.returncode == 0,
        )
        return payload

    if log_type == "acl_audit":
        payload = _build_acl_audit_log_result(
            action=action,
            node=node,
            path=path,
            stdout=stdout,
            stderr=stderr,
            success=result.returncode == 0,
        )
        return payload

    payload = {
        "success": result.returncode == 0,
        "action": action,
        "node": node,
        "log_type": log_type,
        "path": path,
        "content": stdout,
    }
    if stderr:
        payload["stderr"] = stderr
    return payload


def _extract_selected_path(stdout: str, default_path: str) -> tuple[str, str]:
    marker = "__PATH__:"
    if not stdout.startswith(marker):
        return default_path, stdout

    lines = stdout.splitlines()
    selected_path = lines[0][len(marker):].strip() or default_path
    remaining = "\n".join(lines[1:])
    return selected_path, remaining


def _extract_metadata_lines(stdout: str) -> tuple[dict[str, str], str]:
    metadata: dict[str, str] = {}
    content_lines: list[str] = []
    for line in stdout.splitlines():
        match = re.match(r"^__([A-Z_]+)__:(.*)$", line)
        if match:
            metadata[match.group(1)] = match.group(2).strip()
        else:
            content_lines.append(line)
    return metadata, "\n".join(content_lines)


def _build_core_dump_action_result(
    action: str,
    node: str,
    params: dict[str, Any],
    result: Any,
    stdout: str,
    stderr: str,
) -> dict[str, Any]:
    metadata, content = _extract_metadata_lines(stdout)
    source = metadata.get("SOURCE", "filesystem")
    core_pattern = metadata.get("CORE_PATTERN", "")
    search_paths_text = metadata.get("SEARCH_PATHS") or str(
        params.get("search_paths") or params.get("search_path") or ""
    )
    search_paths = [path.strip()
                    for path in search_paths_text.split(";") if path.strip()]

    payload = {
        "success": result.returncode == 0,
        "action": action,
        "node": node,
        "source": source,
        "scope": "server-wide" if source == "coredumpctl" else "node-search-paths",
        "core_pattern": core_pattern,
        "search_paths": search_paths,
        "count": 0,
    }

    if source == "filesystem":
        entries = _parse_directory_listing(content)
        payload["count"] = len(entries)
        payload["entries"] = entries
        if content:
            payload["raw_output"] = content
    else:
        records = [{"summary": line.strip()}
                   for line in content.splitlines() if line.strip()]
        payload["count"] = len(records)
        payload["records"] = records
        if content:
            payload["raw_output"] = content

    if stderr:
        payload["stderr"] = stderr
    return payload


def _parse_directory_listing(stdout: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("|", 3)
        if len(parts) < 3:
            continue
        mtime, size_text, path = parts[0], parts[1], parts[2]
        size: Any = size_text.strip()
        if str(size).isdigit():
            size = int(size)
        normalized_path = path.strip()
        entry: dict[str, Any] = {
            "path": normalized_path,
            "name": Path(normalized_path).name,
            "size": size,
            "mtime": mtime.strip(),
        }
        if len(parts) >= 4 and parts[3].strip():
            entry["file_info"] = parts[3].strip()
        entries.append(entry)
    return entries


def _build_directory_action_result(
    action: str,
    node: str,
    directory_type: str,
    path: str,
    result: Any,
    stdout: str,
    stderr: str,
) -> dict[str, Any]:
    path, stdout = _extract_selected_path(stdout, path)
    not_found_prefixes = (
        "trace directory not found: ",
        "batch job directory not found: ",
        "trace file not found: ",
        "batch job file not found: ",
        "no trace file found in directory: ",
        "no batch job file found in directory: ",
    )
    if any(stdout.startswith(prefix) for prefix in not_found_prefixes):
        payload = {
            "success": False,
            "action": action,
            "node": node,
            "directory_type": directory_type,
            "path": path,
            "reason": stdout.strip(),
        }
        if stderr:
            payload["stderr"] = stderr
        return payload

    payload = {
        "success": result.returncode == 0,
        "action": action,
        "node": node,
        "directory_type": directory_type,
        "path": path,
    }
    if action.startswith("list_"):
        entries = _parse_directory_listing(stdout)
        payload["directory"] = path
        payload["count"] = len(entries)
        payload["entries"] = entries
        if stdout:
            payload["raw_output"] = stdout
    else:
        payload["content"] = stdout
    if stderr:
        payload["stderr"] = stderr
    return payload


def _coerce_audit_value(field: str, value: str) -> Any:
    if field in {"tid", "cid", "remotePort"}:
        stripped = value.strip()
        if stripped.isdigit():
            return int(stripped)
    return value


def _parse_audit_log_content(content: str) -> tuple[list[str], list[dict[str, Any]]]:
    expected_columns = [
        "userId",
        "startTime",
        "endTime",
        "dbName",
        "tbName",
        "opType",
        "opDetail",
        "tid",
        "cid",
        "remoteIp",
        "remotePort",
    ]
    return _parse_csv_records(content, expected_columns, _coerce_audit_value)


def _build_audit_log_result(
    action: str,
    node: str,
    path: str,
    stdout: str,
    stderr: str,
    success: bool,
) -> dict[str, Any]:
    columns, records = _parse_audit_log_content(stdout)
    payload = {
        "success": success,
        "action": action,
        "node": node,
        "log_type": "audit",
        "path": path,
        "columns": columns,
        "records": records,
    }
    if stdout:
        payload["raw_content"] = stdout
    if stderr:
        payload["stderr"] = stderr
    return payload


def _coerce_job_value(field: str, value: str) -> Any:
    if field in {"sessionId", "level"}:
        stripped = value.strip()
        if stripped.isdigit():
            return int(stripped)
    return value


def _parse_csv_records(
    content: str,
    expected_columns: list[str],
    value_coercer,
) -> tuple[list[str], list[dict[str, Any]]]:
    if not content.strip():
        return [], []

    reader = csv.reader(io.StringIO(content), skipinitialspace=True)
    rows = [row for row in reader if any(str(cell).strip() for cell in row)]
    if not rows:
        return [], []

    header = [str(cell or "").strip() for cell in rows[0]]
    has_header = header == expected_columns
    fieldnames = expected_columns if not has_header else header
    data_rows = rows[1:] if has_header else rows

    records: list[dict[str, Any]] = []
    for row in data_rows:
        padded = list(row[:len(fieldnames)])
        if len(padded) < len(fieldnames):
            padded.extend([""] * (len(fieldnames) - len(padded)))
        normalized = {
            key: value_coercer(key, str(value or ""))
            for key, value in zip(fieldnames, padded)
        }
        if any(str(value).strip() for value in normalized.values()):
            records.append(normalized)
    return fieldnames, records


def _parse_job_log_content(content: str) -> tuple[list[str], list[dict[str, Any]]]:
    expected_columns = [
        "node",
        "userId",
        "sessionId",
        "jobId",
        "rootId",
        "type",
        "level",
        "startTime",
        "endTime",
        "jobDesc",
        "errorMsg",
    ]
    return _parse_csv_records(content, expected_columns, _coerce_job_value)


def _build_job_log_result(
    action: str,
    node: str,
    path: str,
    stdout: str,
    stderr: str,
    success: bool,
) -> dict[str, Any]:
    columns, records = _parse_job_log_content(stdout)
    payload = {
        "success": success,
        "action": action,
        "node": node,
        "log_type": "job",
        "path": path,
        "columns": columns,
        "records": records,
    }
    if stdout:
        payload["raw_content"] = stdout
    if stderr:
        payload["stderr"] = stderr
    return payload


def _coerce_query_value(field: str, value: str) -> Any:
    if field in {"sessionId", "level"}:
        stripped = value.strip()
        if stripped.isdigit():
            return int(stripped)
    return value


def _parse_query_log_content(content: str) -> tuple[list[str], list[dict[str, Any]]]:
    expected_columns = [
        "node",
        "userId",
        "sessionId",
        "jobId",
        "rootId",
        "type",
        "level",
        "time",
        "database",
        "table",
        "jobDesc",
    ]
    return _parse_csv_records(content, expected_columns, _coerce_query_value)


def _build_query_log_result(
    action: str,
    node: str,
    path: str,
    stdout: str,
    stderr: str,
    success: bool,
) -> dict[str, Any]:
    columns, records = _parse_query_log_content(stdout)
    payload = {
        "success": success,
        "action": action,
        "node": node,
        "log_type": "query",
        "path": path,
        "columns": columns,
        "records": records,
    }
    if stdout:
        payload["raw_content"] = stdout
    if stderr:
        payload["stderr"] = stderr
    return payload


_ACL_AUDIT_COLUMNS = [
    "userId",
    "time",
    "event",
    "detail",
    "remoteIp",
    "remotePort",
]


def _parse_acl_audit_log_content(content: str) -> tuple[list[str], list[dict[str, Any]]]:
    if not content.strip():
        return _ACL_AUDIT_COLUMNS, []

    records: list[dict[str, Any]] = []
    reader = csv.reader(io.StringIO(content), skipinitialspace=True)
    for row in reader:
        if not row:
            continue

        padded = list(row[:6]) + [""] * max(0, 6 - len(row))
        record = {
            "userId": padded[0],
            "time": padded[1],
            "event": padded[2],
            "detail": padded[3],
            "remoteIp": padded[4],
            "remotePort": int(padded[5]) if str(padded[5]).strip().isdigit() else padded[5],
        }
        if any(str(value).strip() for value in record.values()):
            records.append(record)
    return _ACL_AUDIT_COLUMNS, records


def _build_acl_audit_log_result(
    action: str,
    node: str,
    path: str,
    stdout: str,
    stderr: str,
    success: bool,
) -> dict[str, Any]:
    columns, records = _parse_acl_audit_log_content(stdout)
    payload = {
        "success": success,
        "action": action,
        "node": node,
        "log_type": "acl_audit",
        "path": path,
        "columns": columns,
        "records": records,
    }
    if stdout:
        payload["raw_content"] = stdout
    if stderr:
        payload["stderr"] = stderr
    return payload


def _validate_param(name: str, value: Any, schema: dict) -> str | None:
    """校验单个参数，返回错误信息或 None"""
    param_type = schema.get("type", "str")

    if param_type == "int":
        if not isinstance(value, int):
            try:
                value = int(value)
            except (ValueError, TypeError):
                return f"参数 '{name}' 必须是整数"
        max_val = schema.get("max")
        if max_val is not None and value > int(max_val):
            return f"参数 '{name}' 超过最大值 {max_val}"

    if param_type == "str" and isinstance(value, str):
        pattern = schema.get("pattern")
        if pattern and not re.match(pattern, value):
            return f"参数 '{name}' 格式不合法"

    return None


def _build_command(template: str, params: dict, param_schemas: dict) -> tuple[str | None, str | None]:
    """根据模板和参数构建命令，返回 (command, error)"""
    # 填充默认值
    resolved: dict[str, Any] = {}
    for param_name, param_schema in param_schemas.items():
        if param_name in params:
            resolved[param_name] = params[param_name]
        elif param_schema.get("required", False):
            return None, f"缺少必填参数: {param_name}"
        elif "default" in param_schema:
            resolved[param_name] = param_schema["default"]

    # 校验参数
    for param_name, value in resolved.items():
        schema = param_schemas.get(param_name, {})
        error = _validate_param(param_name, value, schema)
        if error:
            return None, error

    # 参数替换（使用 str.format_map，对值做安全转义）
    # 默认禁止的注入字符
    _DEFAULT_BLOCKED = set(";|&`$()\n\r")
    safe_params = {}
    for k, v in resolved.items():
        # LLM 可能传 JSON boolean，转为小写 "true"/"false" 兼容 bash 判断
        if isinstance(v, bool):
            str_val = "true" if v else "false"
        else:
            str_val = str(v)
        # 参数 schema 中可通过 allow_chars 放行特定字符（如 pattern 参数允许 | 用于正则）
        schema = param_schemas.get(k, {})
        allow = set(schema.get("allow_chars", ""))
        blocked = _DEFAULT_BLOCKED - allow
        bad = [c for c in str_val if c in blocked]
        if bad:
            return None, f"参数 '{k}' 包含不允许的特殊字符"
        safe_params[k] = str_val

    # 使用逐参数替换而非 format_map，避免 bash 花括号 ({ }) 被误当成模板变量
    command = template
    for k, v in safe_params.items():
        command = command.replace(f"{{{k}}}", v)

    return command, None


def _needs_process_filter_autofill(action: str) -> bool:
    return action in {
        "checkProcessAll",
        "resumeStoppedProcess",
        "checkThreadInfo",
    }


def _needs_port_autofill(action: str) -> bool:
    return action in {
        "checkProcessAll",
        "resumeStoppedProcess",
        "checkThreadInfo",
        "checkSystemRuntime",
        "checkSystemConfig",
    }


_LLM_SUGGESTION_HINT = (
    "强制渲染规约（不要简化，不要重写命令，不要替换为更简单的等价命令）：\n"
    "你必须按 system prompt 中『operation_suggestion 渲染规约』里的模板章节顺序输出，"
    "包括：当前排查情况 / 推荐 shell action / **完整 shell_command（code 字段原样粘贴到代码块）**"
    " / 调用方式（target_server + ssh 命令） / 风险点与执行后果 / 执行前确认事项"
    "（含『执行前请先与 DolphinDB 技术支持沟通确认』+『本工具不会代为执行』）。\n"
    "禁止：仅展示 action 名、给出更简单的等价命令替代、在用户书面确认前结束本回合。\n"
    "如需自动执行（如自动化巡检），需 mcp-config.yaml 设置 agent_can_operate: true，"
    "且调用时显式传 __confirm__=true。"
)


def _build_shell_operation_suggestion(
    action_def: Any, cluster_name: str, node_name: str,
    params: dict | None,
) -> dict:
    cfg = load_config()
    suggestion_cfg = cfg.get("operation_suggestion") or {}
    return {
        "type": "operation_suggestion",
        "action_name": action_def.name,
        "permission": action_def.permission,
        "context": {
            "cluster": cluster_name,
            "node": node_name,
            "args": params or {},
        },
        "description": action_def.description,
        "shell_template": action_def.body,
        "execution_methods": suggestion_cfg.get("execution_methods") or [],
        "support_advisory": suggestion_cfg.get("support_advisory") or "",
        "instructions_for_llm": _LLM_SUGGESTION_HINT,
    }


def _shell_description() -> str:
    """动态生成 execShell 工具描述，包含所有 Shell action 目录。"""
    base = (
        "在指定节点所在的服务器上执行预定义的 Shell 运维操作。\n"
        "只能从白名单中选择操作类型（action），不能传入任意命令。\n"
        "服务器信息由环境上下文根据节点名自动解析，无需手动传入。\n"
        "params 里只能传当前 action 明确声明过的字段，不要自行补充未列出的键。\n"
        "⚠️ 重要：node 必须是 datanode 或 computenode，禁止传入 controller 节点。\n"
        "以下参数会根据环境上下文自动填充，无需显式传递：\n"
        "- 日志类 action 的 path：自动使用节点对应的日志路径\n"
        "- check_process/check_process_status/check_process_threads/check_process_fd/check_process_limits/resume_stopped_process，以及所有 check_thread_* 动作的 filter/port：自动使用节点的可执行文件路径和端口\n"
        "- check_disk/check_dir_size/check_inode 的 paths：自动使用节点相关存储路径\n"
        "- find_core_dumps 的 search_paths：自动使用 core_pattern 推导目录\n"
        "- list_dir_usage/clean_file 的路径：自动校验必须在节点已知目录范围内"
    )
    catalog = get_script_registry().action_catalog(source="shell")
    if catalog:
        return f"{base}\n\n可用 actions:\n{catalog}"
    return base


def _shell_parameters() -> dict:
    """动态生成 execShell 工具参数 schema，enum 实时从 ScriptRegistry 获取。"""
    return {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "操作类型（从白名单中选择）",
                "enum": get_script_registry().get_action_names(source="shell"),
            },
            "node": {
                "type": "string",
                "description": "目标节点名（datanode 或 computenode，禁止 controller）。HTTP 模式下若 client 配了 X-DolphinDB-Node header，可省略；缺省 server 会报错。",
            },
            "params": {
                "type": "object",
                "description": "操作参数。只允许传当前 action 在目录中显式列出的字段；未列出的键不要传。",
            },
        },
        "required": ["action"],
    }


def shell_exec_description() -> str:
    return _shell_description()


def shell_exec_input_schema() -> dict[str, Any]:
    schema = _shell_parameters()
    # mcp-server 模式下需要 cluster 透传（平台从 env 注入；外部 agent 必须显式传）
    schema.setdefault("properties", {})["cluster"] = {
        "type": "string",
        "description": "目标集群名（不传时由调用方注入；外部 agent 必须显式提供）",
    }
    return schema


async def call_shell_exec(
    arguments: dict[str, Any],
    session_state: dict[str, set[str]],
    *,
    max_output_length: int = DEFAULT_MAX_OUTPUT_LENGTH,
    max_output_lines: int = DEFAULT_MAX_OUTPUT_LINES,
) -> dict:
    """execShell 的 MCP 实现。"""
    action = arguments.get("action") or ""
    node = arguments.get("node") or ""
    cluster_name = arguments.get("cluster") or ""
    params = arguments.get("params") if isinstance(
        arguments.get("params"), dict) else None
    confirm = bool(arguments.get("__confirm__", False))

    # 白名单校验
    registry = get_script_registry()
    action_def = registry.get_action(action)
    if action_def is None or action_def.source != "shell":
        return {
            "error": f"未知的操作类型: {action}",
            "available_actions": _get_action_names(),
        }

    # 操作类（recoverable / irreversible）默认不执行，返回结构化建议给用户
    # HTTP 模式下 token can_operate=false 强制降级；stdio 模式回退全局 agent_can_operate
    if action_def.permission != "readonly":
        from .. import auth as _auth
        cfg = load_config()
        fallback = bool(cfg.get("agent_can_operate"))
        if not (_auth.is_operate_allowed(fallback=fallback) and confirm):
            return _build_shell_operation_suggestion(
                action_def, cluster_name, node, params)

    template = action_def.body
    # 将 ActionParam 转为 dict schema 以兼容 _build_command/_validate_param
    param_schemas: dict[str, dict] = {}
    for pname, pdef in action_def.params.items():
        schema_p: dict[str, Any] = {
            "type": pdef.type, "required": pdef.required}
        if pdef.default is not None:
            schema_p["default"] = pdef.default
        if pdef.pattern is not None:
            schema_p["pattern"] = pdef.pattern
        if pdef.allow_chars is not None:
            schema_p["allow_chars"] = pdef.allow_chars
        if pdef.max is not None:
            schema_p["max"] = pdef.max
        param_schemas[pname] = schema_p

    if not template:
        return {"error": f"操作 '{action}' 模板配置为空"}

    if not cluster_name:
        return {
            "error": "缺少 cluster 参数（mcp-server 仅靠 mcp-config.yaml 解析集群拓扑）",
            "available_clusters": list_cluster_names(),
        }
    cluster = get_cluster(cluster_name)
    if cluster is None:
        return {
            "error": f"集群 '{cluster_name}' 未在 mcp-config.yaml 中定义",
            "available_clusters": list_cluster_names(),
        }

    node_env = cluster.find_node(node)
    if node_env is None:
        return {
            "error": f"节点 '{node}' 不存在于集群 '{cluster_name}'",
            "available_nodes": [n.name for n in cluster.nodes],
        }

    server_name = node_env.server_name or node_env.host
    if params is None:
        params = {}

    log_resolution: dict[str, Any] | None = None

    # 自动填充日志路径（按日志类型分别解析；getLogs / tailLogs 从 params["log_type"] 动态读取）
    log_action_type = _resolve_action_log_type(action, params)
    if log_action_type and "path" not in params:
        if not node_env:
            return {"error": f"无法找到节点 '{node}' 的环境信息"}

        log_type = log_action_type
        log_resolution = _resolve_log_target(log_type, node_env, node)

        if log_resolution.get("path"):
            params["path"] = log_resolution["path"]

        if not log_resolution.get("enabled", False):
            return {
                "success": False,
                "action": action,
                "node": node,
                "server": server_name,
                "resolved_params": {"path": log_resolution.get("path", "")},
                "reason": log_resolution.get("reason", "日志未启用或路径无法推导"),
                "log_resolution": log_resolution,
            }

        if not log_resolution.get("path"):
            return {
                "success": False,
                "action": action,
                "node": node,
                "server": server_name,
                "resolved_params": {},
                "reason": log_resolution.get("reason", "无法推导日志路径"),
                "log_resolution": log_resolution,
            }

    if action in _DIRECTORY_ACTION_MAP and "path" not in params:
        if not node_env:
            return {"error": f"无法找到节点 '{node}' 的环境信息"}

        directory_type = _DIRECTORY_ACTION_MAP[action]
        log_resolution = _resolve_log_target(
            directory_type, node_env, node)

        if log_resolution.get("path"):
            params["path"] = log_resolution["path"]

        if not log_resolution.get("enabled", False):
            return {
                "success": False,
                "action": action,
                "node": node,
                "server": server_name,
                "resolved_params": {"path": log_resolution.get("path", "")},
                "reason": log_resolution.get("reason", "目录未启用或路径无法推导"),
                "log_resolution": log_resolution,
            }

        if not log_resolution.get("path"):
            return {
                "success": False,
                "action": action,
                "node": node,
                "server": server_name,
                "resolved_params": {},
                "reason": log_resolution.get("reason", "无法推导目录路径"),
                "log_resolution": log_resolution,
            }

    # 自动从环境上下文填充参数，精准定位到目标节点
    if node_env:
        # filter 参数：用部署目录做回退过滤；线程类诊断动作也依赖它做进程定位
        if _needs_process_filter_autofill(action) and "filter" not in params:
            if node_env.exec_dir:
                params["filter"] = f"{node_env.exec_dir}/dolphindb"
            elif node_env.port:
                params["filter"] = str(node_env.port)

        # port 参数：用节点端口
        if _needs_port_autofill(action) and "port" not in params:
            if node_env.port:
                params["port"] = node_env.port

        # paths 参数：checkDiskUsage 同时关注部署目录和数据存储目录
        if action == "checkDiskUsage" and "paths" not in params:
            disk_paths = _resolve_node_storage_paths(
                node_env, include_exec_dir=True)
            if disk_paths:
                params["paths"] = " ".join(disk_paths)

        # config_path 参数：用节点配置文件路径
        if action == "checkConfigFile" and "config_path" not in params:
            if node_env.exec_dir:
                cfg_path = _get_config_path(node_env)
                params["config_path"] = cfg_path

        # path 参数：checkSystemRuntime 使用 exec_dir 解析所在磁盘设备
        if action == "checkSystemRuntime" and "path" not in params:
            if node_env.exec_dir:
                params["path"] = node_env.exec_dir

        if action == "findCoreDumps":
            if "search_paths" not in params:
                explicit_search_path = str(
                    params.get("search_path", "") or "").strip()
                if explicit_search_path:
                    params["search_paths"] = explicit_search_path
                else:
                    search_paths = _resolve_core_dump_search_paths(
                        node_env, node)
                    if search_paths:
                        params["search_paths"] = ";".join(search_paths)
            if "search_path" not in params and params.get("search_paths"):
                params["search_path"] = str(
                    params["search_paths"]).split(";", 1)[0]

        if action == "analyzeCoreDump":
            if "exec_path" not in params and node_env.exec_dir:
                import posixpath
                params["exec_path"] = posixpath.join(
                    node_env.exec_dir, "dolphindb")

        # listDirUsage / cleanFile：路径安全校验，必须在节点已知目录范围内
        if action in ("listDirUsage", "cleanFile"):
            target_key = "target_dir" if action == "listDirUsage" else "target_path"
            target = str(params.get(target_key, "")).strip()
            if target:
                allowed_dirs = _resolve_all_allowed_dirs(node_env, node)
                if not _is_path_allowed(target, allowed_dirs):
                    return {
                        "error": f"路径 '{target}' 不在节点 {node} 的已知目录范围内，禁止访问",
                        "allowed_dirs": allowed_dirs,
                    }

    # 构建命令
    command, error = _build_command(template, params, param_schemas)
    if error:
        return {"error": error}

    try:
        server = get_server(server_name)
        if server is None:
            return {"error": f"服务器 '{server_name}' 未在 mcp-config.yaml 中定义"}

        result = await ssh_pool.run_command(
            host=server.host,
            port=server.ssh_port,
            user=server.ssh_user,
            command=command,
            private_key_path=server.ssh_private_key_path or None,
        )

        stdout = result.stdout or ""
        stderr = result.stderr or ""

        def _compact(text: str) -> str:
            if not text:
                return ""
            lines = text.splitlines()
            if len(lines) > max_output_lines:
                lines = lines[:max_output_lines]
                lines.append(f"...(输出已截断，最多保留 {max_output_lines} 行)")
            compacted = "\n".join(lines)
            if len(compacted) > max_output_length:
                compacted = compacted[:max_output_length] + "\n...(输出已截断)"
            return compacted

        stdout = _compact(stdout)
        stderr = _compact(stderr)

        if _resolve_action_log_type(action, params):
            return _build_log_action_result(
                action=action,
                node=node,
                params=params,
                result=result,
                stdout=stdout,
                stderr=stderr,
            )

        if action in _DIRECTORY_ACTION_MAP:
            return _build_directory_action_result(
                action=action,
                node=node,
                directory_type=_DIRECTORY_ACTION_MAP[action],
                path=str(params.get("path", "") or ""),
                result=result,
                stdout=stdout,
                stderr=stderr,
            )

        if action == "findCoreDumps":
            return _build_core_dump_action_result(
                action=action,
                node=node,
                params=params,
                result=result,
                stdout=stdout,
                stderr=stderr,
            )

        return {
            "success": result.returncode == 0,
            "action": action,
            "node": node,
            "server": server_name,
            "resolved_params": params,
            "log_resolution": log_resolution,
            "command": command,
            "returncode": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }

    except Exception as e:
        logger.error("execShell '%s' failed on node %s (server %s): %s",
                     action, node, server_name, e, exc_info=True)
        return {"error": f"操作执行失败: {str(e)}"}
