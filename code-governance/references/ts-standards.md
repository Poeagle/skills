# TypeScript 深度代码规范

## TypeScript Strict 模式配置

### tsconfig.json 必需设置

```jsonc
{
  "compilerOptions": {
    /* 严格模式家族 — 全部必须开启 */
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true,
    "noPropertyAccessFromIndexSignature": true,
    "exactOptionalPropertyTypes": false, // 按项目需求决定
    
    /* 模块系统 — ESM only */
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "target": "ES2022",
    "lib": ["ES2022"],
    
    /* 输出控制 */
    "outDir": "./dist",
    "rootDir": "./src",
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true,
    
    /* 严格检查 - 额外 */
    "forceConsistentCasingInFileNames": true,
    "skipLibCheck": true,
    "isolatedModules": true,
    "verbatimModuleSyntax": true,
    
    /* 路径映射 */
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src"],
  "exclude": ["node_modules", "dist"]
}
```

## `any` 禁令与替代方案

### 🔴 绝对禁止

```typescript
// ❌ 禁止
function process(data: any): any { ... }
const result: any = someApi();
```

### ✅ 替代方案

| 场景 | 正确做法 |
|------|----------|
| 外部 API 返回值 | `unknown` + 类型收窄（narrow） |
| 泛型容器 | 使用泛型参数 `<T>` |
| 混合类型数组 | 联合类型 `string | number` |
| 递归/自引用结构 | 接口递归定义 |
| 第三方库无类型 | `z.infer<typeof schema>` + Zod schema |

```typescript
// ✅ unknown + 类型守卫
function process(data: unknown): string {
  if (typeof data === 'string') return data;
  if (Array.isArray(data)) return data.join(',');
  throw new Error('Unexpected data type');
}

// ✅ 泛型
function first<T>(arr: T[]): T | undefined {
  return arr[0];
}

// ✅ Zod schema 用于外部边界
import { z } from 'zod';

const ApiResponseSchema = z.object({
  id: z.string(),
  name: z.string(),
  metadata: z.record(z.unknown()).optional(),
});

type ApiResponse = z.infer<typeof ApiResponseSchema>;

function handleResponse(raw: unknown): ApiResponse {
  return ApiResponseSchema.parse(raw);
}
```

### Narrow Adapters 模式

当第三方库没有类型时，使用隔离的适配层：

```typescript
// src/adapters/external-lib.ts — 唯一允许宽松类型的地方
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type ExternalData = any;

// 在适配层内部收窄
export interface NormalizedData {
  id: string;
  label: string;
}

export function normalize(data: ExternalData): NormalizedData {
  return {
    id: String(data?.id ?? ''),
    label: String(data?.label ?? ''),
  };
}
```

**规则**：`any` 只能出现在以 `adapter` 命名的文件中，且必须立即收窄导出。

## ESM 模块规范

```typescript
// ✅ 正确
import { foo } from './foo.js';  // ESM 需要 .js 扩展名
import type { Bar } from './types.js';

export function helper(): void { ... }

// ❌ 禁止
import { foo } from './foo';      // 无扩展名
export default helper;            // default export 禁止
```

**规则**：
- 使用 `import type` 导入仅类型
- 使用具名导出（named exports），禁止 `export default`
- 所有源文件导入路径必须包含 `.js` 扩展名（ESM 约束）

## 导入边界规则

### 分层架构

```
src/
├── core/           ← 领域核心（零外部依赖）
├── services/       ← 业务服务（可依赖 core）
├── api/            ← API 层（可依赖 services + core）
├── cli/            ← CLI 入口（可依赖 api + services + core）
└── extensions/     ← 扩展（可依赖 core，反向禁止）
```

### 导入规则（用 ESLint import/no-restricted-paths 或 Knip 强制执行）

```javascript
// eslint.config.js
{
  rules: {
    'import/no-restricted-paths': ['error', {
      zones: [
        // core 不允许导入 services 及以上
        { target: './src/core', from: './src/services' },
        { target: './src/core', from: './src/api' },
        { target: './src/core', from: './src/cli' },
        { target: './src/core', from: './src/extensions' },
        // extensions 不允许导入 services/api/cli
        { target: './src/extensions', from: './src/services' },
        { target: './src/extensions', from: './src/api' },
        { target: './src/extensions', from: './src/cli' },
        // services 不允许导入 api/cli
        { target: './src/services', from: './src/api' },
        { target: './src/services', from: './src/cli' },
      ],
    }],
  },
}
```

### Monorepo 导入规则

```
packages/
├── shared/       ← 所有人都可以引用
├── core/         ← 只能引用 shared
├── feature-a/    ← 只能引用 shared + core
└── feature-b/    ← 只能引用 shared + core
```

feature-a 和 feature-b 之间**禁止**互相引用。

## 文件大小拆分指南

| 指标 | 阈值 | 行动 |
|------|------|------|
| 文件行数 | > 700 LOC | 必须拆分 |
| 函数行数 | > 50 LOC | 考虑提取子函数 |
| 导入数量 | > 15 | 考虑模块职责过重 |
| 组件 props | > 10 个 | 考虑拆分子组件 |

### 拆分模式

```typescript
// ❌ 不要 — 700+ LOC 单体文件
// src/services/user-service.ts (全部功能)

// ✅ 应该 — 按职责拆分
// src/services/user/user-service.ts        — 主干逻辑
// src/services/user/user-validation.ts     — 验证逻辑
// src/services/user/user-transformer.ts    — 数据转换
// src/services/user/user.types.ts          — 类型定义
```

