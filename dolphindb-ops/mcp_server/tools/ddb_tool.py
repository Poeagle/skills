"""execDdb MCP 工具实现

调用方式（MCP arguments）：
    {
      "action": "<已注册 action 名>",
      "node": "<目标节点名>",
      "params": {...},                    # 可选
      "cluster": "<集群名>",              # 由调用方注入（平台从 env 透传）
      "__source_code_override__": "..."   # 可选：覆盖 startup 中指定 action 函数体
    }

集群拓扑、DDB 凭据来自 mcp-config.yaml，不读取宿主平台的任何模块。
"""

from __future__ import annotations

import logging
from typing import Any

from .. import ddb_pool
from ..cluster_resolver import get_cluster, list_cluster_names
from ..config import load_config
from ..script_registry import get_script_registry

logger = logging.getLogger(__name__)

DEFAULT_MAX_ROWS = 200


def _format_result(result: Any, max_rows: int = DEFAULT_MAX_ROWS) -> Any:
    """将 DolphinDB 返回值转为结构化 JSON 可序列化对象。"""
    if result is None:
        return None

    try:
        import pandas as pd
        if isinstance(result, pd.DataFrame):
            for col in result.columns:
                if pd.api.types.is_datetime64_any_dtype(result[col]):
                    result[col] = result[col].apply(
                        lambda x: x.isoformat() if pd.notna(x) else None)
            total = len(result)
            df_to_convert = result.head(
                max_rows) if total > max_rows else result
            records = df_to_convert.to_dict(orient="records")
            for row in records:
                for k, v in row.items():
                    if isinstance(v, float) and (v != v or v == float("inf") or v == float("-inf")):
                        row[k] = None
            if total > max_rows:
                return {
                    "rows": records,
                    "total_rows": total,
                    "truncated": True,
                    "hint": f"仅显示前 {max_rows} 行（共 {total} 行）",
                }
            return records
        if isinstance(result, pd.Timestamp):
            return result.isoformat() if pd.notna(result) else None
    except ImportError:
        pass

    try:
        import numpy as np
        if isinstance(result, (np.integer,)):
            return int(result)
        if isinstance(result, (np.floating,)):
            v = float(result)
            if v != v or v == float("inf") or v == float("-inf"):
                return None
            return v
        if isinstance(result, np.ndarray):
            lst = result.tolist()
            if len(lst) > max_rows:
                return {"values": lst[:max_rows], "total": len(lst), "truncated": True}
            return lst
    except ImportError:
        pass

    try:
        import datetime
        if isinstance(result, (datetime.datetime, datetime.date)):
            return result.isoformat()
    except Exception:
        pass

    if isinstance(result, dict):
        return {k: _format_result(v, max_rows) for k, v in result.items()}
    if isinstance(result, (list, tuple)):
        return [_format_result(item, max_rows) for item in result]
    if isinstance(result, (int, float, bool, str)):
        if isinstance(result, float) and (result != result or result == float("inf") or result == float("-inf")):
            return None
        return result

    return str(result)


_LLM_SUGGESTION_HINT = (
    "强制渲染规约（不要简化，不要重写代码，不要替换函数名）：\n"
    "你必须按 system prompt 中『operation_suggestion 渲染规约』里的模板章节顺序输出，"
    "包括：当前排查情况 / 推荐 action / **完整函数定义（code 字段原样粘贴到代码块）**"
    " / 调用表达式（call_expression 原样粘贴，不要替换为内置同名函数） / 风险点与执行后果"
    " / 执行前确认事项（含『执行前请先与 DolphinDB 技术支持沟通确认』+『本工具不会代为执行』）。\n"
    "禁止：仅展示函数名、用 DolphinDB 内置同名函数替换 call_expression、给出"
    "『或者直接在 Web Notebook 中运行』等替代执行路径、在用户书面确认前结束本回合。\n"
    "如确实需要本工具代执行（自动化巡检场景），需 mcp-config.yaml 设置 "
    "agent_can_operate: true，且调用时显式传 __confirm__=true。"
)


