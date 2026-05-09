"""测试报告：控制台摘要 + 上传后端。"""

import json
import os
from datetime import datetime

import httpx

API_BASE_URL = os.environ.get("TEST_API_URL", "http://192.168.100.43:7901")


def print_console_summary(results: list[dict], env: dict | None = None,
                          report_type: str = "e2e") -> dict:
    """打印控制台摘要，返回 summary dict。"""
    summary = _build_summary(results, env, report_type=report_type)
    _print_console(summary, results)
    return summary


def upload_report(results: list[dict], env: dict | None = None,
                  report_type: str = "e2e") -> None:
    """将测试结果上传到后端。"""
    summary = _build_summary(results, env, report_type=report_type)
    payload = {"summary": summary, "cases": results}
    url = f"{API_BASE_URL.rstrip('/')}/api/v1/test-reports"
    try:
        resp = httpx.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        report_id = data.get("id", "")
        print(f"\n报告已上传: {report_id}")
    except Exception as e:
        print(f"\n报告上传失败: {e}")
        # 上传失败时保存到本地作为 fallback
        fallback_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        )
        with open(fallback_path, "w", encoding="utf-8") as f:
            json.dump({"summary": summary, "cases": results}, f,
                      ensure_ascii=False, indent=2, default=str)
        print(f"  已保存到本地: {fallback_path}")


def _build_summary(results, env=None, report_type: str = "e2e"):
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "pass")
    failed = sum(1 for r in results if r["status"] == "fail")
    errored = sum(1 for r in results if r["status"] == "error")
    skipped = sum(1 for r in results if r["status"] == "skip")
    total_duration = sum(r.get("duration_s", 0) for r in results)
    summary = {
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "report_type": report_type,
        "total": total,
        "passed": passed,
        "failed": failed,
        "errored": errored,
        "skipped": skipped,
        "pass_rate": f"{passed/total*100:.1f}%" if total else "N/A",
        "total_duration_s": round(total_duration, 1),
    }
    if env:
        summary["cluster_name"] = env.get("cluster_name", "")
        summary["target_nodes"] = env.get("target_nodes", [])
    # 关联会话日志（由平台传入 SESSION_ID 环境变量）
    session_id = os.environ.get("SESSION_ID")
    if session_id:
        summary["session_id"] = session_id
    return summary


def _print_console(summary, results):
    print("\n" + "=" * 70)
    print("  AI Agent 自动化闭环测试报告")
    print("=" * 70)
    print(f"  总计: {summary['total']}  通过: {summary['passed']}  "
          f"失败: {summary['failed']}  错误: {summary['errored']}  "
          f"跳过: {summary['skipped']}  通过率: {summary['pass_rate']}")
    print(f"  总耗时: {summary['total_duration_s']}s")
    if summary.get("cluster_name"):
        nodes = ", ".join(summary.get("target_nodes", [])) or "全部节点"
        print(f"  集群: {summary['cluster_name']}  节点: {nodes}")
    print("-" * 70)
    print(f"  {'用例名':<35} {'状态':<8} {'耗时':>8}  {'失败阶段'}")
    print("-" * 70)

    status_icons = {"pass": "✓ 通过", "fail": "✗ 失败",
                    "error": "! 错误", "skip": "- 跳过"}
    for r in results:
        icon = status_icons.get(r["status"], r["status"])
        phase = r.get("phase_failed", "") or ""
        dur = f"{r.get('duration_s', 0):.1f}s"
        print(f"  {r['case_name']:<35} {icon:<8} {dur:>8}  {phase}")

    # 失败用例详情
    failures = [r for r in results if r["status"] in ("fail", "error")]
    if failures:
        print("\n" + "=" * 70)
        print("  失败/错误 用例详情")
        print("=" * 70)
        for r in failures:
            print(f"\n  【{r['case_name']}】阶段: {r.get('phase_failed', '?')}")
            print(f"  错误: {r.get('error_message', 'N/A')}")
            agent = r.get("agent_response")
            if agent:
                print(f"  Agent 成功: {agent.get('success', 'N/A')}, "
                      f"工具调用: {len(agent.get('tool_calls', []))}次, "
                      f"耗时: {agent.get('duration_ms', 0)}ms")
    print()
