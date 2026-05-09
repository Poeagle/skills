"""DolphinDB / Shell Action 白名单测试脚本

逐个执行 scripts/dolphindb/*.dos 和 scripts/shell/*.sh 中的 action，
验证脚本/命令能否在真实节点上正常运行，输出详细的成功/失败报告。

使用方法:
    python test_actions.py --cluster <集群名> --node <节点名>
    python test_actions.py --cluster ddb-2001011 --node local7908
    python test_actions.py --cluster ddb-2001011 --node local7908 --only ddb
    python test_actions.py --cluster ddb-2001011 --node local7908 --action mem
"""

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

# 路径定位：当前文件在 skills/dolphindb-ops/test/ 下
_TEST_DIR = Path(__file__).resolve().parent
_SKILL_ROOT = _TEST_DIR.parent                         # skills/dolphindb-ops/

# 把 skill 根加 sys.path 以 import 自包含的 mcp_server.script_registry
sys.path.insert(0, str(_SKILL_ROOT))
sys.path.insert(0, str(_TEST_DIR))                     # 让 from report 也能找到

from mcp_server.script_registry import ScriptRegistry  # noqa: E402
from report import upload_report  # noqa: E402

DEFAULT_BASE_URL = "http://192.168.100.43:7901"
DEFAULT_API_KEY = "sk-ops-test-key-001"

SCRIPTS_DIR = _SKILL_ROOT / "scripts"

# 为需要参数的 action 提供测试参数
# 未列出的 action 不需要参数，直接调用即可
# 如果无法提供参数，留空 {}，让服务端报出具体缺少的参数名
DDB_TEST_PARAMS: dict[str, dict] = {
    "checkChunkDetail": {},          # 需要 dbPath
    "cancelJobs": {},                # 三选一参数：jobIds / userId / all
    "cancelConsoleJobs": {},         # 需要 jobIds
    "closeSessions1": {},            # 四选一参数
    "undefSharedVars": {},           # 二选一参数
    "dropStreamEngines": {},         # 需要 names
    "unsubscribeStreaming": {},      # 二选一参数
    "deleteReplica": {},             # 需要 chunkId / scope / node
    "updateChunkVersion": {},        # 需要 chunkId / version / target
}

# 结果截断长度
RESULT_PREVIEW_MAX = 300

SHELL_TEST_PARAMS: dict[str, dict] = {
    # getLogs / tailLogs: log_type 由用户指定，path 由 shell_tool 根据 env 自动填充
    "getLogs": {"log_type": "runtime", "pattern": "error|ERROR", "lines": 10},
    "tailLogs": {"log_type": "runtime", "lines": 20},
    # 目录类 action（trace / batch_job）保留独立 action，path 由 shell_tool 根据 env 自动填充
    "listTraceFiles": {"limit": 5},
    "tailTraceFile": {"lines": 20},
    "getTraceFile": {"pattern": "error|ERROR", "lines": 10},
    "searchTraceFiles": {"pattern": "error|ERROR", "lines": 10},
    "listBatchJobFiles": {"limit": 5},
    "tailBatchJobFile": {"lines": 20},
    "getBatchJobFile": {"pattern": "error|ERROR", "lines": 10},
    "searchBatchJobFiles": {"pattern": "error|ERROR", "lines": 10},
    # checkProcessAll: filter 由 shell_tool 根据 env.exec_dir 自动填充
    # findCoreDumps: search_paths 由 shell_tool 根据 core_pattern 和节点相关目录自动填充
}