def _render_ddb_literal(value: Any, ptype: str) -> str:
    """把 Python 值渲染成可粘贴执行的 DDB 字面量。

    优先根据 Python 实际类型判断（int/float/bool），其次才看 ptype 提示。
    这样 vector 这类无元素类型提示的参数也能正确渲染数字元素。
    """
    if isinstance(value, (list, tuple)):
        items = [_render_ddb_literal(item, ptype) for item in value]
        return "[" + ", ".join(items) + "]"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if ptype in ("int", "float", "long"):
        return str(value)
    if ptype == "bool":
        return "true" if bool(value) else "false"
    s = str(value).replace("'", "\\'")
    return f"'{s}'"


def _build_call_expression(action_name: str, params: dict | None,
                           action_def: Any) -> str:
    """生成可拷贝粘贴的 DDB 调用串，如 cancelJobs(['jobA','jobB'], wait=true)。

    必填参数按顺序定位，可选参数用 name=value 形式（避免中间空位错位）。
    """
    if not action_def.params:
        return f"{action_name}()"
    pos_parts: list[str] = []
    named_parts: list[str] = []
    for pname, pdef in action_def.params.items():
        if pdef.required:
            if params and pname in params:
                pos_parts.append(_render_ddb_literal(params[pname], pdef.type))
            else:
                pos_parts.append(f"<{pname}:{pdef.type}>")
        else:
            if params and pname in params:
                named_parts.append(
                    f"{pname}=" + _render_ddb_literal(params[pname], pdef.type))
    return f"{action_name}({', '.join(pos_parts + named_parts)})"


def _build_operation_suggestion(
    action_def: Any, cluster_name: str, node_name: str,
    params: dict | None,
) -> dict:
    config = load_config()
    suggestion_cfg = config.get("operation_suggestion") or {}
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
        "code": action_def.body,
        "call_expression": _build_call_expression(
            action_def.name, params, action_def),
        "execution_methods": suggestion_cfg.get("execution_methods") or [],
        "support_advisory": suggestion_cfg.get("support_advisory") or "",
        "instructions_for_llm": _LLM_SUGGESTION_HINT,
    }


def _build_ddb_call(action_name: str, params: dict | None) -> tuple[str | None, str | None]:
    """构建 DDB 函数调用字符串，返回 (call_str, error)。"""
    action_def = get_script_registry().get_action(action_name)
    if action_def is None or action_def.source != "ddb":
        return None, f"未知的 DDB 操作: {action_name}"

    if not action_def.params:
        return f"{action_name}()", None

    if not params:
        params = {}

    def _safe_scalar(value: Any, pname: str) -> tuple[str | None, str | None]:
        s = str(value)
        if any(c in s for c in [";", "`", "$", "\n", "\r", "'", '"']):
            return None, f"参数 '{pname}' 包含不允许的特殊字符"
        return s, None

    def _render_one(value: Any, ptype: str, pname: str) -> tuple[str | None, str | None]:
        """单个值（含 list 元素）的渲染：Python 实际类型优先，ptype 兜底。"""
        rendered, err = _safe_scalar(value, pname)
        if err is not None:
            return None, err
        if isinstance(value, bool):
            return ("true" if value else "false"), None
        if isinstance(value, (int, float)):
            return str(value), None
        if ptype in ("int", "float", "long"):
            return rendered, None
        if ptype == "bool":
            return ("true" if str(value).strip().lower() in ("true", "1", "yes") else "false"), None
        return f"'{rendered}'", None

    def _render(value: Any, ptype: str, pname: str) -> tuple[str | None, str | None]:
        if isinstance(value, (list, tuple)):
            items: list[str] = []
            for item in value:
                rendered, err = _render_one(item, ptype, pname)
                if err is not None:
                    return None, err
                items.append(rendered)
            return "[" + ", ".join(items) + "]", None
        return _render_one(value, ptype, pname)

    pos_args: list[str] = []
    named_args: list[str] = []
    for pname, pdef in action_def.params.items():
        if pdef.required:
            if pname not in params:
                return None, f"缺少必填参数: {pname}"
            rendered, err = _render(params[pname], pdef.type, pname)
            if err is not None:
                return None, err
            pos_args.append(rendered)
        else:
            if pname in params:
                rendered, err = _render(params[pname], pdef.type, pname)
                if err is not None:
                    return None, err
                named_args.append(f"{pname}={rendered}")

    return f"{action_name}({', '.join(pos_args + named_args)})", None


