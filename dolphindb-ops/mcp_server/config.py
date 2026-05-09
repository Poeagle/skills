"""mcp-config.yaml 加载器（无平台依赖）"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# 优先级：环境变量 > 当前目录 > 包根目录
_ENV_CONFIG_PATH = "DOLPHINDB_OPS_MCP_CONFIG"
_DEFAULT_FILENAME = "mcp-config.yaml"

# server 启动时把 discovery 解析后的 config 注入此处；之后所有 load_config()
# 调用（包括 cluster_resolver / tools 间接调的）都拿到含 nodes 的运行时 config。
_runtime_config: dict[str, Any] | None = None


_ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


# ── 服务模式 / 多租户配置（仅 HTTP 远程模式使用）──────────────


@dataclass(frozen=True)
class ServiceConfig:
    """`service:` 段。enabled=False 时表示走传统 stdio，无需鉴权。"""

    enabled: bool = False
    transport: str = "stdio"  # "stdio" | "http"
    host: str = "0.0.0.0"
    port: int = 7902
    audit_log: str | None = None  # 不写则不审计
    session_idle_timeout: int = 1800  # http 模式空闲连接回收（秒）


@dataclass(frozen=True)
class TokenConfig:
    """`tokens:` 段单条记录。`clusters=("*",)` 表示对所有集群可见。"""

    token: str
    name: str
    clusters: tuple[str, ...]
    can_operate: bool
    can_call_api: bool

    def can_see_cluster(self, cluster_name: str) -> bool:
        if "*" in self.clusters:
            return True
        return cluster_name in self.clusters


@dataclass(frozen=True)
class CallApiConfig:
    """`call_api:` 段。HTTP 远程模式下，启用 callApi 的 token 用此 JWT。"""

    service_account_jwt: str | None = None


# 缓存：避免每次工具调用都重解析 yaml
_service_config_cache: ServiceConfig | None = None
_tokens_cache: dict[str, TokenConfig] | None = None
_call_api_config_cache: CallApiConfig | None = None


def _parse_service_config(cfg: dict[str, Any]) -> ServiceConfig:
    raw = cfg.get("service") or {}
    if not isinstance(raw, dict):
        return ServiceConfig()
    transport = str(raw.get("transport") or "stdio").lower()
    if transport not in ("stdio", "http"):
        logger.warning(
            "Unknown service.transport=%r, falling back to stdio", transport)
        transport = "stdio"
    return ServiceConfig(
        enabled=bool(raw.get("enabled", False)),
        transport=transport,
        host=str(raw.get("host") or "0.0.0.0"),
        port=int(raw.get("port") or 7902),
        audit_log=(str(raw["audit_log"])
                   if raw.get("audit_log") else None),
        session_idle_timeout=int(raw.get("session_idle_timeout") or 1800),
    )


def _parse_tokens(cfg: dict[str, Any]) -> dict[str, TokenConfig]:
    raw = cfg.get("tokens") or []
    out: dict[str, TokenConfig] = {}
    if not isinstance(raw, list):
        logger.warning(
            "tokens: expected list, got %s — ignoring", type(raw).__name__)
        return out
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            logger.warning("tokens[%d]: not a mapping — skipped", idx)
            continue
        tok = str(item.get("token") or "").strip()
        if not tok:
            logger.warning("tokens[%d]: missing 'token' — skipped", idx)
            continue
        if tok in out:
            logger.warning("tokens[%d]: duplicate token, last entry wins", idx)
        clusters_raw = item.get("clusters") or []
        if isinstance(clusters_raw, str):
            clusters_raw = [clusters_raw]
        if not isinstance(clusters_raw, list):
            logger.warning(
                "tokens[%d].clusters: expected list, got %s — defaulting to []",
                idx, type(clusters_raw).__name__)
            clusters_raw = []
        out[tok] = TokenConfig(
            token=tok,
            name=str(item.get("name") or f"token-{idx}"),
            clusters=tuple(str(c) for c in clusters_raw),
            can_operate=bool(item.get("can_operate", False)),
            can_call_api=bool(item.get("can_call_api", False)),
        )
    return out


def _parse_call_api_config(cfg: dict[str, Any]) -> CallApiConfig:
    raw = cfg.get("call_api") or {}
    if not isinstance(raw, dict):
        return CallApiConfig()
    jwt = raw.get("service_account_jwt")
    return CallApiConfig(
        service_account_jwt=(str(jwt) if jwt else None),
    )


def init_service_config(cfg: dict[str, Any]) -> None:
    """server 启动时调用一次，解析并缓存 service / tokens / call_api。"""
    global _service_config_cache, _tokens_cache, _call_api_config_cache
    _service_config_cache = _parse_service_config(cfg)
    _tokens_cache = _parse_tokens(cfg)
    _call_api_config_cache = _parse_call_api_config(cfg)
    if _service_config_cache.enabled:
        logger.info(
            "Service mode enabled: transport=%s, %d token(s) loaded",
            _service_config_cache.transport, len(_tokens_cache))


def get_service_config() -> ServiceConfig:
    return _service_config_cache or ServiceConfig()


def get_token_info(token: str) -> TokenConfig | None:
    if not _tokens_cache:
        return None
    return _tokens_cache.get(token)


def get_call_api_config() -> CallApiConfig:
    return _call_api_config_cache or CallApiConfig()


def set_runtime_config(cfg: dict[str, Any]) -> None:
    """server 启动后注入已 discovery 的 config，作为后续 load_config() 的来源。"""
    global _runtime_config
    _runtime_config = cfg
    init_service_config(cfg)


def _expand_env_vars(value: Any) -> Any:
    """将 ${VAR_NAME} 占位符替换为环境变量值；递归处理 dict/list。"""
    if isinstance(value, str):
        return _ENV_VAR_PATTERN.sub(
            lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env_vars(v) for v in value]
    return value


def _candidate_paths() -> list[Path]:
    candidates: list[Path] = []
    env_path = os.environ.get(_ENV_CONFIG_PATH)
    if env_path:
        candidates.append(Path(env_path).expanduser())
    candidates.append(Path.cwd() / _DEFAULT_FILENAME)
    candidates.append(Path(__file__).resolve().parents[1] / _DEFAULT_FILENAME)
    return candidates


def find_config_path() -> Path | None:
    """返回第一个存在的 mcp-config.yaml 路径，找不到返回 None。"""
    for path in _candidate_paths():
        if path.is_file():
            return path
    return None


def load_config() -> dict[str, Any]:
    """加载 mcp-config.yaml，自动展开 ${ENV_VAR}。

    若 server 已经通过 set_runtime_config 注入了运行时 config（含 discovery 结果），
    直接返回它，避免每次都从磁盘重读、丢失 discovery 算出的 nodes 等字段。
    """
    if _runtime_config is not None:
        return _runtime_config
    path = find_config_path()
    if path is None:
        logger.warning(
            "mcp-config.yaml not found in any of: %s",
            [str(p) for p in _candidate_paths()],
        )
        return {}

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        logger.error("Failed to read %s: %s", path, e)
        return {}

    if not isinstance(raw, dict):
        logger.error("mcp-config.yaml top-level must be a mapping, got %s",
                     type(raw).__name__)
        return {}

    expanded = _expand_env_vars(raw)
    logger.info("Loaded MCP config from %s", path)
    return expanded


def resolve_skill_dir(config: dict[str, Any]) -> Path:
    """根据 config['skill_dir'] 解析 SKILL 文件根目录。

    - 相对路径：相对 mcp-config.yaml 所在目录
    - 缺省：mcp-config.yaml 所在目录
    """
    raw = config.get("skill_dir") or "./"
    cfg_path = find_config_path()
    base = cfg_path.parent if cfg_path else Path.cwd()
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = (base / p).resolve()
    return p
