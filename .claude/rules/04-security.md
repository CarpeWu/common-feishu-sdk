# 安全规则（必须遵守）

## 日志脱敏
- 日志中禁止出现完整 token、app_secret、authorization header
- 使用 log.py 中的 SensitiveFilter 自动脱敏
- 新增日志时检查：是否可能打印敏感信息

## Secrets 管理
- 禁止在代码中硬编码 app_id、app_secret
- .env 文件必须在 .gitignore 中
- 测试中使用 fake 值（cli_test_000 / test_secret_000）

## 输入校验
- 所有用户输入通过 Pydantic 模型校验后再使用
- 校验失败抛出 FeishuValidationError（retryable=False）
