"""CLI 入口：python -m audit <repo_path>"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .base import get_checker, get_registered_languages
from .report import AuditItem, AuditReport
from .structure import run_structure_checks

# 显式导入以触发 @register 装饰器
from . import check_ts  # noqa: F401
from . import check_py  # noqa: F401
from . import check_go  # noqa: F401
from . import check_rust  # noqa: F401


def check_linter_config(repo: Path) -> tuple[str, str, str]:
    """检查 linter 配置，返回 (status, detail, severity)。"""
    linter_files = [
        ".eslintrc", ".eslintrc.js", ".eslintrc.json", ".eslintrc.yaml",
        "biome.json", ".biome.json",
        "prettier.config.js", ".prettierrc",
        "ruff.toml", ".ruff.toml",
        ".golangci.yml", ".golangci.yaml",
        "clippy.toml", ".clippy.toml",
    ]
    found = [f for f in linter_files if (repo / f).exists()]
    if found:
        return ("PASS", f"发现: {', '.join(found)}", "🟢")
    return ("FAIL", "未发现 linter 配置", "🟢")


def check_readme(repo: Path) -> tuple[str, str, str]:
    for name in ["README.md", "README.rst", "README"]:
        path = repo / name
        if path.exists():
            content = path.read_text(encoding="utf-8", errors="ignore").strip()
            if len(content) > 200:
                return ("PASS", f"{name} ({len(content)} chars)", "🟢")
            return ("FAIL", f"{name} 内容过短或模板", "🟢")
    return ("FAIL", "README 文件缺失", "🟢")


def check_license(repo: Path) -> tuple[str, str, str]:
    for name in ["LICENSE", "LICENSE.txt", "LICENSE.md"]:
        if (repo / name).exists():
            return ("PASS", f"发现 {name}", "🟢")
    return ("FAIL", "LICENSE 文件缺失", "🟢")


def run_compliance_checks(repo: Path) -> list:
    from .report import AuditItem
    items = []
    for name, fn in [("Linter 配置", check_linter_config),
                     ("README 内容", check_readme),
                     ("LICENSE 文件", check_license)]:
        status, detail, sev = fn(repo)
        items.append(AuditItem("compliance", sev, name, status, detail))
    return items


def main() -> None:
    parser = argparse.ArgumentParser(
        description="仓库治理深度审计脚本 (code-governance)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"已注册的语言检查器: {', '.join(get_registered_languages()) or '无'}"
    )
    parser.add_argument("repo_path", nargs="?", default=".",
                       help="仓库路径（默认当前目录）")
    parser.add_argument("--json", action="store_true",
                       help="JSON 格式输出")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="输出详细信息")

    args = parser.parse_args()
    repo = Path(args.repo_path).resolve()
    report = AuditReport(repo_path=str(repo))

    # 层级一：结构检查
    struct_items, lang = run_structure_checks(repo, args.verbose)
    for item in struct_items:
        report.add(item)
    report.detected_lang = lang

    # 层级二：语义检查（插件化）
    checker = get_checker(repo)
    if checker:
        for item in checker.run():
            report.add(item)
    elif lang:
        report.add(AuditItem("semantic", "🟡", f"{lang} 语义检查", "INFO",
                            f"已检测到 {lang} 但尚无对应检查器插件"))
    else:
        report.add(AuditItem("semantic", "🟢", "语义检查", "INFO",
                            "未检测到已知技术栈，跳过语义检查"))

    # 层级三：合规建议
    for item in run_compliance_checks(repo):
        report.add(item)

    # 输出
    if args.json:
        print(report.to_json())
    else:
        report.print_report()

    # exit code
    report.calculate_score()
    if report.score >= 80:
        sys.exit(0)
    elif report.score >= 50:
        sys.exit(1)
    else:
        sys.exit(2)


if __name__ == "__main__":
    main()
