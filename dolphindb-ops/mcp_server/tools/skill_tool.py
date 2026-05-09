"""loadRef MCP 工具实现

负责加载 dolphindb-ops 的 SKILL.md 与 references/ 片段，并按 session_id
维护已加载状态（loaded_skills / loaded_refs）。

references/ 已扁平化（无子目录）。每个 ref 顶部有 frontmatter `kind:
category | operation` 标识其类型：
  - kind=category 的 ref 加载时按脚本 @collect 标签触发自动采集
  - kind=operation 的 ref 仅展示文档，不触发采集

注：introduced_actions 字段在 session_state 中保留接收（兼容 platform 的
__restore_session_state__），但本工具不再使用；完整 action 目录在
execDdb / execShell 的 description 中常驻提供。
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from ..cluster_resolver import get_cluster
from ..script_registry import get_script_registry
from ..skill_loader import MAIN_SKILL_ID, get_skill_loader

logger = logging.getLogger(__name__)


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_KIND_RE = re.compile(r"^\s*kind\s*:\s*(\w+)\s*$", re.MULTILINE)


def _extract_ref_kind(content: str) -> str:
    """从 ref 文件内容的 frontmatter 解析 kind。

    支持的 kind：
      - category：故障诊断类，加载时触发 @collect 自动采集
      - operation：操作指引类，仅展示文档
    无 frontmatter 或 kind 缺失时返回 'reference'（中性分类）。
    """
    if not content:
        return "reference"
    m = _FRONTMATTER_RE.match(content)
    if not m:
        return "reference"
    fm = m.group(1)
    km = _KIND_RE.search(fm)
    if not km:
        return "reference"
    kind = km.group(1).strip().lower()
    if kind in ("category", "operation"):
        return kind
    return "reference"


SKILL_LOADER_DESCRIPTION = """加载主 Skill 包 `dolphindb-ops` 的内容。
- 指定 name='dolphindb-ops' 时：加载主 SKILL.md
- 指定 name='dolphindb-ops' 且给定 ref 时：加载 references/ 下的某个片段（扁平命名，如 'oom'、'platform-api'）
- 不指定 name 但指定 query 时：在主 Skill 包及其 refs 中搜索"""


SKILL_LOADER_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": "固定使用主 Skill 名称 'dolphindb-ops'。不指定则进入搜索模式",
        },
        "ref": {
            "type": "string",
            "description": "可选，加载 references/ 下的知识片段（扁平命名，如 'oom' / 'crash' / 'platform-api'）。仅在指定 name 时生效",
        },
        "query": {
            "type": "string",
            "description": "搜索关键词（仅在未指定 name 时使用）",
        },
        "cluster": {
            "type": "string",
            "description": "目标集群名（加载 kind=category 的 ref 触发自动采集时需要）",
        },
        "target_node": {
            "type": "string",
            "description": "目标节点名（加载 kind=category 的 ref 触发自动采集时需要）",
        },
    },
    "required": [],
}


async def _execute_collect(
    category_id: str,
    cluster_name: str,
    target_node_name: str,
    session_state: dict[str, set[str]],
) -> dict:
    """执行 category 的 @collect 自动采集（in-process 调用 sibling 工具）。"""
    # 延迟 import：避免 skill_tool 与 ddb_tool / shell_tool 之间的循环依赖
    from .ddb_tool import call_ddb_exec
    from .shell_tool import call_shell_exec

    cluster = get_cluster(cluster_name)
    if cluster is None:
        return {
            "results": [],
            "errors": [{
                "label": "cluster_missing",
                "error": f"集群 '{cluster_name}' 未在 mcp-config.yaml 中定义",
            }],
        }

    target_node = cluster.find_node(target_node_name)
    if target_node is None:
        return {
            "results": [],
            "errors": [{
                "label": "node_missing",
                "error": f"节点 '{target_node_name}' 不存在于集群 '{cluster_name}'",
            }],
        }

    actions = get_script_registry().get_collect_actions(category_id)
    if not actions:
        return {"results": [], "errors": []}

    async def _run_step(action_def):
        tool_name = "execDdb" if action_def.source == "ddb" else "execShell"
        args: dict[str, Any] = {
            "action": action_def.name,
            "cluster": cluster_name,
            "node": target_node_name,
        }
        cat_args = action_def.collect_args.get(category_id) or {}
        if cat_args:
            args["params"] = dict(cat_args)
        try:
            if action_def.source == "ddb":
                result = await call_ddb_exec(args, session_state)
            else:
                result = await call_shell_exec(args, session_state)
        except Exception as e:
            return {
                "label": action_def.description or action_def.name,
                "tool": tool_name,
                "error": str(e),
            }

        if isinstance(result, dict) and result.get("error"):
            return {
                "label": action_def.description or action_def.name,
                "tool": tool_name,
                "error": result["error"],
            }
        return {
            "label": action_def.description or action_def.name,
            "tool": tool_name,
            "result": result,
        }

    step_results = await asyncio.gather(
        *[_run_step(a) for a in actions], return_exceptions=False)

    results: list[dict] = []
    errors: list[dict] = []
    for sr in step_results:
        if "error" in sr:
            errors.append(sr)
        else:
            results.append(sr)
    return {"results": results, "errors": errors}


async def call_skill_loader(
    arguments: dict[str, Any],
    session_state: dict[str, set[str]],
) -> dict:
    """loadRef 的 MCP 实现。

    session_state 由 server.py 按 session_id 维护，含
    `loaded_skills` / `loaded_refs` / `introduced_actions` 三个集合。
    其中 `introduced_actions` 已不再被本工具读写（保留兼容平台兜底）。
    """
    name = arguments.get("name")
    ref = arguments.get("ref")
    query = arguments.get("query")
    cluster_name = arguments.get("cluster") or ""
    target_node_name = arguments.get("target_node") or ""

    try:
        loader = get_skill_loader()

        # 搜索模式：未指定 name
        if not name:
            if not query:
                return {
                    "error": "请指定 name='dolphindb-ops'（加载主 Skill）或 query（搜索主 Skill 包）",
                }
            results = loader.search(query, top_k=5)
            return {
                "matched_skills": results,
                "total": len(results),
                "hint": "请使用 loadRef(name='dolphindb-ops', ref='...') 按需加载 diagnosis/category/manual/operation 片段",
            }

        skill_id = str(name).strip()
        if skill_id != MAIN_SKILL_ID:
            return {
                "error": f"当前系统只支持主 Skill 包 '{MAIN_SKILL_ID}'，不支持 '{skill_id}'",
                "hint": f"请使用 loadRef(name='{MAIN_SKILL_ID}') 或 loadRef(name='{MAIN_SKILL_ID}', ref='...')",
            }

        # ref 模式：读取 references/<ref>.md
        if ref:
            content = loader.read_reference(skill_id, ref)
            if content is None:
                available = loader.list_references(skill_id)
                return {
                    "error": f"主 Skill '{skill_id}' 中未找到 reference '{ref}'",
                    "available_refs": available[:20] if available else [],
                    "hint": "请检查 ref 路径是否正确",
                }

            session_state["loaded_skills"].add(skill_id)
            session_state["loaded_refs"].add(f"{skill_id}:{ref}")

            ref_kind = _extract_ref_kind(content)
            result: dict = {
                "skill_id": skill_id,
                "skill_name": skill_id,
                "ref": ref,
                "ref_kind": ref_kind,
                "content": content,
            }

            # kind=category 的 ref：用 ref 名（去 .md）作为 category_id 匹配脚本
            # @collect 标签，触发自动并行采集
            if ref_kind == "category":
                category_id = ref.rsplit("/", 1)[-1]
                if category_id.endswith(".md"):
                    category_id = category_id[:-3]
                actions = get_script_registry().get_collect_actions(category_id)

                if actions:
                    if cluster_name and target_node_name:
                        collected = await _execute_collect(
                            category_id,
                            cluster_name,
                            target_node_name,
                            session_state,
                        )
                        result["collected"] = collected
                        result["phase"] = "phase1_complete"
                    else:
                        result["collect_available"] = True
                        result["collect_hint"] = (
                            "此方法论支持自动采集，但缺少 cluster 或 target_node 参数。"
                            "请确保已选择集群和目标节点；或直接传入这两个参数后重试。"
                        )
                # 不再附 action_catalog：完整 action 目录已在 execDdb / execShell
                # 的工具描述里常驻一次，无需在每次 category 加载时重复介绍。

            return result

        # 加载模式：读取主 SKILL.md
        content = loader.read(skill_id)
        if content is None:
            return {"error": f"主 Skill '{skill_id}' 不存在或无法读取"}

        session_state["loaded_skills"].add(skill_id)
        return {
            "skill_id": skill_id,
            "skill_name": skill_id,
            "content": content,
            "execution_rule": (
                "⚠️ 严格执行模式：必须按步骤编号顺序逐步执行，"
                "禁止跳步、合并步骤或修改脚本。"
                "每步执行完展示结果后再进入下一步。"
            ),
        }

    except Exception as e:
        logger.error("loadRef failed: %s", e, exc_info=True)
        return {"error": f"SKILL 加载失败: {str(e)}"}
