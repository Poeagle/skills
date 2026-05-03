"""语言检查器基类。

所有语言特定的语义检查器继承此基类，通过 PLUGIN_REGISTRY 注册。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from .report import AuditItem


class BaseLangChecker(ABC):
    """语言特定语义检查器的抽象基类。"""

    # 用于语言检测的标记文件（按优先级）
    marker_files: list[str] = []
    # 语言显示名称
    lang_name: str = ""

    def __init__(self, repo: Path):
        self.repo = repo

    @classmethod
    def detect(cls, repo: Path) -> bool:
        """检测仓库是否使用此语言。"""
        return any((repo / m).exists() for m in cls.marker_files)

    @abstractmethod
    def run(self) -> list[AuditItem]:
        """运行所有语义检查，返回审计项列表。"""
        ...


# ── 插件注册表 ──

_registry: dict[str, type[BaseLangChecker]] = {}


def register(checker_cls: type[BaseLangChecker]) -> type[BaseLangChecker]:
    """注册一个语言检查器。"""
    if checker_cls.lang_name:
        _registry[checker_cls.lang_name] = checker_cls
    return checker_cls


def get_checker(repo: Path) -> Optional[BaseLangChecker]:
    """自动检测语言并返回对应的检查器实例。"""
    for name, cls in _registry.items():
        if cls.detect(repo):
            return cls(repo)
    return None


def get_registered_languages() -> list[str]:
    return list(_registry.keys())
