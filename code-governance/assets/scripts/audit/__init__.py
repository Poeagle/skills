"""code-governance audit package。

导入此包时将自动注册所有语言检查器。
"""

from . import check_ts
from . import check_py
from . import check_go
from . import check_rust
from .base import get_checker, get_registered_languages
from .report import AuditItem, AuditReport
