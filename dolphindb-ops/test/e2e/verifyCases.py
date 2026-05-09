import os
import sys
import inspect
import importlib
import random
import time
from pathlib import Path

# report.py 在 test/（e2e/ 上一级），先把 test/ 加到 sys.path 再 import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_client import AgentClient  # noqa: E402
from failure_analyzer import analyze_failure  # noqa: E402
from report import upload_report, print_console_summary  # noqa: E402

# ── 环境变量（DolphinDB 连接） ──────────────────────────
os.environ.setdefault("DDB_IP", "192.168.100.44")
os.environ.setdefault("DDB_PORT", "7932")
os.environ.setdefault("DDB_USER", "admin")
os.environ.setdefault("DDB_PASSWORD", "123456")


# ── Prompt 配置 ──────────────────────────────────────
# 【测试模式】前缀会强制 Agent 执行修复操作
_TEST_MODE_PREFIX = "【自动化测试模式】你必须实际执行修复操作，不能只给建议。\n"
DEFAULT_PROMPT = "当前 DolphinDB 节点可能存在异常，请进行全面诊断并修复"

# ── Agent 配置 ────────────────────────────────────────
CLUSTER_NAME = os.environ.get("TEST_CLUSTER", "ddb-test")
TARGET_NODES = os.environ.get("TEST_NODES", "P2-dnode1").split(",")
AGENT_TIMEOUT = int(os.environ.get("TEST_AGENT_TIMEOUT", "300"))


def load_and_run_cases(case_dir="cases", case_filter=None):
    """
    加载并运行测试用例。
    case_filter: 可选，用例类名（如 "TestMemoryHighUsage"），只运行匹配的用例。
    """
    sys.path.append(os.path.abspath(case_dir))
    agent = AgentClient()
    results = []

    for filename in sorted(os.listdir(case_dir)):
        if not filename.endswith(".py") or filename.startswith("__"):
            continue
        module_name = filename[:-3]
        if module_name == "Test":
            continue

        module = importlib.import_module(module_name)

        for name, obj in inspect.getmembers(module):
            if not (name.startswith("Test") and name != "Test"):
                continue
            # P4: 支持只跑指定用例
            if case_filter and name != case_filter:
                continue

            print(f"\n{'='*60}")
            print(f"  用例: {name}")
            print(f"{'='*60}")

            result = {
                "case_name": name,
                "status": "pass",
                "phase_failed": None,
                "error_message": None,
                "agent_response": None,
                "failure_analysis": None,
                "failure_analysis_error": None,
                "prompt": None,
                "duration_s": 0,
            }
            start = time.time()
            case_instance = None
            phase = "init"

            try:
                # ① 实例化 + 预清理
                phase = "cleanup"
                case_instance = obj()

                # 打印 cleanup 源码
                try:
                    src = inspect.getsource(type(case_instance).cleanup)
                    result["cleanup_source"] = src
                    print(f"  ── cleanup 源码 ──")
                    for line in src.splitlines():
                        print(f"  │ {line}")
                    print(f"  ──────────────────")
                except Exception:
                    pass

                print("  [1/5] cleanup ...", end=" ", flush=True)
                case_instance.cleanup()
                print("OK")

                # ② 制造故障
                phase = "fault_injector"

                # 打印 fault_injector 源码
                try:
                    src = inspect.getsource(type(case_instance).fault_injector)
                    result["fault_injector_source"] = src
                    print(f"  ── fault_injector 源码 ──")
                    for line in src.splitlines():
                        print(f"  │ {line}")
                    print(f"  ──────────────────────────")
                except Exception:
                    pass

                print("  [2/5] fault_injector ...", end=" ", flush=True)
                case_instance.fault_injector()
                print("OK")

                # ③ 调用 AI Agent 诊断修复（P1: 测试模式前缀强制执行修复）
                phase = "agent"
                prompt_pool = getattr(case_instance, 'questions', None) or [
                    DEFAULT_PROMPT]
                if isinstance(prompt_pool, str):
                    prompt_pool = [prompt_pool]
                raw_prompt = random.choice(prompt_pool)
                prompt = _TEST_MODE_PREFIX + raw_prompt
                result["prompt"] = prompt
                print(f"  [3/5] agent prompt: \"{prompt}\"", flush=True)
                agent_resp = agent.ask(
                    prompt=prompt,
                    cluster_name=CLUSTER_NAME,
                    target_nodes=TARGET_NODES,
                    timeout=AGENT_TIMEOUT,
                )
                result["agent_response"] = {
                    "prompt": prompt,
                    "env": {"cluster_name": CLUSTER_NAME, "target_nodes": TARGET_NODES},
                    "success": agent_resp.success,
                    "content": agent_resp.content,
                    "events": agent_resp.events,
                    "tool_calls": agent_resp.tool_calls,
                    "has_error": agent_resp.has_error,
                    "duration_ms": agent_resp.duration_ms,
                }
                # P5: 连接失败或 Agent 返回 error 事件都触发异常
                if agent_resp.error_message:
                    raise RuntimeError(
                        f"Agent 调用失败: {agent_resp.error_message}")
                if agent_resp.has_error:
                    raise RuntimeError("Agent 执行过程中发生错误")
                print(
                    f"       Agent 完成: 工具调用 {len(agent_resp.tool_calls)} 次, "
                    f"耗时 {agent_resp.duration_ms}ms")

                # ④ 验证修复结果
                phase = "health_checker"
                print("  [4/5] health_checker ...", end=" ", flush=True)
                case_instance.health_checker()
                print("OK")

                print(f"  ✓ 【{name}】测试通过！")

            except Exception as e:
                result["status"] = "fail" if phase == "health_checker" else "error"
                result["phase_failed"] = phase
                result["error_message"] = str(e)
                print(f"\n  ✗ 【{name}】{result['status']}: {e}")
                if case_instance:
                    try:
                        result.setdefault(
                            "health_checker_source",
                            inspect.getsource(
                                type(case_instance).health_checker),
                        )
                    except Exception:
                        pass
                try:
                    result["failure_analysis"] = analyze_failure(result)
                except Exception as analysis_error:
                    result["failure_analysis_error"] = str(analysis_error)
            finally:
                # ⑤ 善后清理
                if case_instance:
                    try:
                        print("  [5/5] cleanup ...", end=" ", flush=True)
                        case_instance.cleanup()
                        print("OK")
                    except Exception as e:
                        print(f"清理失败: {e}")
                    # P2: 关闭 DDB 连接
                    try:
                        case_instance.closeConnection()
                    except Exception:
                        pass

            result["duration_s"] = round(time.time() - start, 1)
            results.append(result)

    # 控制台摘要 + 上传报告到后端
    env = {"cluster_name": CLUSTER_NAME, "target_nodes": TARGET_NODES}
    print_console_summary(results, env, report_type="e2e")
    upload_report(results, env, report_type="e2e")
    return results


if __name__ == "__main__":
    # P4: 支持 python verifyCases.py TestMemoryHighUsage
    case_filter = sys.argv[1] if len(sys.argv) > 1 else None
    load_and_run_cases(case_filter=case_filter)
