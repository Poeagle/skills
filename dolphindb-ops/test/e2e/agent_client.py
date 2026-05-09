"""Agent Completions API 客户端，用于自动化闭环测试。"""

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field

import httpx

API_BASE_URL = os.environ.get("TEST_API_URL", "http://192.168.100.43:7901")
API_KEY = os.environ.get("TEST_API_KEY", "sk-ops-test-key-001")
CONNECT_RETRY_ATTEMPTS = int(os.environ.get("TEST_AGENT_CONNECT_RETRIES", "3"))


def _is_local_agent_mode_enabled() -> bool:
    return os.environ.get("TEST_AGENT_LOCAL_MODE", "").strip().lower() in {
        "1", "true", "yes", "on"
    }


def _should_use_ansi_colors() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM", "").strip().lower() == "dumb":
        return False

    force_color = os.environ.get("FORCE_COLOR", "").strip().lower()
    if force_color in {"1", "true", "yes", "on"}:
        return True

    return bool(getattr(sys.stdout, "isatty", lambda: False)())


# 非交互式输出（如 detached runner 落盘日志）不写 ANSI 控制符，避免前端展示乱码。
if _should_use_ansi_colors():
    _GRAY = "\033[90m"
    _CYAN = "\033[36m"
    _GREEN = "\033[32m"
    _YELLOW = "\033[33m"
    _RED = "\033[31m"
    _RESET = "\033[0m"
    _BOLD = "\033[1m"
else:
    _GRAY = ""
    _CYAN = ""
    _GREEN = ""
    _YELLOW = ""
    _RED = ""
    _RESET = ""
    _BOLD = ""


@dataclass
class AgentResponse:
    success: bool = False
    content: str = ""
    events: list = field(default_factory=list)
    tool_calls: list = field(default_factory=list)
    has_error: bool = False
    duration_ms: int = 0
    raw: dict = field(default_factory=dict)
    error_message: str = ""


