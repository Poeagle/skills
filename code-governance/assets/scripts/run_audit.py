#!/usr/bin/env python3
"""
仓库治理审计入口。

用法:
  python run_audit.py <repo-path>         # 交通灯报告
  python run_audit.py <repo-path> --json  # JSON 输出
  python run_audit.py <repo-path> -v      # 详细模式

也支持:
  cd assets/scripts && python -m audit <repo-path>
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from audit.__main__ import main  # noqa: E402

if __name__ == "__main__":
    main()
