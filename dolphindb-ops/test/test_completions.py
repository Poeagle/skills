"""Agent Completions API 测试脚本（同步 / 流式）

使用方法:
    python test_completions.py [--stream] [--base-url URL] [--api-key KEY] [--cluster NAME]

示例:
    python test_completions.py -q "你好"
    python test_completions.py --stream -q "检查内存" --cluster ddb-2001011 --nodes local7908
    python test_completions.py --api-key sk-ops-test-key-001
"""

import argparse
import json
import sys

import httpx

DEFAULT_BASE_URL = "http://192.168.100.43:7901"
DEFAULT_API_KEY = "sk-ops-test-key-001"
DEFAULT_TIMEOUT = 120


def test_completions(
    base_url: str,
    api_key: str,
    question: str,
    cluster_name: str | None = None,
    target_nodes: list[str] | None = None,
    conversation_id: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    """调用 /completions 接口并返回结果"""
    url = f"{base_url}/api/v1/agent/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload: dict = {
        "messages": [{"role": "user", "content": question}],
        "stream": False,
        "timeout": timeout,
    }

    if cluster_name:
        payload["env"] = {
            "cluster_name": cluster_name,
            "target_nodes": target_nodes or [],
        }

    if conversation_id:
        payload["conversation_id"] = conversation_id

    print(f"📤 请求: {question}")
    if cluster_name:
        print(f"   环境: {cluster_name} → {target_nodes or '全部节点'}")
    print(f"   超时: {timeout}s")
    print()

    resp = httpx.post(url, headers=headers,
                      json=payload, timeout=timeout + 10)
    resp.raise_for_status()
    return resp.json()


def print_result(result: dict) -> None:
    """格式化打印返回结果"""
    print("=" * 60)
    print(f"✅ 成功: {result.get('success')}")
    print(f"🤖 模型: {result.get('model')}")
    print(f"📊 统计: {json.dumps(result.get('stats', {}), ensure_ascii=False)}")
    print("=" * 60)

    # 按时序打印 events
    events = result.get("events", [])
    print(f"\n📋 事件流 ({len(events)} 个事件):\n")

    for i, event in enumerate(events):
        etype = event.get("type")
        if etype == "text":
            content = event.get("content", "")
            # 文本内容直接输出
            print(content, end="")
        elif etype == "tool_call":
            name = event.get("name", "")
            args = json.dumps(event.get("arguments", {}), ensure_ascii=False)
            success = "✅" if event.get("success") else "❌"
            duration = event.get("duration_ms", 0)
            result_str = event.get("result", "")
            # 截断过长的结果
            if len(result_str) > 200:
                result_str = result_str[:200] + "..."
            print(f"\n  ┌─ 🔧 {name} {success} ({duration}ms)")
            print(f"  │  参数: {args}")
            print(f"  └─ 结果: {result_str}\n")
        elif etype == "error":
            print(f"\n  ❌ 错误: {event.get('content', '')}\n")

    # 建议
    suggestions = result.get("suggestions", [])
    if suggestions:
        print(f"\n💡 建议: {', '.join(suggestions)}")

    print("\n" + "=" * 60)


def test_stream(
    base_url: str,
    api_key: str,
    question: str,
    cluster_name: str | None = None,
    target_nodes: list[str] | None = None,
    conversation_id: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> None:
    """调用 /completions 接口的流式模式，实时输出"""
    url = f"{base_url}/api/v1/agent/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload: dict = {
        "messages": [{"role": "user", "content": question}],
        "stream": True,
    }

    if cluster_name:
        payload["env"] = {
            "cluster_name": cluster_name,
            "target_nodes": target_nodes or [],
        }

    if conversation_id:
        payload["conversation_id"] = conversation_id

    print(f"📤 请求: {question}")
    if cluster_name:
        print(f"   环境: {cluster_name} → {target_nodes or '全部节点'}")
    print(f"   模式: 流式 (SSE)")
    print("─" * 60)

    with httpx.stream("POST", url, headers=headers, json=payload,
                      timeout=timeout + 10) as resp:
        resp.raise_for_status()

        for line in resp.iter_lines():
            if not line or not line.startswith("data: "):
                continue

            try:
                event = json.loads(line[6:])
            except json.JSONDecodeError:
                continue

            etype = event.get("type")

            if etype == "text":
                print(event.get("content", ""), end="", flush=True)
            elif etype == "tool_call_start":
                name = event.get("name", "")
                args = json.dumps(event.get("arguments", {}),
                                  ensure_ascii=False)
                print(f"\n  ┌─ 🔧 调用 {name}: {args}")
            elif etype == "tool_result":
                result_str = event.get("result", "")
                if len(result_str) > 200:
                    result_str = result_str[:200] + "..."
                print(f"  └─ 结果: {result_str}\n")
            elif etype == "status":
                step = event.get("step", "")
                content = event.get("content", "")
                print(f"\n  ⏳ [{step}] {content}", flush=True)
            elif etype == "suggestions":
                items = event.get("items", [])
                print(f"\n\n💡 建议: {', '.join(items)}")
            elif etype == "error":
                print(f"\n  ❌ {event.get('content', '')}")
            elif etype == "done":
                print("\n" + "─" * 60)
                print("✅ 完成")
                break


def main():
    parser = argparse.ArgumentParser(description="Agent Completions API 测试")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="后端地址")
    parser.add_argument("--api-key", default=DEFAULT_API_KEY, help="API Key")
    parser.add_argument("--cluster", default=None, help="目标集群名")
    parser.add_argument("--nodes", nargs="*", default=None, help="目标节点")
    parser.add_argument("--timeout", type=int,
                        default=DEFAULT_TIMEOUT, help="超时秒数")
    parser.add_argument("--question", "-q", default=None, help="直接指定问题")
    parser.add_argument("--conversation-id", default=None, help="会话 ID（多轮追问）")
    parser.add_argument("--stream", action="store_true", help="使用流式模式（实时输出）")
    args = parser.parse_args()

    # 交互式输入或命令行指定
    question = args.question
    if not question:
        question = input("请输入问题（直接回车使用默认）: ").strip()
        if not question:
            question = "你好，请介绍一下你能做什么"

    try:
        if args.stream:
            test_stream(
                base_url=args.base_url,
                api_key=args.api_key,
                question=question,
                cluster_name=args.cluster,
                target_nodes=args.nodes,
                conversation_id=args.conversation_id,
                timeout=args.timeout,
            )
        else:
            result = test_completions(
                base_url=args.base_url,
                api_key=args.api_key,
                question=question,
                cluster_name=args.cluster,
                target_nodes=args.nodes,
                conversation_id=args.conversation_id,
                timeout=args.timeout,
            )
            print_result(result)
    except httpx.ConnectError:
        print(f"❌ 连接失败: 无法连接到 {args.base_url}")
        print("   请确认后端服务已启动: podman-compose up -d")
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP 错误: {e.response.status_code}")
        try:
            print(f"   详情: {e.response.json()}")
        except Exception:
            print(f"   响应: {e.response.text[:500]}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
