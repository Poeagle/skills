"""HTTP 远程模式 e2e 鉴权 / 多租户隔离测试。

启动一个临时 MCP server (transport=http)，覆盖：
  - 缺 token / 错 token → 401
  - cluster 白名单（不可见集群报错）
  - callApi 权限开关
  - 写操作降级（can_operate=false 时强制返 operation_suggestion）
  - 审计日志写入

运行：
    cd skills/dolphindb-ops
    python -m pytest test/test_http_auth.py -v
或直接：
    python test/test_http_auth.py
"""
from __future__ import annotations

import asyncio
import json
import os
import socket
import sys
import tempfile
from pathlib import Path

import httpx

# 让脚本既能 pytest 也能直接运行
_THIS_DIR = Path(__file__).resolve().parent
_SKILL_DIR = _THIS_DIR.parent
if str(_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILL_DIR))

PORT = 17912  # 测试专用，避开生产端口
BASE = f"http://127.0.0.1:{PORT}"


def _write_test_config(tmpdir: Path, audit_log: Path) -> Path:
    cfg = tmpdir / "mcp-config.yaml"
    cfg.write_text(f"""
skill_dir: {_SKILL_DIR}/

clusters: {{}}
servers: {{}}
ssh:
  user: ymchen
  port: 22
backend:
  base_url: http://localhost:7900
limits:
  ddb_result_max_rows: 200
  shell_output_max_chars: 5000
  shell_output_max_lines: 100
agent_can_operate: false

service:
  enabled: true
  transport: http
  host: 127.0.0.1
  port: {PORT}
  audit_log: {audit_log}

tokens:
  - token: "ro-aaa"
    name: "readonly-team"
    clusters: ["fake-cluster-a"]
    can_operate: false
    can_call_api: false
  - token: "rw-bbb"
    name: "ops-team"
    clusters: ["*"]
    can_operate: true
    can_call_api: true

call_api:
  service_account_jwt: ""
""")
    return cfg


async def _wait_port(host: str, port: int, timeout: float = 6.0) -> bool:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.2)
        s = socket.socket()
        s.settimeout(0.3)
        try:
            s.connect((host, port))
            s.close()
            return True
        except Exception:
            try:
                s.close()
            except Exception:
                pass
    return False


