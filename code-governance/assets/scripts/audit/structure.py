"""语言无关的结构完整性检查。

检查 AGENTS.md 存在性、章节完整性、配套文件等。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from .report import AuditItem


REQUIRED_AGENTS_SECTIONS = [
    "Start", "Map", "Architecture", "Commands",
    "Code", "Tests", "Git", "Security",
]
RECOMMENDED_FILES = [
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CHANGELOG.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/CODEOWNERS",
    "CODEOWNERS",
]
RECOMMENDED_CI_PATTERNS = [
    ".github/workflows/ci.yml",
    ".github/workflows/ci.yaml",
    ".github/workflows/test.yml",
    ".github/workflows/test.yaml",
    ".gitlab-ci.yml",
]
PROJECT_CONFIG_FILES = {
    "TypeScript": ["package.json", "tsconfig.json"],
    "Python": ["pyproject.toml", "setup.py", "setup.cfg"],
    "Go": ["go.mod"],
    "Rust": ["Cargo.toml"],
}


def _detect_project_lang(repo: Path) -> Optional[str]:
    """通过存在性检测项目语言。"""
    if (repo / "Cargo.toml").exists():
        return "Rust"
    if (repo / "go.mod").exists():
        return "Go"
    if (repo / "pyproject.toml").exists():
        return "Python"
    if (repo / "setup.py").exists() or (repo / "setup.cfg").exists():
        return "Python"
    if (repo / "package.json").exists():
        return "TypeScript"
    return None


def check_agents_md_exists(repo: Path, verbose: bool) -> AuditItem:
    path = repo / "AGENTS.md"
    if not path.exists():
        return AuditItem("structure", "🔴", "AGENTS.md 存在性", "FAIL",
                        "AGENTS.md 文件缺失 — 这是治理核心文件")
    return AuditItem("structure", "🔴", "AGENTS.md 存在性", "PASS",
                    str(path) if verbose else "")


def check_agents_md_sections(repo: Path) -> list[AuditItem]:
    path = repo / "AGENTS.md"
    if not path.exists():
        return []

    content = path.read_text(encoding="utf-8", errors="ignore")
    missing = [
        s for s in REQUIRED_AGENTS_SECTIONS
        if not re.search(rf"^##\s+{re.escape(s)}\s*$", content, re.MULTILINE)
    ]

    if missing:
        return [AuditItem("structure", "🔴", "AGENTS.md 章节完整性", "FAIL",
                         f"缺失: {', '.join(missing)}")]
    return [AuditItem("structure", "🔴", "AGENTS.md 章节完整性", "PASS",
                     f"全部 {len(REQUIRED_AGENTS_SECTIONS)} 章存在")]


def check_scoped_agents(repo: Path) -> AuditItem:
    """检查子目录 scoped AGENTS.md。"""
    scoped = sorted(
        p for p in repo.rglob("AGENTS.md")
        if p.parent != repo
    )
    has_submodules = any(
        (repo / d).is_dir() and list((repo / d).rglob("*.[tspygor]*"))
        for d in ["src", "extensions", "packages", "internal"]
    )
    if not has_submodules:
        return AuditItem("structure", "🟡", "Scoped AGENTS.md", "INFO",
                        "无需 scoped AGENTS.md")
    if scoped:
        names = [str(p.relative_to(repo)) for p in scoped]
        return AuditItem("structure", "🟡", "Scoped AGENTS.md", "PASS",
                        f"发现: {', '.join(names)}")
    return AuditItem("structure", "🟡", "Scoped AGENTS.md", "FAIL",
                    "项目有子模块但无 scoped AGENTS.md")


MULTI_AGENT_SYMLINKS = [
    ("CLAUDE.md", "Claude Code"),
    (".cursorrules", "Cursor"),
    (".windsurfrules", "Windsurf"),
    ("CODEX.md", "Codex CLI"),
    (".github/copilot-instructions.md", "GitHub Copilot"),
]


def check_multi_agent_symlinks(repo: Path) -> list[AuditItem]:
    """检查 Multi-Agent 符号链接是否存在且指向 AGENTS.md。"""
    items = []
    agents_md = repo / "AGENTS.md"
    if not agents_md.exists():
        items.append(AuditItem("structure", "🟡", "Multi-Agent 符号链接", "INFO",
                               "AGENTS.md 不存在，跳过符号链接检查"))
        return items

    found = 0
    for filename, platform in MULTI_AGENT_SYMLINKS:
        path = repo / filename
        if path.is_symlink():
            target = path.resolve()
            if target == agents_md.resolve():
                found += 1
            else:
                items.append(AuditItem("structure", "🟡", f"符号链接: {filename}", "FAIL",
                                       f"存在但未指向 AGENTS.md (指向 {target.name})"))
        elif path.exists():
            items.append(AuditItem("structure", "🟡", f"符号链接: {filename}", "FAIL",
                                   f"{filename} 是普通文件而非符号链接"))
        else:
            items.append(AuditItem("structure", "🟢", f"符号链接: {filename}", "FAIL",
                                   f"缺失 — {platform} 无法读取此仓库的治理配置"))

    if found > 0:
        items.append(AuditItem("structure", "🟢", "Multi-Agent 兼容性", "PASS",
                               f"{found}/{len(MULTI_AGENT_SYMLINKS)} 平台已链接"))
    return items


def check_test_framework(repo: Path, lang: Optional[str]) -> AuditItem:
    if lang == "TypeScript":
        pkg = repo / "package.json"
        if not pkg.exists():
            return AuditItem("structure", "🟡", "测试框架配置", "FAIL", "package.json 缺失")
        try:
            deps = json.loads(pkg.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return AuditItem("structure", "🟡", "测试框架配置", "FAIL", "package.json 解析失败")
        all_deps = {**deps.get("dependencies", {}), **deps.get("devDependencies", {})}
        found = [fw for fw in ["vitest", "jest", "mocha", "ava"] if fw in all_deps]
        if found:
            return AuditItem("structure", "🟡", "测试框架配置", "PASS", f"发现: {', '.join(found)}")

    elif lang == "Python":
        for cfg_name in ["pyproject.toml", "pytest.ini", "setup.cfg"]:
            cfg_file = repo / cfg_name
            if cfg_file.exists():
                content = cfg_file.read_text(encoding="utf-8", errors="ignore")
                if "pytest" in content:
                    return AuditItem("structure", "🟡", "测试框架配置", "PASS", f"pytest (via {cfg_name})")
        if (repo / "tox.ini").exists():
            return AuditItem("structure", "🟡", "测试框架配置", "PASS", "tox")

    elif lang == "Go":
        return AuditItem("structure", "🟡", "测试框架配置", "PASS", "go test (built-in)")

    elif lang == "Rust":
        return AuditItem("structure", "🟡", "测试框架配置", "PASS", "cargo test (built-in)")

    return AuditItem("structure", "🟡", "测试框架配置", "FAIL", "未检测到测试框架配置")


def check_recommended_files(repo: Path) -> list[AuditItem]:
    items = []
    # CI 配置
    ci_found = any((repo / p).exists() for p in RECOMMENDED_CI_PATTERNS)
    items.append(AuditItem("structure", "🟢", "CI 工作流配置",
                          "PASS" if ci_found else "FAIL",
                          "" if ci_found else "未发现 CI 配置文件"))

    # 配套文件
    for fname in RECOMMENDED_FILES:
        exists = (repo / fname).exists()
        sev = "🟡" if fname in ("CONTRIBUTING.md", "SECURITY.md") else "🟢"
        items.append(AuditItem("structure", sev, f"文件: {fname}",
                              "PASS" if exists else "FAIL"))
    return items


def check_project_config(repo: Path, lang: Optional[str]) -> list[AuditItem]:
    files = PROJECT_CONFIG_FILES.get(lang, [])
    items = []
    for fname in files:
        exists = (repo / fname).exists()
        items.append(AuditItem("structure", "🟡", f"项目配置: {fname}",
                              "PASS" if exists else "FAIL"))
    return items


def run_structure_checks(repo: Path, verbose: bool) -> tuple[list[AuditItem], Optional[str]]:
    """运行所有结构完整性检查，返回 (items, detected_lang)。"""
    items = []
    lang = _detect_project_lang(repo)

    items.append(check_agents_md_exists(repo, verbose))
    items.extend(check_agents_md_sections(repo))
    items.append(check_scoped_agents(repo))
    items.extend(check_multi_agent_symlinks(repo))
    items.append(check_test_framework(repo, lang))
    items.extend(check_project_config(repo, lang))
    items.extend(check_recommended_files(repo))

    return items, lang
