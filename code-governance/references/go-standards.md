# Go 深度代码规范

基于 references/governance-framework.md 的通用框架，本节定义 Go 项目的特定规则。

## 项目配置

### go.mod 结构

```
module github.com/org/{{project_name}}

go 1.22
```

### 目录布局

```
project-root/
├── cmd/                  # 可执行文件入口
│   └── server/
│       └── main.go
├── internal/             # 私有包（不允许外部导入）
│   ├── core/             # 核心领域逻辑
│   ├── service/          # 业务编排
│   └── handler/          # HTTP/gRPC handler
├── pkg/                  # 可导出的公共库
│   └── apierror/
├── api/                  # API 定义（proto / OpenAPI）
├── config/               # 配置加载
├── scripts/              # 工具脚本
└── test/                 # 集成测试
```

### 标准命令

```bash
go run ./cmd/server          # 启动
go build ./cmd/server        # 构建
go test ./...                # 测试
go vet ./...                 # 静态分析
golangci-lint run            # lint
```

## 类型约束

### 🔴 绝对禁止

```go
// ❌ 禁止
func process(data interface{}) interface{} { ... }
func getValue() interface{} { ... }
```

### ✅ 替代方案

```go
// ✅ 泛型 (Go 1.18+)
func First[T any](items []T) (T, bool) {
    if len(items) == 0 {
        var zero T
        return zero, false
    }
    return items[0], true
}

// ✅ 接口约束
type Stringer interface {
    String() string
}

func Process[T Stringer](items []T) []string {
    result := make([]string, len(items))
    for i, item := range items {
        result[i] = item.String()
    }
    return result
}

// ✅ 定义明确的类型
type UserID string
type Email string

type CreateUserInput struct {
    Name  string `json:"name" validate:"required,min=1,max=100"`
    Email string `json:"email" validate:"required,email"`
}
```

### 规则

- 禁止使用 `interface{}` — 使用 `any`（Go 1.18+ 等价于 `interface{}`，但语义更清晰）
- 优先使用类型参数（泛型）代替 `any`
- 使用明确的类型定义而非字符串别名（见 `UserID` 示例）
- 外部数据入口使用 `validator` 库验证

## 代码风格

### 遵循 gofmt

```bash
gofmt -s -w .      # 格式化
go vet ./...        # 静态检查
golangci-lint run   # 完整 lint
```

### 命名约定

| 元素 | 命名 | 示例 |
|------|------|------|
| 文件 | snake_case | `user_service.go` |
| 包 | single word | `service`, `handler` |
| 导出类型 | PascalCase | `UserService` |
| 未导出类型 | camelCase | `userService` |
| 导出函数 | PascalCase | `CreateUser()` |
| 未导出函数 | camelCase | `createUser()` |
| 接口 | 方法名 + `er` | `Reader`, `Writer`, `Stringer` |
| 常量 | PascalCase | `MaxRetryCount` |
| 错误变量 | 前缀 `Err` | `ErrUserNotFound` |

### 关键规则

```go
// ✅ 正确
var ErrUserNotFound = errors.New("user not found")

type UserService struct { ... }
func NewUserService(repo UserRepository) *UserService { ... }
func (s *UserService) CreateUser(ctx context.Context, input CreateUserInput) (*User, error) { ... }

// ❌ 禁止
type User_service struct { ... }                      // 非 camelCase
func (s *UserService) createUser(...) { ... }         // 应导出的未导出
var ERROR_USER_NOT_FOUND = ...                        // Go 错误变量用 Err 前缀
```

## 文件大小

| 指标 | 阈值 | 行动 |
|------|------|------|
| 文件行数 | > 500 LOC | 必须拆分 |
| 函数行数 | > 40 LOC | 考虑拆分 |
| 单文件类型数 | > 5 | 考虑拆分 |
| 单文件方法接收者 | > 1 个不同类型的接收者 | 必须拆分 |

## 测试规范

### 文件组织