def _classify_expected_skip(action: str, inner_result: object, error: str | None) -> str | None:
    if error and error.startswith("缺少必填参数:"):
        return error

    if not isinstance(inner_result, dict):
        return None

    reason = str(inner_result.get("reason", "") or "")
    if reason.startswith("未满足启用条件:"):
        return reason
    if reason.startswith("log file not found:"):
        return reason
    if reason.startswith("trace directory not found:"):
        return reason
    if reason.startswith("batch job directory not found:"):
        return reason
    if reason.startswith("trace file not found:"):
        return reason
    if reason.startswith("batch job file not found:"):
        return reason
    if reason.startswith("raw script log not found:"):
        return reason
    if reason.startswith("raw script log not found in directory:"):
        return reason
    if reason.startswith("redo log not found:"):
        return reason
    if reason.startswith("redo log not found in directory:"):
        return reason
    if reason.startswith("no trace file found in directory:"):
        return reason
    if reason.startswith("no batch job file found in directory:"):
        return reason
    if reason.startswith("无法推导日志路径"):
        return reason
    if "节点不产生" in reason:
        return reason

    inner_error = str(inner_result.get("error", "") or "")
    if "only supported on controller" in inner_error:
        return inner_error
    if "must be executed on an initialized controller" in inner_error:
        return inner_error

    return None


def _build_shell_params(action: str, node: str) -> dict:
    """根据 action 和节点名动态构建测试参数

    大部分参数由 shell_tool 根据环境上下文自动填充，
    此处只提供 env 无法自动推断的参数。
    """
    dynamic = {
        # checkProcessAll: filter 由 shell_tool 根据 env.exec_dir 自动填充
        # findCoreDumps: search_paths 由 shell_tool 根据 core_pattern 和节点相关目录自动填充
    }
    if action in dynamic:
        return dynamic[action]
    return SHELL_TEST_PARAMS.get(action, {})


def _extract_result_text(inner_result: object) -> str:
    """从 action 执行结果中提取完整的可展示文本。"""
    if not isinstance(inner_result, dict):
        return json.dumps(inner_result, ensure_ascii=False, default=str)

    # 优先 stdout / content
    text = inner_result.get("stdout", "") or inner_result.get("content", "")
    if text:
        return text

    # DDB result
    if inner_result.get("result") is not None:
        return json.dumps(inner_result["result"], ensure_ascii=False, indent=2, default=str)

    # records / entries
    for key in ("records", "entries"):
        if inner_result.get(key) is not None:
            return json.dumps(inner_result[key], ensure_ascii=False, indent=2, default=str)

    # fallback: 整个 inner_result
    return json.dumps(inner_result, ensure_ascii=False, indent=2, default=str)


def load_registry() -> ScriptRegistry:
    """加载 ScriptRegistry"""
    if not SCRIPTS_DIR.exists():
        print(f"❌ 脚本目录不存在: {SCRIPTS_DIR}")
        sys.exit(1)
    registry = ScriptRegistry(SCRIPTS_DIR)
    stats = registry.scan()
    print(
        f"  📦 已加载: {stats['ddb']} DDB actions, {stats['shell']} Shell actions")
    return registry


def validate_registry_structure(registry: ScriptRegistry) -> list[str]:
    """校验 ScriptRegistry 中的 action 结构完整性，返回警告列表"""
    warnings = []
    for name, action_def in registry.get_actions().items():
        if not action_def.description:
            warnings.append(f"[{action_def.source}] {name}: 缺少 description")

        if action_def.source == "ddb" and not action_def.body:
            warnings.append(f"[ddb] {name}: 函数体为空")

        if action_def.source == "shell" and not action_def.body:
            warnings.append(f"[shell] {name}: 命令模板为空")

        # 校验 shell 模板中的变量引用
        if action_def.source == "shell" and action_def.body:
            import re
            cleaned = re.sub(r'\{\{\w+\}\}', '', action_def.body)
            # 提取所有 {xxx} 格式的变量
            all_vars = set(re.findall(r"\{(\w+)\}", cleaned))

            # 排除 awk 关键字和 shell 位置参数
            awk_keywords = {'print', 'next', 'exit', 'getline', 'printf'}
            template_vars = {
                v for v in all_vars
                if v not in awk_keywords and not v.isdigit()
            }

            param_keys = set(action_def.params.keys())
            missing = template_vars - param_keys
            if missing:
                warnings.append(
                    f"[shell] {name}: 模板引用了未定义的参数 {missing}")

    return warnings


