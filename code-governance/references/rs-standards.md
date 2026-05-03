# Rust 深度代码规范

基于 references/governance-framework.md 的通用框架，本节定义 Rust 项目的特定规则。

## 项目配置

### Cargo.toml 必需字段

```toml
[package]
name = "{{project_name}}"
version = "0.1.0"
edition = "2024"
description = "{{project_description}}"

[dependencies]

[dev-dependencies]
anyhow = "1"
tokio = { version = "1", features = ["full"], optional = true }
criterion = { version = "0.5", optional = true }

[profile.release]
opt-level = 3
lto = true
codegen-units = 1
strip = true

[lints.rust]
unsafe_code = "forbid"
unused_crate_dependencies = "warn"
```

### 目录布局

```
project-root/
├── src/
│   ├── main.rs            # 入口（二进制 crate）
│   ├── lib.rs             # 库入口（库 crate）
│   ├── core/              # 核心领域逻辑
│   ├── service/           # 业务编排
│   └── api/               # API 层
├── tests/                 # 集成测试
├── benches/               # 基准测试
├── examples/              # 示例代码
└── scripts/               # 工具脚本
```

### 标准命令

```bash
cargo build           # 构建
cargo run             # 运行
cargo test            # 测试
cargo clippy          # lint
cargo fmt             # 格式化
cargo check           # 快速类型检查
```

## 类型约束

### 🔴 绝对禁止

```rust
// ❌ 禁止
fn process(data: Box<dyn Any>) -> Box<dyn Any> { ... }

// ❌ 禁止 unsafe（除非在极少数经过审查的情况下）
unsafe fn read_raw() { ... }

// ❌ 禁止 transmute（除非有明确注释说明为何安全）
std::mem::transmute::<A, B>(value)
```

### ✅ 替代方案

```rust
// ✅ 泛型
fn first<T: Clone>(items: &[T]) -> Option<T> {
    items.first().cloned()
}

// ✅ 特征约束
trait Repository<T> {
    fn find_by_id(&self, id: &str) -> Result<Option<T>, Error>;
    fn save(&self, entity: T) -> Result<T, Error>;
}

// ✅ 使用 newtype 表达领域概念
#[derive(Debug, Clone, PartialEq, Eq)]
struct UserId(String);

#[derive(Debug, Clone, PartialEq, Eq)]
struct Email(String);

// ✅ enum 替代 Any
enum ConfigValue {
    String(String),
    Number(i64),
    Boolean(bool),
}
```

### 规则

- 禁止 `unsafe` 代码（在极少数需要时，必须在 `# Safety` doc comment 中详细说明）
- 禁止 `std::mem::transmute`
- 使用 `newtype` 模式（tuple struct）代替类型别名来表达领域语义
- 使用 `enum` 代替 `Box<dyn Any>` 处理异构数据
- 外部数据入口使用 `serde` + 验证

## 代码风格

### 遵循 rustfmt

```bash
cargo fmt                          # 格式化
cargo clippy -- -D warnings        # lint（Deny 模式）
```

### 命名约定

| 元素 | 命名 | 示例 |
|------|------|------|
| 文件 | snake_case | `user_service.rs` |
| 类型/枚举 | PascalCase | `UserService` |
| 特征 | PascalCase | `UserRepository` |
| 函数/方法 | snake_case | `create_user()` |
| 变量 | snake_case | `user_name` |
| 常量 | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT` |
| 宏 | snake_case | `test_with_db!` |
| 模块 | snake_case | `mod user_service` |
| 错误类型 | PascalCase + `Error` | `UserError` |

### 关键规则

```rust
// ✅ 正确
pub struct UserService { ... }
pub fn create_user(input: CreateUserInput) -> Result<User, UserError> { ... }

// ✅ 模块声明与文件结构一致
mod core;
mod service;
mod api;

// ✅ 使用 derive 宏
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct User { ... }

// ❌ 禁止
pub struct user_service { ... }          // 非 PascalCase
fn CreateUser(input: CreateUserInput) { ... }  // 非 snake_case
mod UserService;                          // 模块需 snake_case
```

## 文件大小

| 指标 | 阈值 | 行动 |
|------|------|------|
| 文件行数 | > 500 LOC | 必须拆分 |
| 函数行数 | > 30 LOC | 考虑提取 |
| 单文件类型数 | > 5 | 考虑拆分 |
| impl 块 | > 200 LOC | 考虑拆分文件 |

### 模块拆分模式

```rust
// src/service/user_service.rs — 200+ LOC，不要单体
// 拆分为：
// src/service/user/service.rs       — 主干逻辑
// src/service/user/validation.rs    — 验证逻辑
// src/service/user/transformer.rs   — 数据转换
// src/service/user/types.rs         — 类型定义
// src/service/user/mod.rs           — 重新导出
```

## 测试规范

### 文件组织

```rust
// 单元测试（内联）
// src/core/user.rs
#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_create_user() {
        // ...
    }
}

