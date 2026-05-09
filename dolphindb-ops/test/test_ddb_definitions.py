"""DDB 函数定义校验脚本

逐个把 scripts/dolphindb/*.dos 中每个 action 的函数体提交到一个真实 DolphinDB
节点（直连，不经 platform / MCP）。两阶段：

  Phase 1 — 检验 `def name(...) { ... }` 是否被节点接受为合法定义
            （DDB 编译期会查直接调用的 token 是否存在；try/catch 不豁免）
  Phase 2 — 提取每个 action body 内被引用的所有函数名（含直接调用、
            partial-application、parseExpr 内字符串拼接），用 DDB 的
            `defs("name")` 实测每个引用是否在该节点上存在；不存在的
            报告出来（不删 action）。

用途：在 lint（解析）和 e2e（实际调用）之间补一道 DDB 自身的语法/编译校验。

退出码：
  0 — Phase 1 全过 + Phase 2 全部引用都存在
  1 — Phase 1 任一失败 或 Phase 2 任一引用不存在（CI 据此判失败）

用法：
  python test/test_ddb_definitions.py --host 192.168.100.44 --port 7932 \\
      --user admin --password 123456
  python test/test_ddb_definitions.py ... --filter cancel  # 只测名字含 cancel 的
  python test/test_ddb_definitions.py ... --verbose        # 打印每个 def 完整错误
  python test/test_ddb_definitions.py ... --no-refs        # 跳过 Phase 2
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import dolphindb as ddb

# 让 mcp_server 包可导入
_TEST_DIR = Path(__file__).resolve().parent
_SKILL_ROOT = _TEST_DIR.parent
sys.path.insert(0, str(_SKILL_ROOT))

from mcp_server.script_registry import ScriptRegistry  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="校验 scripts/dolphindb/*.dos 中每个 action 的函数定义能否被 DDB 接受")
    parser.add_argument("--host", required=True, help="DolphinDB 节点 IP")
    parser.add_argument("--port", type=int, required=True, help="DolphinDB 节点端口")
    parser.add_argument("--user", default="admin")
    parser.add_argument("--password", default="123456")
    parser.add_argument("--filter", default=None,
                        help="只测试名字包含此子串的 action")
    parser.add_argument("--include-compat", action="store_true",
                        help="包含 compat.dos 的 helpers（默认排除，因为这层应被删除）")
    parser.add_argument("--verbose", action="store_true",
                        help="失败时打印完整错误信息（默认截断 200 字符）")
    parser.add_argument("--no-refs", action="store_true",
                        help="跳过 Phase 2 函数引用校验")
    args = parser.parse_args()

    scripts_dir = _SKILL_ROOT / "scripts"
    reg = ScriptRegistry(scripts_dir)
    reg.scan(force=True)

    # 默认排除 compat.dos —— 这是"无 prelude"测试，意在暴露所有调用 helper
    # 的 action（它们应该通过 inline 替换或重写消除掉 compat 依赖）。
    # 用 --include-compat 可以恢复测试 compat 自身（用于改 compat 时校验）。
    actions = [
        a for a in reg.get_actions(source="ddb").values()
        if a.body
        and (args.include_compat or "compat.dos" not in a.file_path)
        and (not args.filter or args.filter in a.name)
    ]

    if not actions:
        print("没有找到匹配的 ddb action")
        return 0

    print(f"=== DDB 函数定义校验（无 prelude 模式）===")
    print(f"目标节点: {args.host}:{args.port}  用户: {args.user}")
    print(f"待校验:   {len(actions)} 个 action（按 file → name 排序）")
    if not args.include_compat:
        print(f"已排除:   compat.dos 的 helpers（用 --include-compat 恢复）")
    print()

    sess = ddb.session()
    if not sess.connect(args.host, args.port, args.user, args.password):
        print(f"❌ 无法连接 {args.host}:{args.port}")
        return 1

    passed: list[tuple[str, float]] = []
    failed: list[tuple[str, str, float]] = []

    # 按 file_path → name 排序，输出便于按文件聚合查看
    ordered = sorted(actions, key=lambda a: (a.file_path, a.name))

    for a in ordered:
        rel_file = Path(a.file_path).name
        t = time.time()
        try:
            sess.run(a.body)
            elapsed_ms = int((time.time() - t) * 1000)
            passed.append((a.name, elapsed_ms))
            print(f"  ✅ [{rel_file:<18}] {a.name:<40} {elapsed_ms:>4}ms")
        except Exception as e:
            elapsed_ms = int((time.time() - t) * 1000)
            err = str(e).strip()
            if not args.verbose and len(err) > 200:
                err = err[:200] + "..."
            failed.append((a.name, err, elapsed_ms))
            print(f"  ❌ [{rel_file:<18}] {a.name:<40} {elapsed_ms:>4}ms  {err}")

    print()
    print("─" * 80)
    total = len(passed) + len(failed)
    rate = (len(passed) / total * 100) if total else 0.0
    print(f"Phase 1 (def 解析): 总计 {total}  通过 {len(passed)}  失败 {len(failed)}  "
          f"通过率 {rate:.1f}%")

    if failed:
        print()
        print("=== Phase 1 失败明细（按文件聚合）===")
        from collections import defaultdict
        by_file: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for name, err, _ms in failed:
            file_path = next(
                (str(Path(a.file_path).name) for a in ordered if a.name == name),
                "?")
            by_file[file_path].append((name, err))
        for file_path in sorted(by_file):
            print(f"\n  --- {file_path} ---")
            for name, err in by_file[file_path]:
                print(f"  ❌ {name}: {err}")

    sess.close()

    # ── Phase 2: 函数引用存在性校验 ──────────────────────────────
    refs_missing: list[tuple[str, str, str]] = []  # (action, ref, file)
    if not args.no_refs:
        print()
        print("─" * 80)
        print("=== Phase 2: 函数引用存在性校验 ===")
        print("提取每个 action body 内的函数调用候选（直接 / partial / parseExpr 内），")
        print("在【新 session】（无任何用户 def）上跑 defs(\"<name>\") 实测。")
        print("不存在 = 该名字在 DDB 内置中找不到（可能是版本兼容兜底，或自身 shadow，或 typo）。")
        print()

        # 关键字 / 控制流（不是函数，跳过）
        SKIP = {
            # SQL
            "select", "from", "where", "group", "by", "order", "asc", "desc",
            "having", "update", "delete", "insert", "into", "values", "exec",
            "distinct", "limit", "offset", "in", "is", "as", "on", "and", "or",
            "not", "null", "true", "false", "case", "when", "then", "else",
            "end", "between", "like", "all", "any", "left", "right", "inner",
            "outer", "join",
            # 控制流 / 关键字
            "if", "else", "for", "while", "do", "break", "continue", "return",
            "throw", "try", "catch", "def", "share", "module", "use",
            # 类型字面量
            "STRING", "SYMBOL", "INT", "LONG", "FLOAT", "DOUBLE", "BOOL",
            "BYTE", "TIMESTAMP", "DATE", "DATETIME", "TIME", "MINUTE",
            "NANOTIME", "DURATION", "ANY", "VOID", "TABLE", "DICT",
            "VECTOR", "SET", "SHARED", "BATCH", "NULL", "TRUE", "FALSE",
        }
        PE_STR_RE = re.compile(r'parseExpr\s*\(\s*"([^"]*)"')
        FN_RE = re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*[\(\{]')
        ASSIGN_RE = re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*=', re.MULTILINE)

        # ★ 新 session：让 defs() 只查 DDB 内置而非用户已 def 的 action
        sess2 = ddb.session()
        if not sess2.connect(args.host, args.port, args.user, args.password):
            print("⚠️  无法建立 fresh session，跳过 Phase 2")
            return 1 if failed else 0

        for a in ordered:
            body = a.body or ""
            locals_set = set(ASSIGN_RE.findall(body))
            params_match = re.match(r'\s*def\s+\w+\s*\(([^)]*)\)', body)
            if params_match:
                for p in params_match.group(1).split(","):
                    p = p.strip().split("=")[0].strip()
                    if p:
                        locals_set.add(p)

            # ★ 把 def 头剔除，否则 FN_RE 会把 def 头里的 `name(` 误认为调用
            body_without_def = re.sub(
                r'^\s*def\s+\w+\s*\([^)]*\)\s*\{', '', body, count=1)

            candidates: set[str] = set(FN_RE.findall(body_without_def))
            for pe_str in PE_STR_RE.findall(body_without_def):
                candidates.update(FN_RE.findall(pe_str))

            candidates -= SKIP
            candidates -= locals_set
            # 不排除 action 自身或其他 action 名 —— 这正是想暴露 shadow / 自递归

            for fn in sorted(candidates):
                try:
                    res = sess2.run(f'defs("{fn}").size()')
                    if int(res) == 0:
                        refs_missing.append(
                            (a.name, fn, Path(a.file_path).name))
                except Exception:
                    refs_missing.append(
                        (a.name, fn, Path(a.file_path).name))

        sess2.close()

        if not refs_missing:
            print("✅ 所有引用都在 DDB 节点的内置函数中存在")
        else:
            print(f"⚠️  {len(refs_missing)} 处引用在 DDB 内置中不存在:")
            print()
            from collections import defaultdict
            by_action: dict[tuple[str, str], list[str]] = defaultdict(list)
            for action, fn, file in refs_missing:
                by_action[(file, action)].append(fn)
            for (file, action), fns in sorted(by_action.items()):
                # 标注：当某个不存在的引用 = action 自己的名字 → 自递归 / shadow
                marked = []
                for f in sorted(fns):
                    marked.append(f + (" ⚠️self/typo?" if f == action else ""))
                print(f"  ❌ [{file:<18}] {action:<32} 不存在: {', '.join(marked)}")

    return 1 if (failed or refs_missing) else 0


if __name__ == "__main__":
    sys.exit(main())
