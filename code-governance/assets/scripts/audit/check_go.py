"""Go 语义检查器。"""

from __future__ import annotations

import re
from pathlib import Path

from .base import BaseLangChecker, register
from .report import AuditItem


@register
class GoChecker(BaseLangChecker):
    marker_files = ["go.mod"]
    lang_name = "Go"

    def run(self) -> list[AuditItem]:
        return [i for i in [
            self._check_interface_type(),
            self._check_file_sizes(),
        ] if i is not None]

    def _go_files(self) -> list[Path]:
        return [f for f in self.repo.rglob("*.go")
                if "vendor" not in f.parts]

    def _check_interface_type(self) -> AuditItem:
        files = self._go_files()
        if not files:
            return AuditItem("semantic", "🟡", "GO: 源文件扫描", "INFO", "未找到 .go 文件")

        pat_interface = re.compile(r'interface\{\}')
        total = 0
        for f in files:
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            total += len(pat_interface.findall(content))

        if total == 0:
            return AuditItem("semantic", "🟡", "GO: interface{} 使用 (应使用 any)", "PASS",
                           "零 interface{} — 使用 Go 1.18+ any")
        return AuditItem("semantic", "🟡", "GO: interface{} 使用 (应使用 any)", "FAIL",
                        f"{total} 处 interface{{}} — 应替换为 any")

    def _check_file_sizes(self) -> AuditItem:
        files = self._go_files()
        if not files:
            return AuditItem("semantic", "🟢", "GO: 文件大小分布", "INFO", "")

        large = []
        for f in files:
            try:
                loc = len(f.read_text(encoding="utf-8", errors="ignore").splitlines())
            except Exception:
                continue
            if loc > 500:
                large.append((str(f.relative_to(self.repo)), loc))

        if not large:
            return AuditItem("semantic", "🟢", "GO: 文件大小分布 (>500 LOC)", "PASS", "全部达标")
        detail = "\n".join(f"{p}: {l} LOC" for p, l in sorted(large, key=lambda x: -x[1]))
        return AuditItem("semantic", "🟡", "GO: 文件大小分布 (>500 LOC)", "FAIL",
                        f"{len(large)} 个文件超限:\n{detail}")