def call_action_test(
    base_url: str,
    api_key: str,
    tool: str,
    action: str,
    node: str,
    cluster: str,
    params: dict | None = None,
    timeout: int = 30,
) -> dict:
    """调用 /actions/test 端点"""
    url = f"{base_url}/api/v1/agent/actions/test"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "tool": tool,
        "action": action,
        "node": node,
        "cluster": cluster,
        "params": params or {},
    }
    resp = httpx.post(url, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def run_tests(
    base_url: str,
    api_key: str,
    cluster: str,
    node: str,
    tool_filter: str | None = None,
    action_filter: str | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """执行所有测试，返回 (passed, failed, skipped)"""
    passed, failed, skipped = [], [], []

    registry = load_registry()

    # 结构校验
    print("━" * 70)
    print("📋 脚本结构校验")
    print("━" * 70)
    warnings = validate_registry_structure(registry)
    if warnings:
        for w in warnings:
            print(f"  ⚠️  {w}")
    else:
        print("  ✅ 所有 action 结构正确")
    print()

    # 构建测试列表
    tests: list[tuple[str, str, dict]] = []
    all_actions = registry.get_actions()

    if tool_filter in (None, "ddb"):
        for name in sorted(registry.get_actions(source="ddb").keys()):
            if action_filter and name != action_filter:
                continue
            params = DDB_TEST_PARAMS.get(name, {})
            tests.append(("execDdb", name, params))

    if tool_filter in (None, "shell"):
        for name in sorted(registry.get_actions(source="shell").keys()):
            if action_filter and name != action_filter:
                continue
            params = _build_shell_params(name, node)
            tests.append(("execShell", name, params))

    # 执行测试
    print("━" * 70)
    print(f"🧪 执行测试 ({len(tests)} 个 action)")
    print(f"   集群: {cluster}  节点: {node}")
    print("━" * 70)

    env_printed = False

    for tool, action, params in tests:
        label = f"[{tool}] {action}"
        action_def = all_actions.get(action)
        source_code = action_def.body if action_def else ""
        try:
            start = time.monotonic()
            result = call_action_test(
                base_url=base_url,
                api_key=api_key,
                tool=tool,
                action=action,
                node=node,
                cluster=cluster,
                params=params,
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)

            # env 信息只在第一个 action 时输出一次
            if not env_printed:
                env_info = result.get("env") or {}
                if env_info:
                    print()
                    print("  📌 环境上下文 (env):")
                    print(f"     cluster_name: {env_info.get('cluster_name')}")
                    print("     target_nodes:", json.dumps(
                        env_info.get("target_nodes", []), ensure_ascii=False, default=str))
                    print("     server_names:", json.dumps(
                        env_info.get("server_names", []), ensure_ascii=False, default=str))
                    node_info = env_info.get("target_node") or {}
                    if node_info:
                        print("     target_node:")
                        for key, value in node_info.items():
                            print(
                                f"       - {key}: {json.dumps(value, ensure_ascii=False, default=str)}")
                    print()
                env_printed = True

            success = result.get("success", False)
            inner_result = result.get("result", {})
            error = result.get("error") or (
                inner_result.get("error") if isinstance(
                    inner_result, dict) else None
            )

            # 提取该 action 实际使用的参数（含自动填充）
            resolved = inner_result.get(
                "resolved_params") if isinstance(inner_result, dict) else None

            skip_reason = _classify_expected_skip(action, inner_result, error)
            if skip_reason:
                print(f"  ⏭️  {label:<35} ({elapsed_ms}ms)")
                if resolved:
                    print(
                        f"     参数: {json.dumps(resolved, ensure_ascii=False, default=str)}")
                print(f"     跳过: {skip_reason}")
                skipped.append({
                    "tool": tool, "action": action,
                    "duration_ms": elapsed_ms,
                    "reason": skip_reason,
                    "input_params": params,
                    "resolved_params": resolved,
                    "source_code": source_code})
                continue

            # shell 命令 returncode 1 且无 stderr 表示"无匹配数据"而非执行失败
            # 如 checkProcessAll grep 无匹配、findCoreDumps 未找到文件
            if (
                not success
                and not error
                and isinstance(inner_result, dict)
                and inner_result.get("returncode") == 1
                and not inner_result.get("stderr")
            ):
                success = True

            if success:
                # 构建结果预览
                preview = ""
                if isinstance(inner_result, dict):
                    actual = inner_result.get("result")
                    if actual is not None:
                        preview = json.dumps(
                            actual, ensure_ascii=False, default=str)
                    else:
                        preview = json.dumps(
                            inner_result, ensure_ascii=False, default=str)
                else:
                    preview = json.dumps(
                        inner_result, ensure_ascii=False, default=str)
                if len(preview) > RESULT_PREVIEW_MAX:
                    preview = preview[:RESULT_PREVIEW_MAX] + "..."
                print(f"  ✅ {label:<35} ({elapsed_ms}ms)")
                if resolved:
                    print(
                        f"     参数: {json.dumps(resolved, ensure_ascii=False, default=str)}")
                # 显示命令实际输出（stdout）
                if isinstance(inner_result, dict):
                    stdout = inner_result.get("stdout", "")
                    if not stdout:
                        stdout = inner_result.get("content", "")
                    if stdout:
                        stdout_preview = stdout[:500]
                        if len(stdout) > 500:
                            stdout_preview += "..."
                        print(f"     输出: {stdout_preview}")
                    elif inner_result.get("result") is not None:
                        # DDB actions 的结果在 result 字段
                        result_str = json.dumps(
                            inner_result["result"], ensure_ascii=False, default=str)
                        if len(result_str) > 500:
                            result_str = result_str[:500] + "..."
                        print(f"     输出: {result_str}")
                    elif inner_result.get("records") is not None:
                        records_str = json.dumps(
                            inner_result["records"][:3], ensure_ascii=False, default=str)
                        if len(records_str) > 500:
                            records_str = records_str[:500] + "..."
                        print(f"     输出: {records_str}")
                    elif inner_result.get("entries") is not None:
                        entries_str = json.dumps(
                            inner_result["entries"][:3], ensure_ascii=False, default=str)
                        if len(entries_str) > 500:
                            entries_str = entries_str[:500] + "..."
                        print(f"     输出: {entries_str}")
                passed.append({
                    "tool": tool, "action": action,
                    "duration_ms": elapsed_ms,
                    "input_params": params,
                    "resolved_params": resolved,
                    "full_result": _extract_result_text(inner_result),
                    "source_code": source_code})
            else:
                print(f"  ❌ {label:<35} ({elapsed_ms}ms)")
                if resolved:
                    print(
                        f"     参数: {json.dumps(resolved, ensure_ascii=False, default=str)}")
                if error:
                    print(f"     错误: {error}")
                else:
                    if isinstance(inner_result, dict):
                        stdout = inner_result.get("stdout", "")
                        if not stdout:
                            stdout = inner_result.get("content", "")
                        if stdout:
                            stdout_preview = stdout[:500]
                            if len(stdout) > 500:
                                stdout_preview += "..."
                            print(f"     输出: {stdout_preview}")
                    # 打印完整返回以便调试
                    detail = json.dumps(
                        inner_result, ensure_ascii=False, indent=2)
                    if len(detail) > 500:
                        detail = detail[:500] + "..."
                    print(f"     返回: {detail}")
                failed.append({
                    "tool": tool, "action": action,
                    "duration_ms": elapsed_ms,
                    "error": error or str(inner_result),
                    "input_params": params,
                    "resolved_params": resolved,
                    "full_result": _extract_result_text(inner_result),
                    "source_code": source_code})

        except httpx.ConnectError:
            print(f"  ❌ {label:<35} 连接失败")
            failed.append({
                "tool": tool, "action": action,
                "error": "连接失败"})
        except httpx.TimeoutException:
            print(f"  ❌ {label:<35} 超时")
            failed.append({
                "tool": tool, "action": action,
                "error": "请求超时"})
        except httpx.HTTPStatusError as e:
            print(f"  ❌ {label:<35} HTTP {e.response.status_code}")
            try:
                detail = e.response.json()
                print(f"     详情: {detail}")
            except Exception:
                print(f"     响应: {e.response.text[:300]}")
            failed.append({
                "tool": tool, "action": action,
                "error": f"HTTP {e.response.status_code}"})
        except Exception as e:
            print(f"  ❌ {label:<35} 异常: {e}")
            failed.append({
                "tool": tool, "action": action,
                "error": str(e)})

    return passed, failed, skipped


def print_summary(
    passed: list[dict],
    failed: list[dict],
    skipped: list[dict],
) -> None:
    """打印测试汇总"""
    total = len(passed) + len(failed) + len(skipped)

    print()
    print("━" * 70)
    print("📊 测试汇总")
    print("━" * 70)
    print(
        f"  总计: {total}  通过: {len(passed)}  失败: {len(failed)}  跳过: {len(skipped)}")
    print()

    if failed:
        print("  ❌ 失败的 action:")
        for f in failed:
            print(
                f"     - [{f['tool']}] {f['action']}: {f.get('error', '未知错误')}")
        print()

    if skipped:
        print("  ⏭️  跳过的 action:")
        for s in skipped:
            print(f"     - [{s['tool']}] {s['action']}: {s['reason']}")

    print("━" * 70)


def _to_report_cases(
    passed: list[dict],
    failed: list[dict],
    skipped: list[dict],
) -> list[dict]:
    """将 passed/failed/skipped 转换为 report.py 统一的 cases 格式。"""
    cases: list[dict] = []
    for r in passed:
        cases.append({
            "case_name": f"[{r['tool']}] {r['action']}",
            "status": "pass",
            "duration_s": round(r.get("duration_ms", 0) / 1000, 2),
            "input_params": r.get("input_params") or {},
            "resolved_params": r.get("resolved_params"),
            "full_result": r.get("full_result", ""),
            "source_code": r.get("source_code", ""),
        })
    for r in failed:
        cases.append({
            "case_name": f"[{r['tool']}] {r['action']}",
            "status": "fail",
            "error_message": r.get("error", ""),
            "duration_s": round(r.get("duration_ms", 0) / 1000, 2),
            "input_params": r.get("input_params") or {},
            "resolved_params": r.get("resolved_params"),
            "full_result": r.get("full_result", ""),
            "source_code": r.get("source_code", ""),
        })
    for r in skipped:
        cases.append({
            "case_name": f"[{r['tool']}] {r['action']}",
            "status": "skip",
            "error_message": r.get("reason", ""),
            "duration_s": round(r.get("duration_ms", 0) / 1000, 2),
            "input_params": r.get("input_params") or {},
            "resolved_params": r.get("resolved_params"),
            "source_code": r.get("source_code", ""),
        })
    return cases


def main():
    parser = argparse.ArgumentParser(
        description="DolphinDB / Shell Action 白名单测试")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="后端地址")
    parser.add_argument("--api-key", default=DEFAULT_API_KEY, help="API Key")
    parser.add_argument("--cluster", required=True, help="目标集群名")
    parser.add_argument("--node", required=True, help="目标节点名")
    parser.add_argument("--only", choices=["ddb", "shell"],
                        default=None, help="只测试 ddb 或 shell")
    parser.add_argument("--action", default=None,
                        help="只测试指定 action（如 mem、checkDiskUsage）")
    parser.add_argument("--upload", action="store_true",
                        help="将测试结果上传到前端报告页面")
    args = parser.parse_args()

    passed, failed, skipped = run_tests(
        base_url=args.base_url,
        api_key=args.api_key,
        cluster=args.cluster,
        node=args.node,
        tool_filter=args.only,
        action_filter=args.action,
    )

    print_summary(passed, failed, skipped)

    if args.upload:
        cases = _to_report_cases(passed, failed, skipped)
        env = {"cluster_name": args.cluster, "target_nodes": [args.node]}
        upload_report(cases, env=env, report_type="action")

    # 退出码: 失败数
    sys.exit(len(failed))


if __name__ == "__main__":
    main()
