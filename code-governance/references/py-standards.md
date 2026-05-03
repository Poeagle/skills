# Python 深度代码规范

基于 references/governance-framework.md 的通用框架，本节定义 Python 项目的特定规则。

## 项目配置

### pyproject.toml 必需字段

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "{{package_name}}"
version = "0.1.0"
description = "{{project_description}}"
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "ruff>=0.3.0",
    "mypy>=1.8.0",
]

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "SIM", "ARG"]

[tool.ruff.format]
quote-style = "single"

[tool.mypy]
strict = true
python_version = "3.11"
disallow_any_unimported = true
no_implicit_optional = true
warn_unused_ignores = true

[tool.pytest.ini_options]
testpaths = ["test"]
python_files = ["test_*.py"]
```

### 虚拟环境

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 类型约束

### 🔴 绝对禁止

```python
# ❌ 禁止
def process(data: Any) -> Any: ...
```

### ✅ 替代方案

```python
from collections.abc import Sequence
from typing import TypeVar

T = TypeVar('T')

# ✅ 泛型
def first(items: Sequence[T]) -> T | None:
    return items[0] if items else None

# ✅ Union 类型收窄
from typing import assert_never

def handle(value: str | int | None) -> str:
    if value is None:
        return 'empty'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return value
    assert_never(value)

# ✅ Pydantic 模型用于外部边界
from pydantic import BaseModel, EmailStr

class CreateUserRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    role: str = 'user'
```

### 规则

- `Any` 只能出现在适配器文件（`*_adapter.py`），且必须立即收窄导出
- 所有函数必须有类型注解（mypy strict 模式）
- 使用 `TypeVar` 而非 `Any` 表达泛型意图
- 外部数据入口使用 Pydantic model 验证（API 请求、环境变量、配置文件）

## 代码风格

### 遵循 Ruff 规则

```bash
ruff check .           # lint
ruff format --check .  # 格式检查
ruff format .          # 自动格式化
```

### 命名约定

| 元素 | 命名 | 示例 |
|------|------|------|
| 模块/文件 | snake_case | `user_service.py` |
| 类 | PascalCase | `UserService` |
| 函数/方法 | snake_case | `create_user()` |
| 变量 | snake_case | `user_name` |
| 常量 | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT` |
| 私有 | 前缀 `_` | `_validate_input()` |

### 导入顺序（Ruff I 规则）

```python
# 标准库
import os
import sys
from collections.abc import Sequence
from typing import TypeVar

# 第三方
import pytest
from pydantic import BaseModel

# 项目内部
from myproject.core import User
from myproject.services import user_service
```

## 文件大小

| 指标 | 阈值 | 行动 |
|------|------|------|
| 文件行数 | > 500 LOC | 必须拆分 |
| 函数行数 | > 30 LOC | 考虑提取子函数 |
| 类方法数 | > 15 | 考虑拆分职责 |

## 测试规范

```python
# test/services/test_user_service.py
import pytest
from myproject.services.user_service import create_user

class TestUserService:
    def test_create_user_with_valid_input(self):
        result = create_user(name='Alice', email='alice@example.com')
        assert result.name == 'Alice'
        assert result.id is not None

    def test_create_user_raises_on_duplicate_email(self):
        with pytest.raises(ValueError, match='Email already exists'):
            create_user(name='Bob', email='alice@example.com')
```

### 测试命名

```python
# 单元测试 — 与源文件对应
src/services/user_service.py
→ test/services/test_user_service.py

# 集成测试
src/api/user_handler.py
→ test/api/test_user_handler.py

# 夹具
→ test/conftest.py
→ test/fixtures/user_fixtures.py
```

- 测试文件名前缀 `test_`
- 测试函数名前缀 `test_`
- 类名前缀 `Test`
- 使用 `pytest` 的 fixture 机制管理依赖

## 错误处理

```python
from typing import assert_never

# ✅ 使用自定义异常类
class UserError(Exception): ...
class UserNotFoundError(UserError): ...
class DuplicateEmailError(UserError): ...

# ✅ 显式错误类型
def create_user(name: str, email: str) -> User:
    if email_exists(email):
        raise DuplicateEmailError(f'Email already exists: {email}')
    ...

# ✅ Result 模式（可选）
from dataclasses import dataclass
from typing import Generic, TypeVar

E = TypeVar('E')
T = TypeVar('T')

@dataclass
class Ok(Generic[T]):
    value: T

@dataclass
class Err(Generic[E]):
    error: E

type Result[T, E] = Ok[T] | Err[E]
```

## 格式化工具

| 工具 | 适用场景 | 推荐 |
|------|----------|------|
| **Ruff** | 新项目 | ⭐ 首选（快速、all-in-one lint+format） |
| **Black** | 现有 Black 项目 | 保持一致性 |
| **isort + flake8** | 遗留项目 | 迁移到 Ruff |

## 依赖管理

```toml
# pyproject.toml
[project]
dependencies = [
    "fastapi>=0.110.0",
    "pydantic>=2.6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "ruff>=0.3.0",
    "mypy>=1.8.0",
]
```

- 使用 `pip-tools` 或 `uv` 锁定依赖版本
- 使用 `pip-audit` 或 Dependabot 扫描已知漏洞
- 生产依赖和开发依赖分离

## 环境变量验证

```python
from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """应用配置，启动时从环境变量加载"""
    database_url: str = Field(alias='DATABASE_URL')
    api_key: str = Field(alias='API_KEY', min_length=1)
    log_level: str = Field(default='INFO', alias='LOG_LEVEL')

    model_config = {
        'env_file': '.env',
        'env_file_encoding': 'utf-8',
    }

settings = Settings()  # 启动时验证，失败则立即退出
```
