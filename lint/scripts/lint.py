#!/usr/bin/env python3
"""Lint: 知识库健康扫描——纯机械操作，零 AI"""

import os, re, glob, json
from collections import defaultdict

def find_vault_root():
    cwd = os.getcwd()
    for _ in range(10):
        if os.path.isfile(os.path.join(cwd, "wiki", "index.md")):
            return cwd
        parent = os.path.dirname(cwd)
        if parent == cwd:
            break
        cwd = parent
    return os.getcwd()

def scan(vault):
    result = {
        "dead_links": [],
        "orphan_pages": [],
        "unregistered_pages": [],
        "indexed_but_missing": [],
        "knowledge_conflicts": [],
        "pending_files": 0,
        "stats": {}
    }

    os.chdir(vault)
    wiki_dir = os.path.join(vault, "wiki")

    # 1. 收集所有 wiki 文件（排除 index.md 和 log.md）
    all_files = {}
    for f in glob.glob("wiki/**/*.md", recursive=True):
        name = os.path.relpath(f, "wiki")
        if name in ("index.md", "log.md"):
            continue
        all_files[f] = name

    # 2. 读 index.md 提取已注册的 [[链接]]
    registered = set()
    index_path = os.path.join(wiki_dir, "index.md")
    if os.path.isfile(index_path):
        index_content = open(index_path, "r", encoding="utf-8").read()
        for m in re.finditer(r'\[\[([^\]|#^]+)', index_content):
            registered.add(m.group(1).strip())

    # 3. 索引一致性：已注册但文件不存在
    for name in registered:
        candidates = [
            f"wiki/{name}.md",
            f"wiki/sources/{name}.md",
            f"wiki/entities/{name}.md",
            f"wiki/concepts/{name}.md",
            f"wiki/syntheses/{name}.md",
        ]
        found = any(os.path.isfile(c) for c in candidates)
        if not found:
            result["indexed_but_missing"].append(name)

    # 文件存在但未在 index.md 注册
    # index.md 中的 [[摘要-xxx]] 不含 sources/ 前缀，需要去掉分类前缀再比较
    def strip_category(wikipath):
        """wiki/sources/摘要-xxx → 摘要-xxx"""
        return re.sub(r'^(sources|entities|concepts|syntheses)/', '', re.sub(r'\.md$', '', wikipath))

    for f, name in all_files.items():
        # code-design 页面用独立索引（纯文本仓库列表），不参与 wikilink 注册检查
        if name.startswith("code-design/"):
            continue
        basename = strip_category(name)
        if basename not in registered:
            result["unregistered_pages"].append(basename)

    # 4. 死链检测 + 引用统计
    links_from = defaultdict(list)

    for f in all_files:
        content = open(f, "r", encoding="utf-8").read()
        seen = set()
        for m in re.finditer(r'\[\[([^\]|#^]+)', content):
            target = m.group(1).strip()
            if target in seen:
                continue
            seen.add(target)
            target_candidates = [
                f"wiki/{target}.md",
                f"wiki/sources/{target}.md",
                f"wiki/entities/{target}.md",
                f"wiki/concepts/{target}.md",
                f"wiki/syntheses/{target}.md",
            ]
            raw_candidate = target if target.endswith(".md") else target + ".md"
            target_candidates.append(raw_candidate)

            found = any(os.path.isfile(c) for c in target_candidates)
            if not found:
                result["dead_links"].append({
                    "source": f,
                    "target": f"[[{target}]]"
                })
            links_from[target].append(f)

    # 5. 孤儿页面（排除 code-design，其文档独立不参与双链网络）
    for f, name in all_files.items():
        if name.startswith("code-design/"):
            continue
        basename = strip_category(name)
        if len(links_from.get(basename, [])) == 0 and len(links_from.get(name.replace(".md", ""), [])) == 0:
            content = open(f, encoding="utf-8").read()
            has_outgoing = bool(re.search(r'\[\[([^\]|#^]+)', content))
            result["orphan_pages"].append({
                "page": f,
                "has_outgoing_links": has_outgoing
            })

    # 6. 知识冲突
    for f in all_files:
        content = open(f, encoding="utf-8").read()
        if "知识冲突" in content:
            result["knowledge_conflicts"].append(f)

    # 7. 收件箱积压
    raw_count = 0
    raw_path = os.path.join(vault, "raw")
    if os.path.isdir(raw_path):
        for root, dirs, files in os.walk(raw_path):
            dirs[:] = [d for d in dirs if d not in ("09-archive", "04-weread")]
            raw_count += len([f for f in files if f.endswith(".md")])
    result["pending_files"] = raw_count

    # 8. code-design 完整性检查
    REQUIRED_FILES = ["README.md", "1.设计原理.md", "2.架构.md", "3.实现步骤.md"]

    REQUIRED_HEADINGS = {
        "README.md":        ["职责", "子模块清单", "输入", "输出", "依赖", "被依赖"],
        "1.设计原理.md":     ["问题背景", "边界范围"],
        "2.架构.md":         ["文件清单", "核心接口与类型", "模块关系图", "核心数据流"],
        "3.实现步骤.md":     ["总体流程", "详细拆解", "关键分支", "调用关系"],
    }
    # 允许"设计思路"/"架构决策记录"/"架构决策"作为"问题背景"的互补标题
    ALT_DESIGN_HEADINGS = ["设计思路", "架构决策记录", "架构决策"]

    code_design_report = {"repos": []}

    code_design_base = os.path.join(wiki_dir, "code-design")
    if os.path.isdir(code_design_base):
        for repo in sorted(os.listdir(code_design_base)):
            repo_path = os.path.join(code_design_base, repo)
            if not os.path.isdir(repo_path) or repo.startswith("."):
                continue
            components_dir = os.path.join(repo_path, "4.组件详情")
            if not os.path.isdir(components_dir):
                continue

            repo_report = {"repo": repo, "total_components": 0, "passed": 0, "failed": 0, "defects": []}

            for comp in sorted(os.listdir(components_dir)):
                comp_path = os.path.join(components_dir, comp)
                if not os.path.isdir(comp_path):
                    continue
                repo_report["total_components"] += 1
                comp_defects = []

                # 检查文件完整性
                for rf in REQUIRED_FILES:
                    if not os.path.isfile(os.path.join(comp_path, rf)):
                        comp_defects.append(f"缺失文件 {rf}")

                # 检查子标题完整性
                for rf, headings in REQUIRED_HEADINGS.items():
                    filepath = os.path.join(comp_path, rf)
                    if not os.path.isfile(filepath):
                        continue
                    content = open(filepath, "r", encoding="utf-8").read()
                    for h in headings:
                        # 对 1.设计原理.md 的特殊处理
                        if rf == "1.设计原理.md" and h == "问题背景":
                            alt_found = any(f"## {alt}" in content for alt in ALT_DESIGN_HEADINGS)
                            if "## 问题背景" not in content and not alt_found:
                                comp_defects.append(f"{rf}: 缺失子标题「问题背景」（或「设计思路」「架构决策记录」「架构决策」）")
                            continue
                        if f"## {h}" not in content:
                            comp_defects.append(f"{rf}: 缺失子标题「{h}」")

                if comp_defects:
                    repo_report["failed"] += 1
                    repo_report["defects"].append({"component": comp, "issues": comp_defects})
                else:
                    repo_report["passed"] += 1

            code_design_report["repos"].append(repo_report)

    result["code_design"] = code_design_report

    # 9. 统计
    total_pages = len(all_files)
    total_links = sum(len(v) for v in links_from.values())
    result["stats"] = {
        "total_pages": total_pages,
        "total_links": total_links,
        "dead_link_count": len(result["dead_links"]),
        "orphan_count": len(result["orphan_pages"]),
        "unregistered_count": len(result["unregistered_pages"]),
        "missing_count": len(result["indexed_but_missing"]),
        "conflict_count": len(result["knowledge_conflicts"]),
    }

    return result

if __name__ == "__main__":
    vault = find_vault_root()
    result = scan(vault)
    print(json.dumps(result, indent=2, ensure_ascii=False))