// 集成测试
// tests/integration/user_test.rs
use myproject::service::user_service;

#[test]
fn test_create_user_via_api() {
    // ...
}

// 文档测试（doc tests）
/// ```
/// use myproject::core::add;
/// assert_eq!(add(2, 3), 5);
/// ```
pub fn add(a: i32, b: i32) -> i32 {
    a + b
}
```

### 命名约定

```rust
#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn create_user_with_valid_input() {
        // Arrange
        let input = CreateUserInput {
            name: "Alice".to_string(),
            email: "alice@example.com".to_string(),
        };
        
        // Act
        let result = create_user(input);
        
        // Assert
        assert!(result.is_ok());
        let user = result.unwrap();
        assert_eq!(user.name, "Alice");
    }
    
    #[test]
    fn create_user_returns_error_on_duplicate_email() {
        // Arrange
        let input = CreateUserInput {
            name: "Bob".to_string(),
            email: "alice@example.com".to_string(),
        };
        
        // Act
        let result = create_user(input);
        
        // Assert
        assert!(result.is_err());
        assert!(matches!(result, Err(UserError::DuplicateEmail(_))));
    }
}
```

- 所有公共函数应有文档测试（doc test）
- 单元测试放在源文件中（`#[cfg(test)] mod tests`）
- 集成测试放在 `tests/` 目录

## 错误处理

```rust
use thiserror::Error;

// ✅ 使用 thiserror 定义错误类型
#[derive(Error, Debug)]
pub enum UserError {
    #[error("user not found: {0}")]
    NotFound(String),
    
    #[error("duplicate email: {0}")]
    DuplicateEmail(String),
    
    #[error("validation error: {0}")]
    Validation(String),
}

// ✅ 自定义 Result 别名
pub type Result<T> = std::result::Result<T, UserError>;

// ✅ 使用 ? 运算符传播错误
pub fn create_user(input: CreateUserInput) -> Result<User> {
    if input.name.is_empty() {
        return Err(UserError::Validation("name is required".into()));
    }
    
    if email_exists(&input.email)? {
        return Err(UserError::DuplicateEmail(input.email.clone()));
    }
    
    Ok(User { /* ... */ })
}

// ❌ 禁止
// panic!("something went wrong");     // panic 仅限初始化阶段
// unwrap() / expect() 在外部分界处   // 在库代码中应返回 Result
```

## 格式化工具

| 工具 | 适用场景 | 推荐 |
|------|----------|------|
| **rustfmt** | 所有 Rust 项目 | ⭐ 必须（官方标准） |
| **clippy** | 所有 Rust 项目 | ⭐ 必须（官方 lint） |

## 异步规范

```rust
// ✅ 使用 tokio 运行时
#[tokio::main]
async fn main() -> Result<()> {
    let service = UserService::new().await?;
    let user = service.create_user(input).await?;
    Ok(())
}

// ✅ 使用 async trait（借助 async-trait 或原生 trait 支持）
#[async_trait]
pub trait UserRepository: Send + Sync {
    async fn find_by_id(&self, id: &str) -> Result<Option<User>>;
    async fn save(&self, user: &User) -> Result<User>;
}
```

## 环境变量验证

```rust
use std::env;
use serde::Deserialize;

#[derive(Debug, Deserialize)]
pub struct Config {
    pub port: u16,
    pub database_url: String,
    pub api_key: String,
    pub log_level: String,
}

impl Config {
    pub fn from_env() -> Result<Self, ConfigError> {
        Ok(Config {
            port: env::var("PORT")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(3000),
            database_url: env::var("DATABASE_URL")
                .map_err(|_| ConfigError::Missing("DATABASE_URL"))?,
            api_key: env::var("API_KEY")
                .map_err(|_| ConfigError::Missing("API_KEY"))?,
            log_level: env::var("LOG_LEVEL").unwrap_or_else(|_| "info".to_string()),
        })
    }
}
```
