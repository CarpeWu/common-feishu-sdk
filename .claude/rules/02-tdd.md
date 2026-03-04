# 测试规则（必须遵守）

## TDD 流程
所有新功能必须按 Red → Green → Refactor 顺序开发：
1. Red：先写失败的测试
2. Green：写最少的代码让测试通过
3. Refactor：重构，保持测试通过

## Mock 策略
- 禁止 mock HTTP 层（不用 responses 库）
- 必须 mock lark.Client 的方法返回值
- 使用 conftest.py 中的 make_success_response() / make_error_response()

## 覆盖要求
- 每个 Service 方法至少覆盖：成功、参数校验失败、权限错误、空结果
- 分页接口额外覆盖：多页自动翻页
- 重试相关：可重试错误触发重试、不可重试错误立即抛出

## 测试命名
- test_{方法名}_{场景}，例如 test_send_text_empty_text
- 测试文件与源文件镜像：src/ylhp_common_feishu_sdk/services/auth.py → tests/services/test_auth.py

## 运行方式
- 运行全部测试：uv run pytest
- 运行单文件：uv run pytest tests/services/test_contact.py -v
- 实现任何代码后必须运行测试验证