class AgentClient:
    def __init__(self, base_url: str = API_BASE_URL, api_key: str = API_KEY):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def ask(
        self,
        prompt: str,
        cluster_name: str = "",
        target_nodes: list[str] | None = None,
        timeout: int = 300,
        verbose: bool = True,
    ) -> AgentResponse:
        if _is_local_agent_mode_enabled():
            return self._ask_local(
                prompt=prompt,
                cluster_name=cluster_name,
                target_nodes=target_nodes,
                timeout=timeout,
                verbose=verbose,
            )
        return self._ask_via_http(
            prompt=prompt,
            cluster_name=cluster_name,
            target_nodes=target_nodes,
            timeout=timeout,
            verbose=verbose,
        )

    def _ask_via_http(
        self,
        prompt: str,
        cluster_name: str = "",
        target_nodes: list[str] | None = None,
        timeout: int = 300,
        verbose: bool = True,
    ) -> AgentResponse:
        url = f"{self.base_url}/api/v1/agent/completions"
        headers = {"Authorization": f"Bearer {self.api_key}",
                   "Content-Type": "application/json"}
        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "timeout": timeout,
        }
        if cluster_name:
            payload["env"] = {"cluster_name": cluster_name,
                              "target_nodes": target_nodes or []}

        events = []
        content_parts = []
        tool_calls = []
        pending_tool_args = {}  # id → arguments（从 tool_call_start 暂存）
        has_error = False
        start_ms = time.time()
        client = None
        resp = None

        # connect=10, read=总超时+30s (防 SSE 长间隔事件被默认读超时打断)
        timeout_obj = httpx.Timeout(
            connect=10.0, read=float(timeout + 30), write=10.0, pool=10.0)

        for attempt in range(1, CONNECT_RETRY_ATTEMPTS + 1):
            try:
                client = httpx.Client(timeout=timeout_obj)
                request = client.build_request(
                    "POST", url, json=payload, headers=headers)
                resp = client.send(request, stream=True)
                resp.raise_for_status()
                break
            except httpx.TimeoutException:
                if resp is not None:
                    resp.close()
                    resp = None
                if client is not None:
                    client.close()
                    client = None
                if attempt >= CONNECT_RETRY_ATTEMPTS:
                    return AgentResponse(error_message=f"HTTP 请求超时 ({timeout+30}s)")
                if verbose:
                    print(
                        f"\n       {_YELLOW}⚠ 建立 Agent 连接超时，准备重试 ({attempt}/{CONNECT_RETRY_ATTEMPTS}){_RESET}",
                        flush=True,
                    )
            except httpx.ConnectError as e:
                if resp is not None:
                    resp.close()
                    resp = None
                if client is not None:
                    client.close()
                    client = None
                if attempt >= CONNECT_RETRY_ATTEMPTS:
                    return AgentResponse(error_message=f"连接失败: {e}")
                if verbose:
                    print(
                        f"\n       {_YELLOW}⚠ Agent 连接被重置，准备重试 ({attempt}/{CONNECT_RETRY_ATTEMPTS}): {e}{_RESET}",
                        flush=True,
                    )
            except httpx.HTTPStatusError:
                status = resp.status_code if resp is not None else "?"
                # 流式响应未读取，先 close
                if resp is not None:
                    resp.close()
                if client is not None:
                    client.close()
                return AgentResponse(error_message=f"HTTP {status}")
            except Exception as e:
                if resp is not None:
                    resp.close()
                if client is not None:
                    client.close()
                return AgentResponse(error_message=f"未知错误: {e}")

            time.sleep(min(attempt, 3))

        if resp is None or client is None:
            return AgentResponse(error_message="Agent 连接未建立")

        # 解析 SSE 流
        try:
            for line in resp.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                raw = line[6:]
                if raw.strip() == "[DONE]":
                    break
                try:
                    ev = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                has_error = self._consume_event(
                    ev=ev,
                    verbose=verbose,
                    events=events,
                    content_parts=content_parts,
                    tool_calls=tool_calls,
                    pending_tool_args=pending_tool_args,
                ) or has_error
                if ev.get("type") == "done":
                    break
        except Exception as e:
            return AgentResponse(
                content="".join(content_parts),
                events=events,
                tool_calls=tool_calls,
                has_error=True,
                error_message=f"流式解析错误: {e}",
                duration_ms=int((time.time() - start_ms) * 1000),
            )
        finally:
            resp.close()
            client.close()

        if verbose:
            print()  # 换行
        elapsed_ms = int((time.time() - start_ms) * 1000)

        return AgentResponse(
            success=not has_error,
            content="".join(content_parts),
            events=events,
            tool_calls=tool_calls,
            has_error=has_error,
            duration_ms=elapsed_ms,
        )

    def _ask_local(
        self,
        prompt: str,
        cluster_name: str = "",
        target_nodes: list[str] | None = None,
        timeout: int = 300,
        verbose: bool = True,
    ) -> AgentResponse:
        try:
            return asyncio.run(self._ask_local_async(
                prompt=prompt,
                cluster_name=cluster_name,
                target_nodes=target_nodes,
                timeout=timeout,
                verbose=verbose,
            ))
        except Exception as e:
            return AgentResponse(error_message=f"本地 Agent 执行失败: {e}")

    async def _ask_local_async(
        self,
        prompt: str,
        cluster_name: str = "",
        target_nodes: list[str] | None = None,
        timeout: int = 300,
        verbose: bool = True,
    ) -> AgentResponse:
        try:
            from app.core.dependencies import UserInfo, get_dependency_container
            from app.services.agent.agent_service import run_agent
            from app.services.agent.env_context import build_env_context
            from app.services.agent.llm_client import create_llm_client
            from app.services.agent.message_context import prepare_user_messages
            from app.services.agent.model_manager import get_model_manager
            from app.services.agent.tools import build_tool_registry
        except Exception as e:
            return AgentResponse(error_message=f"本地 Agent 初始化失败: {e}")

        user_info = self._resolve_local_api_key_user()
        if user_info is None:
            return AgentResponse(error_message="本地 Agent 模式下 API Key 无效")

        agent_config = get_model_manager().get_active_config()
        if not agent_config.get("enabled", False):
            return AgentResponse(error_message="Agent 未启用")

        llm_client = create_llm_client(agent_config)
        content_parts = []
        events = []
        tool_calls = []
        pending_tool_args = {}
        has_error = False
        start_ms = time.time()

        try:
            container = get_dependency_container()
            config_manager = container.get_config_manager()
            service_factory = container.get_service_factory()
            connection_pool = container.get_connection_pool()

            env_context = None
            if cluster_name:
                try:
                    env_context = await build_env_context(
                        config_manager=config_manager,
                        connection_pool=connection_pool,
                        cluster_name=cluster_name,
                        target_nodes=target_nodes,
                        user_id=user_info.user_id,
                        is_admin=user_info.is_admin,
                    )
                except Exception as e:
                    if verbose:
                        print(
                            f"\n       {_YELLOW}⚠ 构建环境上下文失败: {e}{_RESET}", flush=True)

            tool_registry = build_tool_registry(
                config_manager=config_manager,
                service_factory=service_factory,
                connection_pool=connection_pool,
                user_id=user_info.user_id,
                is_admin=user_info.is_admin,
                auth_token=self.api_key,
                backend_base_url=self.base_url,
                tool_timeout=float(agent_config.get("tool_timeout_secs", 30)),
                agent_config=agent_config,
                env=env_context,
            )

            user_messages = prepare_user_messages(
                [{"role": "user", "content": prompt}],
                cluster_name=cluster_name,
                target_nodes=target_nodes,
                env_context=env_context,
            )

            async with asyncio.timeout(timeout):
                async for ev in run_agent(
                    llm_client=llm_client,
                    tool_registry=tool_registry,
                    user_messages=user_messages,
                    conversation_id=None,
                    max_iterations=self._parse_max_tool_iterations(
                        agent_config.get("max_tool_iterations")
                    ),
                    max_context_chars=agent_config.get(
                        "max_context_chars", 80_000),
                ):
                    has_error = self._consume_event(
                        ev=ev,
                        verbose=verbose,
                        events=events,
                        content_parts=content_parts,
                        tool_calls=tool_calls,
                        pending_tool_args=pending_tool_args,
                    ) or has_error
                    if ev.get("type") == "done":
                        break
        except (TimeoutError, asyncio.TimeoutError):
            has_error = True
            events.append({"type": "error", "content": f"请求超时 ({timeout}s)"})
            if verbose:
                print(
                    f"\n       {_RED}✗ 错误: 请求超时 ({timeout}s){_RESET}", flush=True)
        except Exception as e:
            has_error = True
            events.append({"type": "error", "content": f"本地 Agent 内部错误: {e}"})
            if verbose:
                print(f"\n       {_RED}✗ 错误: {e}{_RESET}", flush=True)
        finally:
            try:
                await llm_client.close()
            except Exception:
                pass

        if verbose:
            print()
        elapsed_ms = int((time.time() - start_ms) * 1000)
        error_message = ""
        if has_error:
            error_events = [ev for ev in events if ev.get("type") == "error"]
            if error_events:
                error_message = str(error_events[-1].get("content", ""))
        return AgentResponse(
            success=not has_error,
            content="".join(content_parts),
            events=events,
            tool_calls=tool_calls,
            has_error=has_error,
            duration_ms=elapsed_ms,
            error_message=error_message,
        )

    def _consume_event(
        self,
        ev: dict,
        verbose: bool,
        events: list,
        content_parts: list,
        tool_calls: list,
        pending_tool_args: dict,
    ) -> bool:
        events.append(ev)
        ev_type = ev.get("type", "")

        if ev_type == "system_prompt":
            sp = ev.get("content", "")
            if verbose:
                print(
                    f"\n       {_CYAN}📋 系统提示词 ({len(sp)} chars){_RESET}", flush=True)

        elif ev_type == "env_context":
            env_data = ev.get("content", {})
            nodes_count = len(env_data.get("nodes", []))
            if verbose:
                print(f"\n       {_CYAN}🌐 环境上下文: cluster={env_data.get('cluster_name','?')}, "
                      f"nodes={nodes_count}{_RESET}", flush=True)

        elif ev_type == "text":
            text = ev.get("content", "")
            content_parts.append(text)
            if verbose:
                sys.stdout.write(f"{_GRAY}{text}{_RESET}")
                sys.stdout.flush()

        elif ev_type == "status":
            status = ev.get("content", "")
            if verbose:
                print(f"\n       {_CYAN}⟳ {status}{_RESET}", flush=True)

        elif ev_type == "tool_call_start":
            tc_id = ev.get("id", "")
            tc_name = ev.get("name", "")
            tc_args = ev.get("arguments", {})
            pending_tool_args[tc_id] = tc_args
            action = tc_args.get("action", "")
            if verbose:
                print(
                    f"\n       {_YELLOW}🔧 {tc_name}({action}){_RESET}", end="", flush=True)

        elif ev_type == "tool_result":
            tc_id = ev.get("id", "")
            tc_name = ev.get("name", "")
            result_str = ev.get("result", "")
            success = ev.get("success", True)
            duration = ev.get("duration_ms", 0)
            tc_args = pending_tool_args.pop(tc_id, {})
            tc = {
                "type": "tool_call",
                "name": tc_name,
                "result": result_str,
                "success": success,
                "duration_ms": duration,
                "arguments": tc_args,
            }
            tool_calls.append(tc)
            if verbose:
                icon = f"{_GREEN}✓{_RESET}" if success else f"{_RED}✗{_RESET}"
                preview = result_str[:80].replace(
                    "\n", " ") if result_str else ""
                print(f" {icon} {duration}ms {_GRAY}{preview}{_RESET}", flush=True)

        elif ev_type == "error":
            err_msg = ev.get("content", "")
            if verbose:
                print(f"\n       {_RED}✗ 错误: {err_msg}{_RESET}", flush=True)
            return True

        elif ev_type == "suggestions":
            items = ev.get("items", [])
            if verbose and items:
                print(
                    f"\n       {_CYAN}建议: {', '.join(items)}{_RESET}", flush=True)

        return False

    def _resolve_local_api_key_user(self):
        import hmac

        from app.core.dependencies import UserInfo
        from app.services.agent.model_manager import get_model_manager

        for api_key in get_model_manager().get_api_keys():
            stored_key = api_key.get("key", "")
            if stored_key and hmac.compare_digest(self.api_key, stored_key):
                return UserInfo(
                    user_id=api_key.get("user_id", 0),
                    username=api_key.get("name", "api_key_user"),
                    is_admin=api_key.get("is_admin", False),
                )
        return None

    def _parse_max_tool_iterations(self, raw):
        if raw is None:
            return None
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None
