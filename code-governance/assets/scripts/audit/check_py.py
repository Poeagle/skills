"""Python 语义检查器。"""

from __future__ import annotations

import re
from pathlib import Path

from .base import BaseLangChecker, register
from .report import AuditItem


@register
class PythonChecker(BaseLangChecker):
    marker_files = ["pyproject.toml", "setup.py", "setup.cfg"]
    lang_name = "Python"

    def run(self) -> list[AuditItem]:
        return [i for i in [
            self._check_any_type(),
            self._check_ignore_comments(),
            self._check_file_sizes(),
            self._check_import_boundaries(),
        ] if i is not None]

    def _py_files(self) -> list[Path]:
        return [f for f in self.repo.rglob("*.py")
                if "venv" not in f.parts and ".venv" not in f.parts
                and "__pycache__" not in f.parts]

    def _check_any_type(self) -> AuditItem:
        files = self._py_files()
        if not files:
            return AuditItem("semantic", "🟡", "PY: 源文件扫描", "INFO", "未找到 .py 文件")

        pat = re.compile(r'(?<!\.):\s*Any\b')
        total = 0
        n_files = 0

        for f in files:
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            c = len(pat.findall(content))
            if c:
                n_files += 1
                total += c

        if total == 0:
            return AuditItem("semantic", "🟡", "PY: Any 类型使用", "PASS", "零 Any — 完美")
        if total <= 5:
            return AuditItem("semantic", "🟡", "PY: Any 类型使用", "FAIL",
                           f"{total} 处 Any ({n_files}/{len(files)} 文件)")
        return AuditItem("semantic", "🔴", "PY: Any 类型使用", "FAIL",
                        f"{total} 处 Any ({n_files}/{len(files)} 文件) — 严重")

    def _check_ignore_comments(self) -> AuditItem:
        files = self._py_files()
        if not files:
            return None  # type: ignore[return-value]

        n_ignore = 0
        n_type_ignore = 0
        for f in files:
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            n_ignore += len(re.findall(r'# noqa', content))
            n_type_ignore += len(re.findall(r'# type:\s*ignore', content))

        total = n_ignore + n_type_ignore
        if total == 0:
            return AuditItem("semantic", "🟡", "PY: # noqa / # type: ignore", "PASS", "零使用")
        sev = "🟡" if total <= 5 else "🔴"
        return AuditItem("semantic", sev, "PY: # noqa / # type: ignore", "FAIL",
                        f"{total} 处 (noqa: {n_ignore}, type:ignore: {n_type_ignore})")

    def _check_file_sizes(self) -> AuditItem:
        src = self.repo / "src"
        if not src.is_dir():
            return AuditItem("semantic", "🟢", "PY: 文件大小分布", "INFO", "无 src/ 目录")

        large = []
        for f in src.rglob("*.py"):
            try:
                loc = len(f.read_text(encoding="utf-8", errors="ignore").splitlines())
            except Exception:
                continue
            if loc > 500:
                large.append((str(f.relative_to(self.repo)), loc))

        if not large:
            return AuditItem("semantic", "🟢", "PY: 文件大小分布 (>500 LOC)", "PASS", "全部达标")
        detail = "\n".join(f"{p}: {l} LOC" for p, l in sorted(large, key=lambda x: -x[1]))
        return AuditItem("semantic", "🟡", "PY: 文件大小分布 (>500 LOC)", "FAIL",
                        f"{len(large)} 个文件超限:\n{detail}")

    def _check_import_boundaries(self) -> AuditItem:
        """检查外部目录是否反向引用 src/。"""
        for ext_dir_name in ["extensions", "plugins"]:
            ext_dir = self.repo / ext_dir_name
            src_dir = self.repo / "src"
            if ext_dir.is_dir() and src_dir.is_dir():
                pat = re.compile(r'from\s+src\.|import\s+src\.')
                violations = []
                for f in ext_dir.rglob("*.py"):
                    try:
                        if pat.search(f.read_text(encoding="utf-8", errors="ignore")):
                            violations.append(str(f.relative_to(self.repo)))
                    except Exception:
                        continue
                if violations:
                    return AuditItem("semantic", "🔴", f"PY: 导入边界 ({ext_dir_name}→src)", "FAIL",
                                    f"{len(violations)} 处违规:\n" + "\n".join(violations))
        return AuditItem("semantic", "🟡", "PY: 导入边界", "PASS", "无违规")