async def _run_e2e() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="mcp_http_test_"))
    audit_path = tmpdir / "audit.jsonl"
    cfg_path = _write_test_config(tmpdir, audit_path)

    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "mcp_server.server",
        "serve", "--transport", "http",
        cwd=str(_SKILL_DIR),
        env={
            **os.environ,
            "PYTHONPATH": str(_SKILL_DIR),
            "DOLPHINDB_OPS_MCP_CONFIG": str(cfg_path),
        },
        stdout=asyncio.subprocess.DEVNULL,
        stderr=open(tmpdir / "stderr.log", "wb"),
    )

    try:
        ok = await _wait_port("127.0.0.1", PORT, timeout=8.0)
        assert ok, f"server didn't open port {PORT}"

        # 基础 HTTP 拒绝
        async with httpx.AsyncClient(timeout=5.0, trust_env=False) as c:
            r = await c.post(BASE + "/mcp",
                             json={"jsonrpc": "2.0", "id": 1,
                                   "method": "tools/list"})
            assert r.status_code == 401, f"no-auth should be 401, got {r.status_code}"

            r = await c.post(BASE + "/mcp",
                             headers={"Authorization": "Bearer wrong"},
                             json={"jsonrpc": "2.0", "id": 2,
                                   "method": "tools/list"})
            assert r.status_code == 401, f"bad token should be 401, got {r.status_code}"

        # 走 mcp 协议：cluster 白名单 / callApi 权限 / 写降级
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        async with streamablehttp_client(
            BASE + "/mcp",
            headers={"Authorization": "Bearer ro-aaa"},
        ) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools = await session.list_tools()
                names = {t.name for t in tools.tools}
                assert "execDdb" in names
                assert "loadRef" in names
                assert "describeAction" in names, (
                    "describeAction must be exposed to LLM clients")

                # describeAction：返回完整 body + 元信息
                r = await session.call_tool("describeAction", {
                    "name": "forceCorrectVersion",
                })
                txt = r.content[0].text
                assert '"body":' in txt, f"missing body: {txt[:200]}"
                assert '"permission": "irreversible"' in txt, txt[:300]
                assert "forceCorrectVersion" in txt, txt[:200]

                # 不存在的 action 应返友好错误
                r = await session.call_tool("describeAction", {
                    "name": "no-such-action",
                })
                txt = r.content[0].text
                assert "未注册" in txt, txt[:200]

                # cluster 白名单
                r = await session.call_tool("execDdb", {
                    "action": "cancelJobs",
                    "cluster": "other-cluster",
                    "node": "n1",
                    "params": {"all": True},
                })
                txt = r.content[0].text
                assert "不可见" in txt, txt

                # callApi 权限
                r = await session.call_tool("callApi", {
                    "method": "GET",
                    "path": "/api/v1/anything",
                })
                txt = r.content[0].text
                assert "无 call_api 权限" in txt, txt

                # 写权限降级
                r = await session.call_tool("execDdb", {
                    "action": "cancelJobs",
                    "cluster": "fake-cluster-a",
                    "node": "n1",
                    "params": {"all": True},
                    "__confirm__": True,
                })
                txt = r.content[0].text
                assert "operation_suggestion" in txt, txt

        # X-DolphinDB-Cluster / X-DolphinDB-Node header：args 不传时自动注入默认；
        # 注入后仍受 token ACL 校验（不可见 cluster 应被挡）
        async with streamablehttp_client(
            BASE + "/mcp",
            headers={
                "Authorization": "Bearer ro-aaa",
                "X-DolphinDB-Cluster": "fake-cluster-a",  # ro-aaa 可见
                "X-DolphinDB-Node": "default-node",
            },
        ) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                # 不传 cluster + 不传 node：应自动用 header 注入
                r = await session.call_tool("execDdb", {
                    "action": "cancelJobs",
                    "params": {"all": True},
                    "__confirm__": True,
                })
                txt = r.content[0].text
                assert "operation_suggestion" in txt, (
                    f"expected suggestion (defaults injected), got: {txt[:200]}")
                # operation_suggestion 的 context 应该看到注入的 node
                assert '"node": "default-node"' in txt, (
                    f"expected default-node in context, got: {txt[:300]}")
                # 显式传的 cluster 不会被 header 覆盖
                r = await session.call_tool("execDdb", {
                    "action": "cancelJobs",
                    "cluster": "other-cluster",   # 不在白名单
                    "node": "n1",
                    "params": {"all": True},
                })
                txt = r.content[0].text
                assert "不可见" in txt, (
                    f"explicit cluster should not be overridden by header: {txt[:200]}")

        # 默认 cluster + token 白名单不放行：仍应被 ACL 挡
        async with streamablehttp_client(
            BASE + "/mcp",
            headers={
                "Authorization": "Bearer ro-aaa",
                "X-DolphinDB-Cluster": "forbidden-cluster",
            },
        ) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                r = await session.call_tool("execDdb", {
                    "action": "cancelJobs",
                    "node": "n1",
                    "params": {"all": True},
                })
                txt = r.content[0].text
                assert "不可见" in txt, (
                    f"default cluster should still go through ACL: {txt[:200]}")

        # ops token：service_account_jwt 缺失时 callApi 应该报指引
        async with streamablehttp_client(
            BASE + "/mcp",
            headers={"Authorization": "Bearer rw-bbb"},
        ) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()

                r = await session.call_tool("callApi", {
                    "method": "GET",
                    "path": "/health",
                })
                txt = r.content[0].text
                assert "service_account_jwt" in txt, txt

                # client 自己塞 Authorization 也无效
                r = await session.call_tool("callApi", {
                    "method": "GET",
                    "path": "/health",
                    "headers": {"Authorization": "Bearer fake-injected"},
                })
                txt = r.content[0].text
                assert "service_account_jwt" in txt, txt

        # 审计日志校验
        assert audit_path.is_file(), "audit log not written"
        lines = audit_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) >= 4, f"expected ≥4 audit lines, got {len(lines)}"
        # 至少出现两个 token 的痕迹
        names_in_audit = {json.loads(l)["token_name"] for l in lines}
        assert "readonly-team" in names_in_audit
        assert "ops-team" in names_in_audit
        # 注入的 fake Authorization 应被脱敏
        assert "fake-injected" not in audit_path.read_text(encoding="utf-8")

    finally:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=3)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()


def test_http_auth_e2e() -> None:
    """pytest 入口"""
    # 清掉代理环境（CI 机器可能有 http_proxy）
    for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
        os.environ.pop(k, None)
    asyncio.run(_run_e2e())


if __name__ == "__main__":
    test_http_auth_e2e()
    print("ALL PASS")