## 测试命名约定

```typescript
// 单元测试 — 与源文件对应
src/services/user-service.ts
→ test/services/user-service.test.ts

// 集成测试 — .int 后缀
src/api/user-handler.ts
→ test/api/user-handler.int.test.ts

// E2E 测试 — .e2e 后缀
→ test/e2e/user-flow.e2e.test.ts

// 测试工具/夹具
→ test/fixtures/user-fixtures.ts
→ test/utils/test-helpers.ts
```

### 测试结构规范

```typescript
import { describe, it, expect } from 'vitest';

// 顶层描述 = 被测试的模块/函数
describe('UserService', () => {
  // 嵌套 describe = 方法名
  describe('createUser', () => {
    // it 描述 = 行为
    it('should create a user with valid input', async () => {
      // Arrange
      const input = { name: 'Alice', email: 'alice@example.com' };
      
      // Act
      const result = await userService.createUser(input);
      
      // Assert
      expect(result).toMatchObject({ name: 'Alice' });
      expect(result.id).toBeDefined();
    });

    it('should throw on duplicate email', async () => {
      await expect(
        userService.createUser({ name: 'Bob', email: 'alice@example.com' })
      ).rejects.toThrow('Email already exists');
    });
  });
});
```

## 格式化工具选择

| 工具 | 适用场景 | 推荐 |
|------|----------|------|
| **Biome** | TS/JS 新项目 | ⭐ 首选（快速、all-in-one） |
| **Prettier** | 现有 Prettier 项目 | 保持一致性 |
| **oxlint** | 需要极致性能 | 配合 Biome/Prettier 使用 |

**Biome 配置示例**：

```json
{
  "$schema": "./node_modules/@biomejs/biome/configuration_schema.json",
  "organizeImports": {
    "enabled": true
  },
  "linter": {
    "enabled": true,
    "rules": {
      "recommended": true,
      "complexity": {
        "noForEach": "off",
        "noBannedTypes": "error"
      },
      "style": {
        "noNonNullAssertion": "error",
        "useConst": "error"
      }
    }
  },
  "formatter": {
    "enabled": true,
    "indentStyle": "space",
    "indentWidth": 2,
    "lineWidth": 100
  },
  "javascript": {
    "formatter": {
      "quoteStyle": "single",
      "semicolons": "always"
    }
  }
}
```

## Zod Schema 用于外部边界

所有外部数据入口必须使用 Zod schema 验证：

| 边界 | 说明 |
|------|------|
| API 请求体 | 每个 handler 入口解析 |
| 环境变量 | 应用启动时验证 |
| 配置文件 | 加载时解析 |
| 第三方 webhook | payload 解析 |
| 数据库查询参数 | 参数验证 |

### 环境变量验证示例

```typescript
import { z } from 'zod';

const EnvSchema = z.object({
  NODE_ENV: z.enum(['development', 'production', 'test']).default('development'),
  PORT: z.coerce.number().int().positive().default(3000),
  DATABASE_URL: z.string().url(),
  API_KEY: z.string().min(1),
  LOG_LEVEL: z.enum(['debug', 'info', 'warn', 'error']).default('info'),
});

// 应用启动时验证，失败则立即退出
export const env = EnvSchema.parse(process.env);
```

### API 输入验证示例

```typescript
import { z } from 'zod';

// 请求体 schema
export const CreateUserSchema = z.object({
  name: z.string().min(1).max(100),
  email: z.string().email(),
  role: z.enum(['admin', 'user', 'viewer']).default('user'),
});

// 路径参数 schema
export const UserIdSchema = z.object({
  id: z.string().uuid(),
});

// 查询参数 schema
export const ListUsersSchema = z.object({
  page: z.coerce.number().int().positive().default(1),
  limit: z.coerce.number().int().min(1).max(100).default(20),
  search: z.string().optional(),
});

// 在 handler 中使用
export async function createUserHandler(raw: unknown) {
  const input = CreateUserSchema.parse(raw);
  // input 现在有完整的类型推断
}
```

## 循环依赖检测

### 检测方法

```bash
# 使用 dpdm（推荐）
npx dpdm src/index.ts

# 使用 Madge
npx madge --circular src/

# 使用 Knip
npx knip --include duplicate-exports
```

### 预防规则

- 不允许 `A → B → A` 的循环引用
- 工具函数提取到独立的 `shared/` 或 `utils/` 目录
- 使用接口/类型倒置依赖方向
- 事件总线模式解耦双向依赖

## `package.json` Exports 配置完整性

对于库项目，必须正确配置 exports：

```jsonc
{
  "name": "@org/my-package",
  "type": "module",
  "exports": {
    ".": {
      "import": {
        "types": "./dist/index.d.ts",
        "default": "./dist/index.js"
      }
    },
    "./utils": {
      "import": {
        "types": "./dist/utils/index.d.ts",
        "default": "./dist/utils/index.js"
      }
    }
  },
  "main": "./dist/index.js",
  "types": "./dist/index.d.ts",
  "files": ["dist"],
  "sideEffects": false
}
```

**规则**：
- 使用 `"type": "module"` 启用 ESM
- 显式列出 `exports`，不要只依赖 `main`
- 每个 export 路径同时提供 `types` 和 `default` 条件
- `files` 字段限制发布内容
- `sideEffects: false` 启用 tree-shaking
