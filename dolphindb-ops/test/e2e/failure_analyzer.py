import json
import os
from typing import Any

from agent_client import AgentClient


ANALYSIS_TIMEOUT = int(os.environ.get("TEST_FAILURE_ANALYSIS_TIMEOUT", "120"))
ANALYSIS_ENABLED = os.environ.get(
    "TEST_FAILURE_ANALYSIS", "true").lower() == "true"

_MAX_TEXT = 4000
_MAX_RESULT = 1200
_MAX_EVENTS = 25
_MAX_TOOL_CALLS = 10
_MAX_SOURCE = 2000


def _clip_text(value: Any, limit: int) -> str:
    text = value if isinstance(value, str) else json.dumps(
        value, ensure_ascii=False, default=str)
    if len(text) <= limit:
        return text
    head = max(limit - 120, 0)
    return text[:head] + "\n...<truncated>...\n" + text[-100:]


def _compact_events(events: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for ev in (events or [])[-_MAX_EVENTS:]:
        compact.append({
            "type": ev.get("type"),
            "id": ev.get("id"),
            "name": ev.get("name"),
            "success": ev.get("success"),
            "duration_ms": ev.get("duration_ms"),
            "content": _clip_text(ev.get("content", ""), 600),
            "arguments": ev.get("arguments", {}),
            "result": _clip_text(ev.get("result", ""), 600),
        })
    return compact


def _compact_tool_calls(tool_calls: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for call in (tool_calls or [])[-_MAX_TOOL_CALLS:]:
        compact.append({
            "name": call.get("name"),
            "arguments": call.get("arguments", {}),
            "success": call.get("success"),
            "duration_ms": call.get("duration_ms"),
            "result": _clip_text(call.get("result", ""), _MAX_RESULT),
        })
    return compact


def _extract_json_block(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except Exception:
        return None


def build_failure_context(result: dict[str, Any]) -> dict[str, Any]:
    agent = result.get("agent_response") or {}
    return {
        "case_name": result.get("case_name"),
        "status": result.get("status"),
        "phase_failed": result.get("phase_failed"),
        "error_message": _clip_text(result.get("error_message", ""), 1200),
        "prompt": _clip_text(result.get("prompt", ""), 1200),
        "cleanup_source": _clip_text(result.get("cleanup_source", ""), _MAX_SOURCE),
        "fault_injector_source": _clip_text(result.get("fault_injector_source", ""), _MAX_SOURCE),
        "health_checker_source": _clip_text(result.get("health_checker_source", ""), _MAX_SOURCE),
        "agent_content": _clip_text(agent.get("content", ""), _MAX_TEXT),
        "agent_has_error": agent.get("has_error"),
        "agent_success": agent.get("success"),
        "agent_duration_ms": agent.get("duration_ms"),
        "tool_calls": _compact_tool_calls(agent.get("tool_calls") or []),
        "events": _compact_events(agent.get("events") or []),
    }


def _build_prompt(context: dict[str, Any]) -> str:
    context_text = json.dumps(context, ensure_ascii=False, indent=2)
    return (
        "你是 DolphinDB 运维测试失败复盘分析器。你的任务是基于给定记录做事后分析。"
        "禁止调用任何工具，禁止提出需要额外采集数据的建议，禁止执行修复动作。"
        "请只输出一个 JSON 对象，不要输出 Markdown，不要输出代码块。"
        "\n\n"
        "输出字段必须包含："
        "analysis_summary, root_cause, failure_type, why_not_fixed, "
        "improvement_suggestions, evidence, confidence。"
        "\n"
        "其中 failure_type 只能取：prompt_routing, wrong_tool_choice, tool_timeout, partial_fix, verification_gap, test_bug, env_issue, unknown。"
        "\n"
        "improvement_suggestions 必须是字符串数组，evidence 必须是字符串数组，confidence 取 high/medium/low。"
        "\n"
        "如果判断是测试基础设施或测试用例问题，而不是 Agent 决策问题，必须明确指出。"
        "\n\n"
        "失败记录如下：\n" + context_text
    )


def analyze_failure(result: dict[str, Any]) -> dict[str, Any] | None:
    if not ANALYSIS_ENABLED:
        return None

    context = build_failure_context(result)
    client = AgentClient()
    resp = client.ask(prompt=_build_prompt(context),
                      timeout=ANALYSIS_TIMEOUT, verbose=False)

    parsed = _extract_json_block(resp.content)
    analysis = parsed or {
        "analysis_summary": _clip_text(resp.content or resp.error_message or "失败复盘分析未返回结构化结果", 1500),
        "root_cause": "模型未返回可解析的结构化 JSON",
        "failure_type": "unknown",
        "why_not_fixed": "失败复盘结果不可结构化解析",
        "improvement_suggestions": ["检查 failure analyzer prompt 是否过于宽松", "限制输出必须为 JSON 对象"],
        "evidence": ["failure analyzer 原始输出无法解析为 JSON"],
        "confidence": "low",
    }

    analysis["analyzer_meta"] = {
        "success": resp.success,
        "has_error": resp.has_error,
        "error_message": resp.error_message,
        "duration_ms": resp.duration_ms,
        "tool_calls": len(resp.tool_calls),
    }
    analysis["failure_context"] = context
    return analysis
