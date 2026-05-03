"""TypeScript 语义检查器。

通过 @register 装饰器自动注册到插件注册表。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .base import BaseLangChecker, register
from .report import AuditItem


@register
class TypeScriptChecker(BaseLangChecker):
    marker_files = ["package.json", "tsconfig.json"]
    lang_name = "TypeScript"

    def run(self) -> list[AuditItem]:
        items: list[AuditItem] = []

        items.append(self._check_any_type())
        items.append(self._check_ts_ignore())
        items.append(self._check_file_sizes())
        items.append(self._check_import_boundaries())
        items.append(self._check_exports_config())

        return [i for i in items if i is not None]

    def _ts_files(self) -> list[Path]:
        files = list(self.repo.rglob("*.ts")) + list(self.repo.rglob("*.tsx"))
        # 排除 node_modules 和 dist
        return [f for f in files
                if "node_modules" not in f.parts and "dist" not in f.parts]

    def _check_any_type(self) -> AuditItem:
        files = self._ts_files()
        if not files:
            return AuditItem("semantic", "🟡", "TS: 源文件扫描", "INFO",
                           "未找到 .ts/.tsx 文件")

        pat_any = re.compile(r':\s*any\b')
        pat_as_any = re.compile(r'as\s+any\b')
        total = 0
        n_files = 0

        for f in files:
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            c = len(pat_any.findall(content)) + len(pat_as_any.findall(content))
            if c:
                n_files += 1
                total += c

        if total == 0:
            return AuditItem("semantic", "🔴", "TS: any 类型使用", "PASS",
                           "零 any — 完美")
        if total <= 5:
            return AuditItem("semantic", "🟡", "TS: any 类型使用", "FAIL",
                           f"{total} 处 any ({n_files}/{len(files)} 文件)")
        return AuditItem("semantic", "🔴", "TS: any 类型使用", "FAIL",
                        f"{total} 处 any ({n_files}/{len(files)} 文件) — 严重")

    def _check_ts_ignore(self) -> AuditItem:
        files = self._ts_files()
        if not files:
            return AuditItem("semantic", "🟡", "TS: 源文件扫描", "INFO", "")

        n_ignore = 0
        n_nocheck = 0
        for f in files:
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            n_ignore += len(re.findall(r'@ts-ignore', content))
            n_nocheck += len(re.findall(r'@ts-nocheck', content))

        total = n_ignore + n_nocheck
        if total == 0:
            return AuditItem("semantic", "🟡", "TS: @ts-ignore / @ts-nocheck", "PASS", "零使用")
        sev = "🟡" if total <= 3 else "🔴"
        return AuditItem("semantic", sev, "TS: @ts-ignore / @ts-nocheck", "FAIL",
                        f"{total} 处 (ignore: {n_ignore}, nocheck: {n_nocheck})")

    def _check_file_sizes(self) -> AuditItem:
        src = self.repo / "src"
        if not src.is_dir():
            return AuditItem("semantic", "🟢", "TS: 文件大小分布", "INFO", "无 src/ 目录")

        large = []
        for f in list(src.rglob("*.ts")) + list(src.rglob("*.tsx")):
            try:
                loc = len(f.read_text(encoding="utf-8", errors="ignore").splitlines())
            except Exception:
                continue
            if loc > 700:
                large.append((str(f.relative_to(self.repo)), loc))

        if not large:
            return AuditItem("semantic", "🟢", "TS: 文件大小分布 (>700 LOC)", "PASS",
                           "全部达标")
        detail = "\n".join(f"{p}: {l} LOC" for p, l in sorted(large, key=lambda x: -x[1]))
        return AuditItem("semantic", "🟡", "TS: 文件大小分布 (>700 LOC)", "FAIL",
                        f"{len(large)} 个文件超限:\n{detail}")

    def _check_import_boundaries(self) -> AuditItem:
        ext_dir = self.repo / "extensions"
        src_dir = self.repo / "src"
        if not ext_dir.is_dir() or not src_dir.is_dir():
            return AuditItem("semantic", "🟡", "TS: 导入边界", "INFO", "无 extensions 或 src")

        pat = re.compile(r'from\s+["\']\.\./(?:src|core)/|import\s+["\']\.\./(?:src|core)/')
        violations = []
        for f in list(ext_dir.rglob("*.ts")) + list(ext_dir.rglob("*.tsx")):
            try:
                if pat.search(f.read_text(encoding="utf-8", errors="ignore")):
                    violations.append(str(f.relative_to(self.repo)))
            except Exception:
                continue

        if not violations:
            return AuditItem("semantic", "🟡", "TS: 导入边界 (extensions→src)", "PASS", "无违规")
        return AuditItem("semantic", "🔴", "TS: 导入边界 (extensions→src)", "FAIL",
                        f"{len(violations)} 处违规:\n" + "\n".join(violations))

    def _check_exports_config(self) -> AuditItem:
        pkg = self.repo / "package.json"
        if not pkg.exists():
            return AuditItem("semantic", "🟢", "TS: package.json exports", "INFO", "")

        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return AuditItem("semantic", "🟡", "TS: package.json exports", "FAIL", "解析失败")

        issues = []
        if "exports" not in data:
            issues.append("缺 exports")
        if data.get("type") != "module":
            issues.append("type 非 module")
        if "types" not in data:
            issues.append("缺 types")

        if not issues:
            return AuditItem("semantic", "🟢", "TS: package.json exports", "PASS", "完整")
        return AuditItem("semantic", "🟡", "TS: package.json exports", "FAIL",
                        "; ".join(issues))
