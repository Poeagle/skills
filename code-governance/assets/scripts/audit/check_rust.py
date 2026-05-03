"""Rust 语义检查器。"""

from __future__ import annotations

import re
from pathlib import Path

from .base import BaseLangChecker, register
from .report import AuditItem


@register
class RustChecker(BaseLangChecker):
    marker_files = ["Cargo.toml"]
    lang_name = "Rust"

    def run(self) -> list[AuditItem]:
        return [i for i in [
            self._check_unsafe(),
            self._check_file_sizes(),
        ] if i is not None]

    def _rs_files(self) -> list[Path]:
        return list(self.repo.rglob("*.rs"))

    def _check_unsafe(self) -> AuditItem:
        files = self._rs_files()
        if not files:
            return AuditItem("semantic", "🟡", "RS: 源文件扫描", "INFO", "未找到 .rs 文件")

        total = 0
        n_files = 0
        for f in files:
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            c = len(re.findall(r'\bunsafe\b', content))
            if c:
                n_files += 1
                total += c

        if total == 0:
            return AuditItem("semantic", "🔴", "RS: unsafe 代码", "PASS", "零 unsafe — 完美")
        return AuditItem("semantic", "🔴", "RS: unsafe 代码", "FAIL",
                        f"{total} 处 unsafe ({n_files} 个文件) — 需要审查")

    def _check_file_sizes(self) -> AuditItem:
        files = self._rs_files()
        if not files:
            return AuditItem("semantic", "🟢", "RS: 文件大小分布", "INFO", "")

        large = []
        for f in files:
            try:
                loc = len(f.read_text(encoding="utf-8", errors="ignore").splitlines())
            except Exception:
                continue
            if loc > 500:
                large.append((str(f.relative_to(self.repo)), loc))

        if not large:
            return AuditItem("semantic", "🟢", "RS: 文件大小分布 (>500 LOC)", "PASS", "全部达标")
        detail = "\n".join(f"{p}: {l} LOC" for p, l in sorted(large, key=lambda x: -x[1]))
        return AuditItem("semantic", "🟡", "RS: 文件大小分布 (>500 LOC)", "FAIL",
                        f"{len(large)} 个文件超限:\n{detail}")