```go
// 单元测试 — 与源文件对应（white-box）
// internal/core/user.go
// → internal/core/user_test.go

// 集成测试 — 放在 test/ 目录
// → test/integration/user_test.go
```

### 命名约定

```go
package core

import (
    "testing"
)

func TestCreateUser(t *testing.T) {
    t.Parallel()
    
    // Arrange
    input := CreateUserInput{
        Name:  "Alice",
        Email: "alice@example.com",
    }
    
    // Act
    user, err := CreateUser(input)
    
    // Assert
    if err != nil {
        t.Fatalf("unexpected error: %v", err)
    }
    if user.Name != "Alice" {
        t.Errorf("got name %q, want %q", user.Name, "Alice")
    }
    if user.ID == "" {
        t.Error("expected non-empty user ID")
    }
}
```

### 表格驱动测试

```go
func TestValidateEmail(t *testing.T) {
    tests := []struct {
        name    string
        email   string
        wantErr bool
    }{
        {name: "valid email", email: "alice@example.com", wantErr: false},
        {name: "missing @", email: "invalid", wantErr: true},
        {name: "empty string", email: "", wantErr: true},
    }
    
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            err := ValidateEmail(tt.email)
            if (err != nil) != tt.wantErr {
                t.Errorf("ValidateEmail(%q) error = %v, wantErr = %v", tt.email, err, tt.wantErr)
            }
        })
    }
}
```

- 使用 `t.Parallel()` 并行执行独立测试
- 使用表格驱动测试（table-driven tests）覆盖多场景
- 使用 `testify/assert` 或 `testify/require` 简化断言（可选）

## 错误处理

```go
// ✅ 哨兵错误
var ErrUserNotFound = errors.New("user not found")

// ✅ 包装错误
if err != nil {
    return fmt.Errorf("create user: %w", err)
}

// ✅ 自定义错误类型
type ValidationError struct {
    Field   string
    Message string
}

func (e *ValidationError) Error() string {
    return fmt.Sprintf("%s: %s", e.Field, e.Message)
}

func (e *ValidationError) Is(target error) bool {
    _, ok := target.(*ValidationError)
    return ok
}

// ❌ 禁止
if err != nil {
    return err  // 未包装，丢失上下文
}
panic(err)       // panic 仅限初始化阶段
_ = err          // 静默忽略错误
```

## 格式化工具

| 工具 | 适用场景 | 推荐 |
|------|----------|------|
| **gofmt** | 所有 Go 项目 | ⭐ 必须（Go 官方标准） |
| **golangci-lint** | CI 集成 | ⭐ 强烈推荐 |
| **go vet** | 基础检查 | 必须 |

## 并发规范

```go
// ✅ 使用 errgroup 管理 goroutine
import "golang.org/x/sync/errgroup"

func processItems(ctx context.Context, items []Item) error {
    g, ctx := errgroup.WithContext(ctx)
    
    for _, item := range items {
        item := item  // 循环变量捕获
        g.Go(func() error {
            return processItem(ctx, item)
        })
    }
    
    return g.Wait()
}

// ❌ 禁止
go func() {                 // 裸 goroutine，未管理生命周期
    doWork()
}()
```

## 环境变量验证

```go
import (
    "os"
    "strconv"
)

type Config struct {
    Port        int
    DatabaseURL string
    APIKey      string
}

func LoadConfig() (*Config, error) {
    port, err := strconv.Atoi(os.Getenv("PORT"))
    if err != nil {
        port = 3000  // 默认值
    }
    
    dbURL := os.Getenv("DATABASE_URL")
    if dbURL == "" {
        return nil, errors.New("DATABASE_URL is required")
    }
    
    apiKey := os.Getenv("API_KEY")
    if apiKey == "" {
        return nil, errors.New("API_KEY is required")
    }
    
    return &Config{
        Port:        port,
        DatabaseURL: dbURL,
        APIKey:      apiKey,
    }, nil
}
```
