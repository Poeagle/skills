"""SKILL 加载与检索（mcp-server 版本，无平台依赖）

skill_dir 由 mcp-config.yaml 提供。如未配置则取 mcp-config.yaml 所在目录。
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

import yaml

from .config import load_config, resolve_skill_dir

logger = logging.getLogger(__name__)

MAIN_SKILL_ID = "dolphindb-ops"
SKILL_FILENAME = "SKILL.md"


def _to_display_source_dir(source_root: Path) -> str:
    """将源目录转换为便于展示的相对路径（优先相对 git 根目录）。"""
    resolved = source_root.resolve()

    # 优先定位最近的 git 根目录
    repo_root: Path | None = None
    for candidate in [resolved, *resolved.parents]:
        if (candidate / ".git").exists():
            repo_root = candidate
            break

    if repo_root is not None:
        try:
            return str(resolved.relative_to(repo_root)).replace("\\", "/")
        except Exception:
            pass

    return source_root.name


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """解析 YAML frontmatter，返回 (metadata, body)"""
    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        meta = {}
    body = parts[2].lstrip("\n")
    return meta, body


def _normalize_string_list(raw: object) -> list[str]:
    """将 frontmatter 中的 tags / typical_questions 等字段归一化为字符串列表。"""
    if not isinstance(raw, list):
        return []
    normalized: list[str] = []
    for item in raw:
        if item is None:
            continue
        if isinstance(item, str):
            text = item.strip()
        else:
            text = str(item).strip()
        if text:
            normalized.append(text)
    return normalized


class SkillEntry:
    """单个主 SKILL 的索引条目"""

    def __init__(self, id: str, name: str, description: str, tags: list[str],
                 typical_questions: list[str], file_path: Path, source_dir: str, source_root_path: Path,
                 references: list[str] | None = None, reference_map: dict[str, str] | None = None):
        self.id = id
        self.name = name
        self.description = description
        self.tags = tags
        self.typical_questions = typical_questions
        self.file_path = file_path
        self.source_dir = source_dir
        self.source_root_path = source_root_path
        self.references = references or []
        self.reference_map = reference_map or {}
        # 分层搜索文本：name/tags 权重高，description 权重低
        self._name_lower = name.lower()
        self._tags_lower = [t.lower() for t in tags]
        self._desc_lower = description.lower()
        self._questions_lower = [q.lower() for q in typical_questions]
        self._refs_lower = [r.lower() for r in self.references]


class SkillLoader:
    """SKILL 知识库加载器"""

    def __init__(self):
        self._entries: dict[str, SkillEntry] = {}
        self._path_to_id: dict[str, str] = {}
        self._path_to_snapshot: dict[str, tuple[int, int]] = {}
        self._source_dirs: list[Path] = []
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.refresh_if_needed(force=True)
            self._loaded = True
            return
        self.refresh_if_needed(force=False)

    def _build_skill_source_dirs(self) -> list[Path]:
        """从 mcp-config.yaml 解析 skill_dir，返回唯一有效目录列表。"""
        config = load_config()
        skill_dir = resolve_skill_dir(config)
        if not skill_dir.exists() or not skill_dir.is_dir():
            logger.warning("Skill dir does not exist: %s", skill_dir)
            return []
        return [skill_dir.resolve()]

    def _discover_skill_files(self, source_dirs: list[Path]) -> dict[str, tuple[Path, Path, tuple[int, int]]]:
        """只发现主 Skill 包的 SKILL.md，并生成文件快照。"""
        discovered: dict[str, tuple[Path, Path, tuple[int, int]]] = {}
        for source_root in source_dirs:
            if not source_root.exists() or not source_root.is_dir():
                continue

            skill_file = source_root / SKILL_FILENAME
            if not skill_file.exists() or not skill_file.is_file():
                continue

            try:
                stat = skill_file.stat()
                snapshot = (int(stat.st_mtime_ns), int(stat.st_size))
                discovered[str(skill_file.resolve())] = (
                    skill_file.resolve(), source_root.resolve(), snapshot)
            except Exception as e:
                logger.warning(
                    "Failed to stat SKILL file %s: %s", skill_file, e)
        return discovered

    def _remove_entry_by_path(self, path_key: str) -> None:
        skill_id = self._path_to_id.pop(path_key, None)
        self._path_to_snapshot.pop(path_key, None)
        if skill_id:
            self._entries.pop(skill_id, None)

    def _upsert_entry(self, skill_file: Path, source_root: Path, snapshot: tuple[int, int]) -> None:
        content = skill_file.read_text(encoding="utf-8")
        meta, _ = _parse_frontmatter(content)
        if not meta:
            logger.warning("SKILL file has no frontmatter: %s", skill_file)
            self._remove_entry_by_path(str(skill_file))
            return

        extra_meta = meta.get("metadata", {}) if isinstance(
            meta.get("metadata", {}), dict) else {}

        skill_id = (meta.get("id") or "").strip() or MAIN_SKILL_ID
        old_path = next(
            (k for k, v in self._path_to_id.items() if v == skill_id), None)
        current_path = str(skill_file)
        if old_path and old_path != current_path:
            logger.warning(
                "Duplicate skill id '%s': keep %s, ignore %s",
                skill_id, old_path, current_path,
            )
            return

        refs_dir = skill_file.parent / "references"
        references: list[str] = []
        reference_map: dict[str, str] = {}
        if refs_dir.exists() and refs_dir.is_dir():
            for md_file in refs_dir.rglob("*.md"):
                try:
                    rel = md_file.relative_to(refs_dir)
                    canonical_ref = str(rel).replace("\\", "/")
                    if canonical_ref.endswith(".md"):
                        canonical_ref = canonical_ref[:-3]
                    references.append(canonical_ref)
                    reference_map[canonical_ref] = canonical_ref

                    basename = md_file.stem.strip()
                    if basename and basename not in reference_map:
                        reference_map[basename] = canonical_ref
                except Exception:
                    continue

        entry = SkillEntry(
            id=skill_id,
            name=str(extra_meta.get("display_name")
                     or meta.get("name", skill_id)),
            description=str(meta.get("description", "")),
            tags=_normalize_string_list(
                meta.get("tags", extra_meta.get("tags", []))),
            typical_questions=_normalize_string_list(
                meta.get("typical_questions", extra_meta.get("typical_questions", []))),
            file_path=skill_file,
            source_dir=_to_display_source_dir(source_root),
            source_root_path=source_root.resolve(),
            references=sorted(references),
            reference_map=reference_map,
        )
        self._entries[entry.id] = entry
        self._path_to_id[current_path] = entry.id
        self._path_to_snapshot[current_path] = snapshot

    def refresh_if_needed(self, force: bool = False) -> dict:
        """按需增量刷新 SKILL 索引。"""
        source_dirs = self._build_skill_source_dirs()
        source_changed = [str(p) for p in source_dirs] != [
            str(p) for p in self._source_dirs]
        discovered = self._discover_skill_files(source_dirs)

        to_remove = set(self._path_to_snapshot.keys()) - set(discovered.keys())
        changed: list[tuple[Path, Path, tuple[int, int]]] = []
        for path_key, (file_path, source_root, snapshot) in discovered.items():
            old_snapshot = self._path_to_snapshot.get(path_key)
            if force or source_changed or old_snapshot != snapshot:
                changed.append((file_path, source_root, snapshot))

        if not force and not source_changed and not to_remove and not changed:
            return {
                "updated": 0,
                "removed": 0,
                "total": len(self._entries),
                "sources": len(source_dirs),
            }

        for path_key in to_remove:
            self._remove_entry_by_path(path_key)

        for file_path, source_root, snapshot in changed:
            try:
                self._upsert_entry(file_path, source_root, snapshot)
            except Exception as e:
                logger.error("Failed to load SKILL from %s: %s",
                             file_path, e, exc_info=True)

        self._source_dirs = source_dirs
        self._loaded = True
        logger.info(
            "SKILL index refreshed: sources=%d, changed=%d, removed=%d, total=%d",
            len(source_dirs), len(changed), len(to_remove), len(self._entries),
        )
        return {
            "updated": len(changed),
            "removed": len(to_remove),
            "total": len(self._entries),
            "sources": len(source_dirs),
        }

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[dict]:
        """单一主 Skill 模型下，只搜索主包 dolphindb-ops 及其 references。"""
        self._ensure_loaded()

        entry = self._entries.get(MAIN_SKILL_ID)
        if entry is None:
            return []

        keywords = set(re.findall(r'[\w一-鿿]+', query.lower()))
        if not keywords:
            return []

        score = 0.0
        for kw in keywords:
            if kw in entry._name_lower:
                score += 3.0
            if any(kw in q for q in entry._questions_lower):
                score += 3.0
            if any(kw in t for t in entry._tags_lower):
                score += 2.0
            if any(kw in r for r in entry._refs_lower):
                score += 2.0
            if kw in entry._desc_lower:
                score += 1.0

        if score <= 0:
            return []

        normalized = score / (len(keywords) * 11.0)
        return [{
            "id": entry.id,
            "name": entry.name,
            "description": entry.description,
            "tags": entry.tags,
            "relevance": round(normalized, 2),
            "references": entry.references,
        }][:top_k]

    def read(self, skill_id: str) -> Optional[str]:
        """读取主 Skill 的 SKILL.md 内容。"""
        self._ensure_loaded()

        if str(skill_id or "").strip() != MAIN_SKILL_ID:
            return None

        entry = self._entries.get(MAIN_SKILL_ID)
        if not entry:
            return None

        if not entry.file_path.exists():
            logger.warning("SKILL file not found: %s", entry.file_path)
            return None

        try:
            return entry.file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error("Failed to read SKILL file %s: %s",
                         entry.file_path, e)
            return None

    def _resolve_reference(self, entry: SkillEntry, ref: str) -> str | None:
        ref_key = str(ref or "").strip().strip("/")
        if not ref_key:
            return None
        return entry.reference_map.get(ref_key)

    def read_reference(self, skill_id: str, ref: str) -> Optional[str]:
        """读取主 Skill 下 references/<ref>.md 片段内容"""
        self._ensure_loaded()

        if str(skill_id or "").strip() != MAIN_SKILL_ID:
            return None

        entry = self._entries.get(MAIN_SKILL_ID)
        if not entry:
            return None

        resolved_ref = self._resolve_reference(entry, ref)
        if not resolved_ref:
            logger.warning("Reference not found: %s", ref)
            return None

        ref_path = entry.file_path.parent / "references" / f"{resolved_ref}.md"
        ref_path = ref_path.resolve()

        refs_root = (entry.file_path.parent / "references").resolve()
        if not str(ref_path).startswith(str(refs_root)):
            logger.warning(
                "Reference path escapes references dir: %s", ref_path)
            return None

        if not ref_path.exists():
            logger.warning("Reference file not found: %s", ref_path)
            return None

        try:
            return ref_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error("Failed to read reference file %s: %s",
                         ref_path, e)
            return None

    def list_references(self, skill_id: str) -> list[str]:
        """列出主 Skill 下所有可加载的 reference 片段路径（相对于 references/）"""
        self._ensure_loaded()

        if str(skill_id or "").strip() != MAIN_SKILL_ID:
            return []

        entry = self._entries.get(MAIN_SKILL_ID)
        if not entry:
            return []

        return list(entry.references)


# 单例
_loader: Optional[SkillLoader] = None


def get_skill_loader() -> SkillLoader:
    global _loader
    if _loader is None:
        _loader = SkillLoader()
    return _loader
