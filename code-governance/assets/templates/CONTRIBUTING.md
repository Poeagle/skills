# Contributing to {{project_name}}

欢迎贡献！以下指南帮助你快速参与项目。

## 开发流程

1. Fork 或 clone 仓库
2. 创建 feature branch: `git checkout -b feat/your-feature`
3. 安装依赖: `{{install_command}}`
4. 进行更改
5. 确保测试通过: `{{test_command}}`
6. 确保 lint 通过: `{{lint_command}}`
7. 提交 PR

## 代码规范

- 遵循项目配置的 formatter 规则
- 所有新代码必须包含测试
- 保持函数简洁（不超过 50 行）
- 使用有意义的命名

## 提交规范

使用 Conventional Commits 格式：

```
feat: 添加用户登录功能
fix: 修复登录页面的样式问题
docs: 更新 API 文档
refactor: 重构认证中间件
test: 添加用户服务的单元测试
```

## PR 要求

- PR 标题使用 Conventional Commits 格式
- 描述变更内容和动机
- 关联相关 issue（如果有）
- 所有 CI 检查必须通过
- 至少 1 名维护者 review 并 approve

## 分支策略

- `main`: 稳定分支，保护状态
- `feat/*`: 功能开发
- `fix/*`: 缺陷修复
- `chore/*`: 杂项任务

---

再次感谢你的贡献！
