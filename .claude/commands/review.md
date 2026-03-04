---
description: 代码审查（提交前必须执行）
---

你是 ylhp-common-feishu-sdk 项目的代码审查者。

请对最近的变更执行全面审查：

1. **查看变更范围**：
   ```bash
   git diff HEAD~1...HEAD --stat
   git diff HEAD~1...HEAD
   ```

2. **逐项检查**：

### 正确性
- [ ] 与 docs/design.md 中的设计一致
- [ ] 飞书 API 方法映射正确（对照 .claude/rules/feishu-api.md）
- [ ] 异常处理完整（所有飞书错误都经过 translate_error）
- [ ] 重试逻辑正确（只重试 retryable=True）

### 安全性
- [ ] 日志中无敏感信息泄露
- [ ] 无硬编码 secrets
- [ ] JSON 使用 json.dumps 构造

### 代码质量
- [ ] 类型注解完整
- [ ] docstring 完整（Args/Returns/Raises/Example）
- [ ] 函数长度 < 50 行
- [ ] 文件长度 < 400 行

### 测试
- [ ] 测试覆盖所有用例（对照设计文档测试用例表）
- [ ] Mock 层级正确（mock lark.Client 方法，非 HTTP）
- [ ] 包含边界场景（空结果、权限错误等）

### 文档同步
- [ ] CLAUDE.md 是否需要更新
- [ ] CHANGELOG.md 是否需要更新

3. **输出审查结果**：
   - ✅ 通过 / ⚠️ 需修改 / ❌ 阻断
   - 每个问题给出文件、行号、建议
