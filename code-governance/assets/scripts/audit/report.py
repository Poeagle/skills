"""审计报告数据结构和输出格式。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AuditItem:
    """单项检查结果。"""
    category: str          # structure / semantic / compliance
    severity: str          # 🔴 red / 🟡 yellow / 🟢 green
    check: str             # 检查项名称
    status: str            # PASS / FAIL / INFO
    detail: str = ""       # 详细信息

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "severity": self.severity,
            "check": self.check,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass
class AuditReport:
    """审计报告。"""
    repo_path: str
    detected_lang: Optional[str] = None
    items: list[AuditItem] = field(default_factory=list)
    score: int = 0

    def add(self, item: AuditItem) -> None:
        self.items.append(item)

    def calculate_score(self) -> int:
        """计算总分 (0-100)。

        从 70 分基础分开始：
        - 🔴 FAIL: -10 每项
        - 🟡 FAIL: -5  每项
        - 🟢 PASS: +1  每项
        """
        penalty = 0
        bonus = 0
        weights = {"🔴": 10, "🟡": 5, "🟢": 1}
        for item in self.items:
            if item.status == "FAIL":
                penalty += weights.get(item.severity, 5)
            elif item.status == "PASS":
                bonus += 1
        self.score = max(0, min(100, 70 - penalty + bonus))
        return self.score

    def print_report(self) -> None:
        """打印交通灯报告。"""
        self.calculate_score()
        print(f"\n{'='*60}")
        print(f"  仓库治理审计报告: {self.repo_path}")
        if self.detected_lang:
            print(f"  检测语言: {self.detected_lang}")
        print(f"{'='*60}")

        sections = {
            "structure": "结构完整性",
            "semantic": "代码语义检查",
            "compliance": "合规建议",
        }

        for cat_key, cat_name in sections.items():
            cat_items = [i for i in self.items if i.category == cat_key]
            if not cat_items:
                continue
            print(f"\n--- {cat_name} ---")
            for item in cat_items:
                icon_map = {"PASS": "✅", "FAIL": "❌", "INFO": "ℹ️"}
                icon = icon_map.get(item.status, "➖")
                print(f"  {item.severity} {icon} [{item.check}]")
                if item.detail:
                    for line in item.detail.split("\n"):
                        print(f"         {line}")

        # 总体评分
        print(f"\n{'='*60}")
        grade = (
            "🟢 优秀" if self.score >= 80
            else "🟡 需要改进" if self.score >= 50
            else "🔴 急需修复"
        )
        print(f"  📊 总体评分: {self.score}/100 ({grade})")

        reds = len([i for i in self.items if i.severity == "🔴" and i.status == "FAIL"])
        yellows = len([i for i in self.items if i.severity == "🟡" and i.status == "FAIL"])
        greens = len([i for i in self.items if i.severity == "🟢" and i.status == "PASS"])
        print(f"  🔴 红线: {reds}  🟡 建议: {yellows}  🟢 通过: {greens}")
        print(f"{'='*60}\n")

    def to_json(self) -> str:
        self.calculate_score()
        return json.dumps({
            "repo_path": self.repo_path,
            "detected_lang": self.detected_lang,
            "score": self.score,
            "items": [i.to_dict() for i in self.items],
        }, ensure_ascii=False, indent=2)