def ddb_loader_description() -> str:
    base = (
        "在指定的 DolphinDB 数据节点或计算节点上执行预定义操作。\n"
        "只能从白名单中选择操作类型（action），不能传入任意脚本。\n"
        "结果自动转为结构化 JSON（DataFrame 转 records 数组，dict/list 保留原样）。\n"
        "⚠️ 重要：node 必须是 datanode 或 computenode，禁止直连 controller。"
    )
    catalog = get_script_registry().action_catalog(source="ddb")
    if catalog:
        return f"{base}\n\n可用 actions:\n{catalog}"
    return base


def ddb_loader_input_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "操作类型（从白名单中选择）",
                "enum": get_script_registry().get_action_names(source="ddb"),
            },
            "node": {
                "type": "string",
                "description": "目标节点名（datanode 或 computenode，禁止 controller）。HTTP 模式下若 client 配了 X-DolphinDB-Node header，可省略；缺省 server 会报错。",
            },
            "cluster": {
                "type": "string",
                "description": "目标集群名。HTTP 模式下若 client 配了 X-DolphinDB-Cluster header，可省略；backend 集成模式自动注入。",
            },
            "params": {
                "type": "object",
                "description": "操作参数（部分 action 需要，如 cancel_job 需要 jobId）",
            },
        },
        "required": ["action"],
    }


async def call_ddb_exec(
    arguments: dict[str, Any],
    session_state: dict[str, set[str]],
    *,
    default_max_rows: int = DEFAULT_MAX_ROWS,
) -> dict:
    """execDdb 的 MCP 实现。"""
    action = arguments.get("action") or ""
    node = arguments.get("node") or ""
    cluster_name = arguments.get("cluster") or ""
    params = arguments.get("params") if isinstance(
        arguments.get("params"), dict) else None
    source_code_override = arguments.get("__source_code_override__")
    confirm = bool(arguments.get("__confirm__", False))

    registry = get_script_registry()

    action_def = registry.get_action(action)
    if action_def is None or action_def.source != "ddb":
        return {
            "error": f"未知的操作类型: {action}",
            "available_actions": registry.get_action_names(source="ddb"),
        }
    if not action_def.body:
        return {"error": f"操作 '{action}' 函数定义为空"}

    # 操作类（recoverable / irreversible）默认不执行，返回结构化建议给用户
    # HTTP 模式下 token can_operate=false 强制降级；stdio 模式回退全局 agent_can_operate
    if action_def.permission != "readonly":
        from .. import auth as _auth
        cfg = load_config()
        fallback = bool(cfg.get("agent_can_operate"))
        if not (_auth.is_operate_allowed(fallback=fallback) and confirm):
            return _build_operation_suggestion(
                action_def, cluster_name, node, params)

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

    target_node = cluster.find_node(node)
    if target_node is None:
        return {
            "error": f"节点 '{node}' 不存在于集群 '{cluster_name}'",
            "available_nodes": [n.name for n in cluster.nodes],
        }

    call_str, err = _build_ddb_call(action, params)
    if err:
        return {"error": err}

    try:
        session = ddb_pool.get_session(
            host=target_node.host,
            port=target_node.port,
            username=cluster.username,
            password=cluster.password,
        )

        # 每次调用前先注入这一个 action 的 def（DDB 重定义同名 def 是幂等的）。
        # 这取代了原来全局 _ddb_startup 一次性注入所有 def 的方案——好处是隐式
        # 依赖（一个 action 调用另一个 action 内的函数）会立即暴露，而不是被
        # "凡事都先 def 一遍" 掩盖。
        body_to_run = (
            source_code_override
            if isinstance(source_code_override, str) and source_code_override.strip()
            else action_def.body
        )
        session.run(body_to_run)

        raw = session.run(call_str)

        formatted = _format_result(raw, max_rows=default_max_rows)
        return {
            "success": True,
            "action": action,
            "cluster": cluster_name,
            "node": target_node.name,
            "result": formatted,
        }
    except Exception as e:
        # 连接异常时清理缓存以便下次重连
        ddb_pool.invalidate(target_node.host, target_node.port, cluster.username)
        logger.error(
            "execDdb '%s' on %s/%s failed: %s",
            action, cluster_name, node, e, exc_info=True)
        return {"error": f"操作执行失败: {str(e)}"}
