"""脚本注册表 —— 从 .dos / .sh 文件自动发现 action 定义（mcp-server 版本）

scripts_dir 由 mcp-config.yaml 的 skill_dir 决定（默认 `<skill_dir>/scripts/`）。
注解格式与平台版本一致，详见 docs/agent_generic_migration.md。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from .config import load_config, resolve_skill_dir

logger = logging.getLogger(__name__)


@dataclass
class ActionParam:
    name: str
    type: str = "str"
    required: bool = False
    default: str | None = None
    pattern: str | None = None
    allow_chars: str | None = None
    max: int | None = None


# 三级权限：以"操作的可恢复性"为主轴
#   readonly      —— 只读查询，无任何副作用
#   recoverable   —— 修改运行时状态但可恢复（取消作业、清缓存、关会话…）
#   irreversible  —— 不可逆 / 数据风险（删副本、改版本号、备份恢复…）
PERMISSION_LEVELS = ("readonly", "recoverable", "irreversible")


@dataclass
class ActionDef:
    """单个 action 的完整定义。"""
    name: str
    description: str
    source: Literal["ddb", "shell"]
    permission: str = "readonly"
    params: dict[str, ActionParam] = field(default_factory=dict)
    body: str = ""
    file_path: str = ""
    collect_categories: list[str] = field(default_factory=list)
    collect_args: dict[str, dict[str, str]] = field(default_factory=dict)

    @property
    def dangerous(self) -> bool:
        """向后兼容：dangerous == 不可逆。"""
        return self.permission == "irreversible"


# ── 解析器 ────────────────────────────────────────────────

_DDB_DESC_RE = re.compile(r'^//\s*@description\s+(.*)', re.MULTILINE)
_DDB_PARAMS_RE = re.compile(r'^//\s*@params\s+(.*)', re.MULTILINE)
_DDB_PERMISSION_RE = re.compile(
    r'^//\s*@permission\s+(\w+)', re.MULTILINE)
_DDB_COLLECT_RE = re.compile(r'^//\s*@collect\s+(.*)', re.MULTILINE)
_DDB_COLLECT_ARGS_RE = re.compile(
    r'^//\s*@collect_args\s+(\S+)\s+(.*)', re.MULTILINE)
_DDB_FUNC_START_RE = re.compile(r'^def\s+(\w+)\s*\(', re.MULTILINE)

_SH_FUNC_START_RE = re.compile(r'^(\w+)\s*\(\)\s*\{', re.MULTILINE)
_SH_DESC_RE = re.compile(r'#\s*@description\s+(.*)')
_SH_PARAMS_RE = re.compile(r'#\s*@params\s+(.*)')
_SH_PERMISSION_RE = re.compile(r'#\s*@permission\s+(\w+)')
_SH_COLLECT_RE = re.compile(r'#\s*@collect\s+(.*)')
_SH_COLLECT_ARGS_RE = re.compile(r'#\s*@collect_args\s+(\S+)\s+(.*)')


_ENUM_PATTERN_RE = re.compile(r"^\^\(([\w|.\-]+)\)\$$")


def _enum_choices_from_pattern(pattern: str | None) -> str:
    """从 ^(a|b|c)$ 形式的 regex 提取枚举候选，用于 action_catalog 暴露给 LLM。

    匹配的 pattern 返回 ',可选值=a|b|c'；不匹配返回空串（不污染输出）。
    """
    if not pattern:
        return ""
    m = _ENUM_PATTERN_RE.match(pattern.strip())
    if not m:
        return ""
    return f",可选值={m.group(1)}"


def _parse_collect_args(raw: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for m in re.finditer(r'(\w+)=(\S+)', raw):
        result[m.group(1)] = m.group(2)
    return result


def _parse_all_collect_args(
    comment_block: str, regex: re.Pattern[str],
) -> dict[str, dict[str, str]]:
    args_map: dict[str, dict[str, str]] = {}
    for m in regex.finditer(comment_block):
        category = m.group(1).strip()
        kv = _parse_collect_args(m.group(2))
        if kv:
            args_map[category] = kv
    return args_map


def _parse_params(raw: str) -> dict[str, ActionParam]:
    params: dict[str, ActionParam] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue

        pattern = None
        pattern_key = ":pattern="
        pidx = part.find(pattern_key)
        if pidx != -1:
            pattern_raw = part[pidx + len(pattern_key):]
            part = part[:pidx]
            for attr_key in (":allow_chars=", ":max=", ":default=", ":required", ":optional"):
                aidx = pattern_raw.find(attr_key)
                if aidx != -1:
                    part += pattern_raw[aidx:]
                    pattern_raw = pattern_raw[:aidx]
            pattern = pattern_raw

        segments = part.split(":")
        name = segments[0].strip()
        ptype = segments[1].strip() if len(segments) > 1 else "str"
        required = False
        default = None
        allow_chars = None
        pmax = None
        for seg in segments[2:]:
            seg = seg.strip()
            if seg == "required":
                required = True
            elif seg == "optional":
                required = False
            elif seg.startswith("default="):
                default = seg[8:]
            elif seg.startswith("allow_chars="):
                allow_chars = seg[12:]
            elif seg.startswith("max="):
                try:
                    pmax = int(seg[4:])
                except ValueError:
                    pass
        params[name] = ActionParam(
            name=name, type=ptype, required=required,
            default=default, pattern=pattern,
            allow_chars=allow_chars, max=pmax,
        )
    return params


def _find_brace_end(text: str, start: int) -> int | None:
    try:
        i = text.index("{", start)
    except ValueError:
        return None
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return j + 1
    return None


def _extract_ddb_function_at(text: str, start: int) -> str:
    end = _find_brace_end(text, start)
    if end is not None:
        return text[start:end].strip()
    return text[start:].strip()


def _parse_ddb_file(path: Path) -> list[ActionDef]:
    text = path.read_text(encoding="utf-8")
    actions: list[ActionDef] = []

    func_starts = list(_DDB_FUNC_START_RE.finditer(text))
    if not func_starts:
        return actions

    for idx, func_match in enumerate(func_starts):
        name = func_match.group(1)
        func_pos = func_match.start()

        if idx == 0:
            comment_block = text[:func_pos]
        else:
            prev_body_end = _find_brace_end(text, func_starts[idx - 1].start())
            comment_block = text[prev_body_end:
                                 func_pos] if prev_body_end else text[:func_pos]

        desc_m = _DDB_DESC_RE.search(comment_block)
        desc = desc_m.group(1).strip() if desc_m else ""
        params_raw = ", ".join(_DDB_PARAMS_RE.findall(comment_block))
        params = _parse_params(params_raw) if params_raw else {}
        perm_m = _DDB_PERMISSION_RE.search(comment_block)
        permission = perm_m.group(1).strip().lower() if perm_m else ""
        collect_m = _DDB_COLLECT_RE.search(comment_block)
        collect_cats = [c.strip() for c in collect_m.group(
            1).split(",")] if collect_m else []
        collect_args = _parse_all_collect_args(
            comment_block, _DDB_COLLECT_ARGS_RE)

        body = _extract_ddb_function_at(text, func_pos)

        actions.append(ActionDef(
            name=name, description=desc, source="ddb",
            permission=permission or "",  # 空串 → strict scan 报错
            params=params,
            body=body, file_path=str(path),
            collect_categories=collect_cats,
            collect_args=collect_args,
        ))

    return actions


def _parse_shell_file(path: Path) -> list[ActionDef]:
    text = path.read_text(encoding="utf-8")
    actions: list[ActionDef] = []

    func_starts = list(_SH_FUNC_START_RE.finditer(text))
    if not func_starts:
        return actions

    for idx, func_match in enumerate(func_starts):
        name = func_match.group(1)
        func_pos = func_match.start()

        if idx == 0:
            comment_block = text[:func_pos]
        else:
            prev_body_end = _find_brace_end(text, func_starts[idx - 1].start())
            comment_block = text[prev_body_end:
                                 func_pos] if prev_body_end else text[:func_pos]

        desc_m = _SH_DESC_RE.search(comment_block)
        desc = desc_m.group(1).strip() if desc_m else ""
        params_raw = ", ".join(_SH_PARAMS_RE.findall(comment_block))
        params = _parse_params(params_raw) if params_raw else {}
        perm_m = _SH_PERMISSION_RE.search(comment_block)
        permission = perm_m.group(1).strip().lower() if perm_m else ""
        collect_m = _SH_COLLECT_RE.search(comment_block)
        collect_cats = [c.strip() for c in collect_m.group(
            1).split(",")] if collect_m else []
        collect_args = _parse_all_collect_args(
            comment_block, _SH_COLLECT_ARGS_RE)

        body_end = _find_brace_end(text, func_pos)
        if body_end is not None:
            brace_start = func_match.end() - 1
            inner = text[brace_start + 1: body_end - 1]
            lines = inner.split("\n")
            stripped_lines = [l for l in lines if l.strip()]
            if stripped_lines:
                min_indent = min(len(l) - len(l.lstrip())
                                 for l in stripped_lines)
                body = "\n".join(l[min_indent:] for l in lines).strip()
            else:
                body = ""
        else:
            body = ""

        actions.append(ActionDef(
            name=name, description=desc, source="shell",
            permission=permission or "",
            params=params,
            body=body, file_path=str(path),
            collect_categories=collect_cats,
            collect_args=collect_args,
        ))

    return actions


# ── ScriptRegistry ────────────────────────────────────────

class ScriptRegistry:
    """脚本注册表：扫描并管理所有 action 定义。"""

    def __init__(self, scripts_dir: Path | str):
        self._scripts_dir = Path(scripts_dir)
        self._actions: dict[str, ActionDef] = {}
        self._scanned = False
        self._last_fingerprint: str = ""
        # CI 静态校验用：聚合解析阶段的所有错误，运行时不抛、靠调用方决定
        self._parse_errors: list[str] = []

    def _ordered_ddb_files(self, ddb_dir: Path) -> list[Path]:
        return sorted(ddb_dir.glob("*.dos"), key=lambda path: path.name)

    def _scripts_fingerprint(self) -> str:
        entries: list[str] = []
        for pattern in ("dolphindb/*.dos", "shell/*.sh"):
            for f in sorted(self._scripts_dir.glob(pattern)):
                try:
                    entries.append(f"{f.name}:{f.stat().st_mtime}")
                except OSError:
                    pass
        return "|".join(entries)

    def _check_reload(self) -> None:
        if not self._scanned:
            return
        current_fp = self._scripts_fingerprint()
        if current_fp != self._last_fingerprint:
            logger.info("Script files changed, reloading")
            self.scan(force=True)

    def scan(self, force: bool = False) -> dict[str, int]:
        if self._scanned and not force:
            return {"ddb": 0, "shell": 0}

        self._actions.clear()
        self._parse_errors.clear()
        ddb_count = 0
        shell_count = 0

        logger.info("ScriptRegistry scanning: %s (exists=%s)",
                    self._scripts_dir, self._scripts_dir.is_dir())

        ddb_dir = self._scripts_dir / "dolphindb"
        if ddb_dir.is_dir():
            for dos_file in self._ordered_ddb_files(ddb_dir):
                try:
                    actions = _parse_ddb_file(dos_file)
                    for a in actions:
                        if a.name in self._actions:
                            msg = (f"duplicate action '{a.name}' in {dos_file} "
                                   f"(first defined in {self._actions[a.name].file_path})")
                            logger.warning(msg)
                            self._parse_errors.append(msg)
                        if not a.body:
                            self._parse_errors.append(
                                f"empty body for action '{a.name}' in {dos_file}")
                        self._actions[a.name] = a
                        ddb_count += 1
                except Exception as e:
                    logger.error("Failed to parse %s: %s", dos_file, e)
                    self._parse_errors.append(
                        f"parse failed for {dos_file}: {e}")

        shell_dir = self._scripts_dir / "shell"
        if shell_dir.is_dir():
            for sh_file in sorted(shell_dir.glob("*.sh")):
                try:
                    actions = _parse_shell_file(sh_file)
                    for a in actions:
                        if a.name in self._actions:
                            msg = (f"duplicate action '{a.name}' in {sh_file} "
                                   f"(first defined in {self._actions[a.name].file_path})")
                            logger.warning(msg)
                            self._parse_errors.append(msg)
                        if not a.body:
                            self._parse_errors.append(
                                f"empty body for action '{a.name}' in {sh_file}")
                        self._actions[a.name] = a
                        shell_count += 1
                except Exception as e:
                    logger.error("Failed to parse %s: %s", sh_file, e)
                    self._parse_errors.append(
                        f"parse failed for {sh_file}: {e}")

        # @collect 反向校验：collect 引用的 category 应该至少有一个 markdown 描述
        # （这里只校验 collect_args 的 key 与 collect_categories 一致）
        for a in self._actions.values():
            for cat in a.collect_args.keys():
                if cat not in a.collect_categories:
                    self._parse_errors.append(
                        f"action '{a.name}' has @collect_args for "
                        f"'{cat}' but it's not in @collect list")

        # @permission 必填校验
        for a in self._actions.values():
            if not a.permission:
                self._parse_errors.append(
                    f"action '{a.name}' (in {Path(a.file_path).name}) "
                    f"missing @permission annotation. Must be one of: "
                    f"{', '.join(PERMISSION_LEVELS)}"
                )
            elif a.permission not in PERMISSION_LEVELS:
                self._parse_errors.append(
                    f"action '{a.name}' (in {Path(a.file_path).name}) "
                    f"has invalid @permission '{a.permission}'. "
                    f"Must be one of: {', '.join(PERMISSION_LEVELS)}"
                )

        # cross-action 调用校验：禁止 ddb action body 里调用其他 action 名。
        # 因为 ddb_tool 每次只注入当前 action 的 def，跨 action 调用会在运行时
        # 报"function not defined"。如果确实需要复用，应该 inline。
        ddb_action_names = {
            a.name for a in self._actions.values() if a.source == "ddb"
        }
        for a in self._actions.values():
            if a.source != "ddb" or not a.body:
                continue
            # 找 body 里所有形似 `name(` 的调用，排除自身
            for m in re.finditer(r'\b([a-z][a-z0-9_]*)\s*\(', a.body):
                called = m.group(1)
                if called == a.name:
                    continue
                if called in ddb_action_names:
                    self._parse_errors.append(
                        f"action '{a.name}' (in {Path(a.file_path).name}) "
                        f"calls another action '{called}' — "
                        f"cross-action calls are forbidden, please inline."
                    )
                    break  # 一个 action 报一次就够

        self._scanned = True
        self._last_fingerprint = self._scripts_fingerprint()
        logger.info("ScriptRegistry scanned: %d DDB actions, %d Shell actions, %d parse errors",
                    ddb_count, shell_count, len(self._parse_errors))
        return {"ddb": ddb_count, "shell": shell_count}

    def parse_errors(self) -> list[str]:
        """返回最近一次 scan() 收集到的所有解析错误（CI strict 模式用）。"""
        if not self._scanned:
            self.scan()
        return list(self._parse_errors)

    def get_action(self, name: str) -> ActionDef | None:
        if not self._scanned:
            self.scan()
        self._check_reload()
        return self._actions.get(name)

    def get_actions(self, source: str | None = None) -> dict[str, ActionDef]:
        if not self._scanned:
            self.scan()
        self._check_reload()
        if source is None:
            return dict(self._actions)
        return {k: v for k, v in self._actions.items() if v.source == source}

    def get_action_names(self, source: str | None = None) -> list[str]:
        return sorted(self.get_actions(source).keys())

    def shell_template(self, action_name: str) -> str | None:
        action = self.get_action(action_name)
        if action and action.source == "shell":
            return action.body
        return None

    def get_collect_actions(self, category: str) -> list[ActionDef]:
        all_actions = self.get_actions()
        return [a for a in all_actions.values()
                if category in a.collect_categories]

    def action_catalog(
        self,
        source: str | None = None,
        exclude: set[str] | None = None,
    ) -> str:
        actions = self.get_actions(source)
        lines: list[str] = []
        for name in sorted(actions):
            if exclude and name in exclude:
                continue
            a = actions[name]
            header = f"- {name}: {a.description}"
            if a.permission and a.permission != "readonly":
                header += f" [{a.permission}]"
            lines.append(header)
            if a.params:
                param_parts = []
                for p in a.params.values():
                    enum_str = _enum_choices_from_pattern(p.pattern)
                    if p.required:
                        token = f"{p.name}:{p.type}(必填{enum_str})"
                    else:
                        d = f",默认={p.default}" if p.default else ""
                        token = f"{p.name}:{p.type}(可选{d}{enum_str})"
                    param_parts.append(token)
                lines.append(f"  params: {', '.join(param_parts)}")
        return "\n".join(lines)


# ── 全局单例 ──────────────────────────────────────────────

_registry: ScriptRegistry | None = None


def _resolve_scripts_dir() -> Path:
    """从 mcp-config.yaml 解析 scripts/ 目录（= skill_dir / scripts）。"""
    config = load_config()
    skill_dir = resolve_skill_dir(config)
    return skill_dir / "scripts"


def get_script_registry() -> ScriptRegistry:
    global _registry
    if _registry is None:
        _registry = ScriptRegistry(_resolve_scripts_dir())
        _registry.scan()
    return _registry


def reload_script_registry() -> dict[str, int]:
    global _registry
    if _registry is None:
        _registry = ScriptRegistry(_resolve_scripts_dir())
    return _registry.scan(force=True)


# ── CLI 入口（CI 静态校验用） ──────────────────────────────
#
# 用法：
#   python -m mcp_server.script_registry            # 仅打印统计
#   python -m mcp_server.script_registry --strict   # 有任何 parse error 就 exit 1
#   python -m mcp_server.script_registry --scripts-dir <path>  # 指定 scripts 目录

def _main() -> None:
    import argparse
    import sys as _sys

    parser = argparse.ArgumentParser(
        description="Validate dolphindb-ops scripts (.dos / .sh)")
    parser.add_argument("--strict", action="store_true",
                        help="exit 1 if any parse error or duplicate action")
    parser.add_argument("--scripts-dir", default=None,
                        help="override scripts/ dir (default: skill_dir/scripts from yaml)")
    args = parser.parse_args()

    if args.scripts_dir:
        scripts_dir = Path(args.scripts_dir)
    else:
        try:
            scripts_dir = _resolve_scripts_dir()
        except Exception:
            # 没 yaml 也能跑：相对当前文件推 skill_dir/scripts
            scripts_dir = Path(__file__).resolve().parents[1] / "scripts"

    reg = ScriptRegistry(scripts_dir)
    counts = reg.scan(force=True)
    errs = reg.parse_errors()

    print(f"scripts_dir: {scripts_dir}")
    print(f"actions:     {counts['ddb']} ddb + {counts['shell']} shell "
          f"= {counts['ddb'] + counts['shell']} total")
    print(f"errors:      {len(errs)}")

    if errs:
        print("\n=== parse errors ===")
        for e in errs:
            print(f"  - {e}")

    if args.strict and errs:
        print("\nstrict mode: exit 1")
        _sys.exit(1)
    print("\nOK")
    _sys.exit(0)


if __name__ == "__main__":
    _main()
