# Git 工作流规则

## 提交信息
格式：<type>(<scope>): <description>

type 必须是以下之一：
- feat: 新功能
- fix: 修复 bug
- refactor: 重构（不改变行为）
- test: 测试相关
- docs: 文档更新
- chore: 构建/工具配置

scope 是模块名：config, exceptions, log, models, retry, auth, messaging, contact, client

示例：
- feat(contact): add list_departments with auto-pagination
- test(messaging): add card message test cases
- docs: sync design doc after API mapping fix

## 提交粒度
- 每个逻辑完整的变更一个提交
- 不要把测试和实现放在不同的提交里（一起提交）
- 重构单独提交

## PR 审查
- 创建 PR 前先运行 `uv run pytest && uv run ruff check src/ tests/`
- PR 描述需列出对应的需求编号（F-001, F-002 等）
