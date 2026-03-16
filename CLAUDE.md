# CLAUDE.md

## 项目概述
ylhp-common-feishu-sdk：基于飞书官方 lark-oapi SDK 的薄封装层，
为公司内部提供一行代码调用飞书 API 的能力。
四个核心模块：Auth（H5授权登录）、Contact（组织架构）、Message（消息推送）、Attendance（假勤审批）。
支持多应用场景：同一进程可同时操作多个飞书应用。

## 核心原则（必须遵守）
1. **不自建 HTTP 层和 Token 管理**。所有网络通信和 tenant_access_token 管理由 lark-oapi 官方 SDK 负责。
2. **不使用单例模式**。Feishu 是普通类，每次实例化创建独立客户端。多应用通过命名注册表共享。
3. **参数校验用 Pydantic**。所有 Service 方法的入参必须通过 models.py 中的 Pydantic 模型校验。
4. **JSON 构造用 json.dumps()**。绝对禁止用 f-string 拼接 JSON 字符串。
5. **异常必须翻译**。所有飞书 API 错误通过 exceptions.py 的 translate_error() 转换为语义化异常。
6. **日志必须脱敏**。token、secret、authorization 等字段在日志中必须被掩码。
7. **H5 授权的 code 不重试**。code 是一次性的。get_user_info 内部分两步：步骤1不重试，步骤2可重试。
8. **选择性重试**。@with_retry 从 self._config 动态读取重试参数。只对 retryable=True 的异常重试。最终失败时记录总重试次数和总耗时。
9. **返回类型化对象**。Service 方法返回 Pydantic 模型实例（UserInfo、Department 等），不返回 dict。
10. **日志冒泡到宿主**。SDK 使用 NullHandler + propagate=True，让日志自然冒泡给宿主应用的 root logger。

## 飞书 API 与 lark-oapi 方法映射（重要！）
| 本 SDK 方法 | 飞书 API | lark-oapi 调用 | Request 类 |
|-------------|---------|---------------|------------|
| list_departments | GET /contact/v3/departments/:id/children | client.contact.v3.department.children(req) | ChildrenDepartmentRequest |
| list_department_users | GET /contact/v3/users/find_by_department | client.contact.v3.user.find_by_department(req) | FindByDepartmentUserRequest |
| get_user | GET /contact/v3/users/:user_id | client.contact.v3.user.get(req) | GetUserRequest |
| send_text / send_card | POST /im/v1/messages | client.im.v1.message.create(req) | CreateMessageRequest |
| reply_text | POST /im/v1/messages/:message_id/reply | client.im.v1.message.reply(req) | ReplyMessageRequest |
| code→token | POST /authen/v1/oidc/access_token | client.authen.v1.oidc_access_token.create(req) | CreateOidcAccessTokenRequest |
| token→user_info | GET /authen/v1/user_info | client.authen.v1.user_info.get(req) | GetUserInfoRequest |
| get_user_approvals | POST /attendance/v1/user_approvals/query | client.attendance.v1.user_approval.query(req) | QueryUserApprovalRequest |

## 技术栈
- Python >= 3.12
- lark-oapi >= 1.5.3（官方 SDK）
- pydantic >= 2.12.5（入参校验）
- pytest >= 9.0.2（测试）
- ruff >= 0.15.2（代码检查 + 格式化）
- uv（包管理）

## 构建与测试命令
- 安装依赖: `uv sync`
- 运行测试: `uv run pytest`
- 代码检查: `uv run ruff check src/ tests/`
- 格式化: `uv run ruff format src/ tests/`

## 发布流程
1. **更新版本号**: 修改 `pyproject.toml` 中的 `version`（每次发布必须更改）
2. **构建**: `uv build`（生成 dist/ 目录下的 .tar.gz 和 .whl 文件）
3. **发布到公司 Gitea**:
   ```bash
   uv publish -u <用户名> -p <密码> --publish-url https://<gitea域名>/api/packages/<所有者>/pypi
   ```
   - `<所有者>` = 用户名 或 组织名（取决于发布到个人还是组织空间）

**注意**: 版本号必须更改，否则发布会失败。

## 代码规范
- 行宽: 100 字符
- 类型提示: 所有公共方法必须有完整的类型注解
- 文档字符串: Google 风格，包含 Args / Returns / Raises / Example
- 命名: snake_case，类名 PascalCase
- Python 3.12 语法: 可直接使用 `X | Y` 联合类型、泛型 `class Foo[T]`

## 目录结构
- 源码: src/ylhp_common_feishu_sdk/
- 测试: tests/（镜像 src 结构）
- 示例: examples/

## 测试 Mock 策略
- 不使用 responses 库 mock HTTP 层
- 直接 mock lark.Client 的方法返回值
- 使用 conftest.py 中的 make_success_response() / make_error_response()
- 每个测试创建新的 Feishu 实例，无需 reset()
- autouse fixture 仅清空注册表
- 通讯录测试需 mock:
  - client.contact.v3.department.children() (非 .list())
  - client.contact.v3.user.find_by_department() (非 .list())
  - client.contact.v3.user.get()

## 新增 Service 的标准流程
1. 在 src/ylhp_common_feishu_sdk/services/ 创建新文件
2. 继承 BaseService（自动获得 self._client 和 self._config）
3. 方法流程: 参数校验 → 日志 → 构造 Builder 请求 → 调用官方 SDK → _check_response → 返回类型化对象
4. 加 @with_retry 装饰器（自动从 self._config 读取重试配置）
5. 如有分页接口，同时提供 list_xxx（单页）和 iter_xxx（自动翻页）
6. 在 client.py 的 Feishu.__init__ 中注册为属性
7. 在 tests/services/ 编写测试（含空结果、权限错误场景）
8. 覆盖率 >= 80%

## MVP 验证清单
- [ ] 能创建多个独立的 Feishu 客户端实例（不同 app_id）
- [ ] 能通过命名注册表注册和获取实例
- [ ] 注册表并发安全
- [ ] 能获取 Tenant Access Token（自动缓存/刷新）
- [ ] 能构建 H5 网页授权 URL（使用配置的 domain，含 state 参数）
- [ ] 能通过授权 code 获取用户 open_id（步骤1不重试，步骤2可重试）
- [ ] 能获取子部门列表（使用 department.children API）
- [ ] 能通过迭代器自动翻页获取全部子部门
- [ ] 能获取部门直属员工列表（使用 user.find_by_department API）
- [ ] 能通过迭代器自动翻页获取部门全部员工
- [ ] 能发送个人文本消息（仅对 5xx/429 重试，重试参数从 config 动态读取）
- [ ] 能发送卡片消息（interactive）
- [ ] 重试最终失败时日志包含总重试次数和总耗时

## 开发流程

所有开发流程规则在 `.claude/rules/01-dev-workflow.md` 中定义，必须严格遵守。
新会话开始时，主动询问开发者当前要做什么，并按流程引导。