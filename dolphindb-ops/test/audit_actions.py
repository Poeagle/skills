"""审查 skill 文档中的 action 引用，找出与 ScriptRegistry 不匹配的名称。

退出码：
  0 — 没有 mismatch
  1 — 有 mismatch（CI 用此判定失败）
"""
import os
import re
import sys
from pathlib import Path

# skill 根目录加 sys.path，import 自包含的 mcp_server（不依赖 backend）
_SKILL_ROOT = Path(__file__).resolve().parent.parent  # skills/dolphindb-ops/
sys.path.insert(0, str(_SKILL_ROOT))

from mcp_server.script_registry import get_script_registry  # noqa: E402


reg = get_script_registry()
all_actions = set(reg.get_action_names())

skill_root = os.path.join(os.path.dirname(__file__), '..', 'references')

# Known non-action identifiers to ignore
IGNORE = {
    'execDdb', 'execShell', 'loadRef', 'callApi',
    'config_path', 'target_node', 'cluster_name', 'server_name', 'ddb_log_path',
    'max_mem_size', 'chunk_cache_engine_mem_size', 'enable_raw_script_log',
    'session_timeout', 'max_partial_query_mem_size', 'batch_job_dir',
    'redo_log_dir', 'volumes_dir', 'bad_alloc', 'oom_kill_process',
    'killed_process', 'last_active_time',
    # Non-action identifiers (debug symbols, filesystem names, etc.)
    '__lll_lock_wait', '_metadata', 'sha1_block_data_order_shaext', '_tid_',
}

results = {}
for dirpath, dirs, files in os.walk(skill_root):
    for fn in sorted(files):
        if not fn.endswith('.md'):
            continue
        fpath = os.path.join(dirpath, fn)
        rel = os.path.relpath(fpath, skill_root)
        with open(fpath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for i, line in enumerate(lines, 1):
            # YAML collect action refs
            for name in re.findall(r'action:\s*["\']?(\w+)["\']?', line):
                if name not in all_actions and name not in IGNORE:
                    results.setdefault(rel, []).append(
                        (i, name, 'collect-action', line.strip()))
            # backtick refs that look like action names
            for name in re.findall(r'`(\w+)`', line):
                if '_' in name and name.islower() and len(name) > 4 and name not in all_actions and name not in IGNORE:
                    results.setdefault(rel, []).append(
                        (i, name, 'backtick-ref', line.strip()))

print("=== MISMATCHED ACTION REFS ===\n")
total = 0
for fpath, items in sorted(results.items()):
    # deduplicate
    seen = set()
    unique = []
    for item in items:
        key = (item[0], item[1])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    print(f"--- {fpath} ---")
    for line_no, name, kind, ctx in unique:
        print(f"  L{line_no} [{kind}] \"{name}\"")
        print(f"    > {ctx[:120]}")
        total += 1
    print()

print(f"\nTotal mismatches: {total}")
if total == 0:
    print("All clear!")
    sys.exit(0)
else:
    sys.exit(1)
