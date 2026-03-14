# ylhp-common-feishu-sdk

基于飞书官方 lark-oapi SDK 的薄封装层，为公司内部提供一行代码调用飞书 API 的能力。

## 特性

- **薄封装层**：不自建 HTTP 层和 Token 管理，完全依赖 lark-oapi 官方 SDK
- **多应用支持**：同一进程可同时操作多个飞书应用
- **类型安全**：所有方法返回 Pydantic 模型实例，参数通过 Pydantic 严格校验
- **智能重试**：选择性重试机制，只对 5xx/429 错误重试，参数从实例配置动态读取
- **日志脱敏**：自动脱敏 token、secret 等敏感信息
- **高测试覆盖**：98% 代码覆盖率，170+ 测试用例

## 安装

```bash
uv add ylhp-common-feishu-sdk
```

或使用 pip：

```bash
pip install ylhp-common-feishu-sdk
```

## 快速开始

### 环境变量配置

创建 `.env` 文件或设置环境变量：

```bash
FEISHU_APP_ID=cli_xxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxx
```

### 初始化客户端

```python
from ylhp_common_feishu_sdk import Feishu
from ylhp_common_feishu_sdk.config import FeishuConfig

# 方式1：使用环境变量
feishu = Feishu()

# 方式2：显式传参
config = FeishuConfig(
    app_id="cli_xxxxxxxxxxxx",
    app_secret="your_app_secret",
)
feishu = Feishu(config)

# 方式3：关键字参数
feishu = Feishu(app_id="cli_xxx", app_secret="secret")
```

### H5 网页授权

```python
# 生成授权 URL
auth_url = feishu.auth.build_authorize_url(
    redirect_uri="https://your-domain.com/callback",
    state="random_state"
)

# 通过 code 获取用户信息
user_info = feishu.auth.get_user_info(code="authorization_code")
print(user_info.open_id, user_info.name)
```

### 获取组织架构

```python
# 获取子部门列表（单页）
result = feishu.contacts.list_departments(parent_department_id="0")
for dept in result.items:
    print(dept.name, dept.open_department_id)

# 迭代获取所有子部门（自动翻页）
for dept in feishu.contacts.iter_departments(parent_department_id="0"):
    print(dept.name, dept.open_department_id)

# 获取部门员工列表（单页）
result = feishu.contacts.list_department_users(department_id="od_xxx")
for user in result.items:
    print(user.name, user.open_id)

# 迭代获取部门所有员工（自动翻页）
for user in feishu.contacts.iter_department_users(department_id="od_xxx"):
    print(user.name, user.open_id)

# 获取用户详细信息
user_detail = feishu.contacts.get_user(user_id="ou_xxx")
print(user_detail.name, user_detail.job_title, user_detail.is_activated)
```

### 发送消息

```python
# 发送文本消息给个人
msg_id = feishu.messages.send_text(open_id="ou_xxx", text="Hello!")

# 发送文本消息到群聊
msg_id = feishu.messages.send_text_to_chat(chat_id="oc_xxx", text="Hello Group!")

# 发送卡片消息
card = {
    "config": {"wide_screen_mode": True},
    "elements": [
        {"tag": "div", "text": {"tag": "plain_text", "content": "Hello from SDK!"}}
    ]
}
msg_id = feishu.messages.send_card(receive_id="ou_xxx", card=card)

# 回复消息
reply_id = feishu.messages.reply_text(message_id=msg_id, text="Reply content")
```

### 多应用场景

```python
from ylhp_common_feishu_sdk import Feishu
from ylhp_common_feishu_sdk.config import FeishuConfig

# 注册多个应用
Feishu.register("hr", FeishuConfig(app_id="hr_app_id", app_secret="hr_secret"))
Feishu.register("bot", FeishuConfig(app_id="bot_app_id", app_secret="bot_secret"))

# 按名称获取实例
hr = Feishu.get("hr")
bot = Feishu.get("bot")

# 分别操作不同应用
hr.contacts.iter_departments(parent_department_id="0")
bot.messages.send_text(open_id="ou_xxx", text="来自机器人")
```

### 底层客户端访问

如需调用 SDK 未封装的接口，可直接访问底层 lark-oapi 客户端：

```python
# 访问原生 lark-oapi 客户端
from lark_oapi.api.contact.v3 import BatchGetIdUserRequest

req = BatchGetIdUserRequest.builder().build()
resp = feishu.lark_client.contact.v3.user.batch_get_id(req)
```

## 错误处理

SDK 使用分级异常体系，所有异常继承自 `FeishuError`：

```python
from ylhp_common_feishu_sdk import (
    FeishuError,          # 基类
    FeishuConfigError,    # 配置错误（retryable=False）
    FeishuValidationError,# 参数校验错误（retryable=False）
    FeishuAuthError,      # 认证错误（retryable=False）
    FeishuRateLimitError, # 限流错误（retryable=True）
    FeishuServerError,    # 服务端错误（retryable=True）
    FeishuAPIError,       # 其他 API 错误（retryable=False）
)

try:
    feishu.messages.send_text(open_id="ou_xxx", text="Hello")
except FeishuValidationError as e:
    # 参数校验失败
    print(f"字段 {e.field} 校验失败: {e.detail}")
except FeishuAuthError as e:
    # 认证/权限错误
    print(f"认证失败 [{e.code}]: {e.msg}")
except FeishuRateLimitError as e:
    # 触发限流
    print(f"触发限流，建议等待 {e.retry_after} 秒后重试")
except FeishuServerError as e:
    # 服务端错误
    print(f"服务端错误 [{e.code}]: {e.msg}, log_id={e.log_id}")
except FeishuAPIError as e:
    # 其他 API 错误
    print(f"API 错误 [{e.code}]: {e.msg}")
```

**异常属性说明**：

| 异常类 | 属性 | 类型 | 说明 |
|--------|------|------|------|
| `FeishuError` | `message` | `str` | 完整错误消息 |
| `FeishuValidationError` | `field` | `str` | 校验失败的字段名 |
| `FeishuValidationError` | `detail` | `str` | 详细错误信息 |
| `FeishuAPIError` | `code` | `int` | 飞书错误码 |
| `FeishuAPIError` | `msg` | `str` | 飞书错误消息 |
| `FeishuAPIError` | `log_id` | `str \| None` | 请求日志 ID（提交工单用） |
| `FeishuRateLimitError` | `retry_after` | `float \| None` | 建议等待秒数 |

**重试机制**：
- 自动重试：`FeishuServerError`、`FeishuRateLimitError`
- 不重试：`FeishuValidationError`、`FeishuAuthError`、`FeishuConfigError`
- 重试参数从 `FeishuConfig` 动态读取：`max_retries`、`retry_wait_seconds`

## 配置参数

| 参数 | 环境变量 | 默认值 | 说明 |
|------|---------|--------|------|
| `app_id` | `FEISHU_APP_ID` | - | 飞书应用 App ID（必填） |
| `app_secret` | `FEISHU_APP_SECRET` | - | 飞书应用 App Secret（必填） |
| `domain` | `FEISHU_DOMAIN` | `https://open.feishu.cn` | API 域名（私有化部署时修改） |
| `log_level` | `FEISHU_LOG_LEVEL` | `INFO` | SDK 日志级别（DEBUG/INFO/WARNING/ERROR） |
| `timeout` | `FEISHU_TIMEOUT` | `10` | HTTP 请求超时时间（秒） |
| `max_retries` | `FEISHU_MAX_RETRIES` | `3` | 最大重试次数 |
| `retry_wait_seconds` | `FEISHU_RETRY_WAIT_SECONDS` | `1.0` | 重试基础等待时间（秒），实际 = base × 2^attempt |

## 模块说明

| 模块 | 属性名 | 说明 |
|------|--------|------|
| `auth` | `feishu.auth` | H5 授权登录 |
| `contacts` | `feishu.contacts` | 组织架构（部门、员工） |
| `messages` | `feishu.messages` | 消息推送（文本、卡片） |

## API 参考

### AuthService

| 方法 | 说明 | 返回类型 |
|------|------|---------|
| `build_authorize_url(redirect_uri, state="")` | 构建 H5 授权 URL | `str` |
| `get_user_info(code)` | 通过授权码获取用户信息 | `UserInfo` |

### ContactService

| 方法 | 说明 | 返回类型 |
|------|------|---------|
| `list_departments(parent_department_id="0", page_size=50, page_token=None, fetch_child=False)` | 获取子部门列表（单页） | `PageResult[Department]` |
| `iter_departments(parent_department_id="0", page_size=50, fetch_child=False)` | 迭代获取所有子部门 | `Iterator[Department]` |
| `list_department_users(department_id, page_size=50, page_token=None)` | 获取部门员工列表（单页） | `PageResult[UserInfo]` |
| `iter_department_users(department_id, page_size=50)` | 迭代获取部门所有员工 | `Iterator[UserInfo]` |
| `get_user(user_id, user_id_type="open_id")` | 获取用户详细信息 | `UserDetail` |

### MessagingService

| 方法 | 说明 | 返回类型 |
|------|------|---------|
| `send_text(open_id, text)` | 发送个人文本消息 | `str` (message_id) |
| `send_text_to_chat(chat_id, text)` | 发送群聊文本消息 | `str` (message_id) |
| `send_card(receive_id, card, receive_id_type="open_id")` | 发送卡片消息 | `str` (message_id) |
| `reply_text(message_id, text)` | 回复消息 | `str` (message_id) |

**`send_card` 的 `receive_id_type` 可选值**：

| 值 | 说明 |
|----|------|
| `"open_id"` | 用户 open_id（默认） |
| `"user_id"` | 用户 user_id |
| `"union_id"` | 用户 union_id |
| `"chat_id"` | 群聊 ID |
| `"email"` | 邮箱地址 |

## 返回类型

### UserInfo

用户基本信息（H5 登录返回 / 部门员工列表条目）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `open_id` | `str` | 用户 open_id |
| `name` | `str` | 用户姓名 |
| `en_name` | `str \| None` | 英文名 |
| `email` | `str \| None` | 邮箱 |
| `mobile` | `str \| None` | 手机号 |
| `tenant_key` | `str \| None` | 租户 key |
| `department_ids` | `list[str]` | 所属部门 ID 列表 |
| `avatar_url` | `str \| None` | 头像 URL |

### UserDetail

用户详细信息（`get_user` 返回）。包含 `UserInfo` 的大部分字段，以及以下扩展字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `open_id` | `str` | 用户 open_id |
| `name` | `str` | 用户姓名 |
| `en_name` | `str \| None` | 英文名 |
| `email` | `str \| None` | 邮箱 |
| `mobile` | `str \| None` | 手机号 |
| `department_ids` | `list[str]` | 所属部门 ID 列表 |
| `avatar_url` | `str \| None` | 头像 URL |
| `job_title` | `str \| None` | 职位 |
| `is_activated` | `bool \| None` | 是否已激活 |
| `is_frozen` | `bool \| None` | 是否已冻结 |
| `is_resigned` | `bool \| None` | 是否已离职 |

### Department

部门信息。

| 字段 | 类型 | 说明 |
|------|------|------|
| `department_id` | `str` | 部门 ID |
| `open_department_id` | `str` | 部门 open_department_id |
| `name` | `str` | 部门名称 |
| `parent_department_id` | `str \| None` | 父部门 ID |
| `leader_user_id` | `str \| None` | 部门主管用户 ID |
| `member_count` | `int \| None` | 部门成员数量 |

### PageResult[T]

分页查询结果。

| 字段 | 类型 | 说明 |
|------|------|------|
| `items` | `list[T]` | 当前页数据 |
| `page_token` | `str \| None` | 下一页标记（用于获取下一页） |
| `has_more` | `bool` | 是否有更多数据 |

```python
# 手动翻页示例
result = feishu.contacts.list_departments()
while result.has_more:
    result = feishu.contacts.list_departments(page_token=result.page_token)
```

## 卡片消息

卡片消息遵循飞书开放平台卡片消息协议。完整协议参考：[飞书卡片消息开发文档](https://open.feishu.cn/document/client-docs/bot-v3/card-card-create)

### 原生卡片示例

```python
card = {
    "config": {
        "wide_screen_mode": True
    },
    "header": {
        "title": {"tag": "plain_text", "content": "通知标题"},
        "template": "blue"
    },
    "elements": [
        {
            "tag": "div",
            "text": {"tag": "plain_text", "content": "这是消息内容"}
        },
        {
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "点击按钮"},
                    "url": "https://example.com",
                    "type": "primary"
                }
            ]
        }
    ]
}
feishu.messages.send_card(receive_id="ou_xxx", card=card)
```

### 模板卡片示例

```python
card = {
    "type": "template",
    "data": {
        "template_id": "your_template_id",
        "template_variable": {
            "title": "动态标题",
            "content": "动态内容"
        }
    }
}
feishu.messages.send_card(receive_id="ou_xxx", card=card)
```

## 导出的类型

SDK 导出以下类型，可直接导入使用：

```python
from ylhp_common_feishu_sdk import (
    # 客户端
    Feishu,
    FeishuConfig,
    # 异常
    FeishuError,
    FeishuConfigError,
    FeishuValidationError,
    FeishuAuthError,
    FeishuRateLimitError,
    FeishuServerError,
    FeishuAPIError,
    # 返回类型
    UserInfo,
    UserDetail,
    Department,
    PageResult,
)
```

## 开发指南

```bash
# 安装依赖
uv sync

# 运行测试
uv run pytest

# 运行测试（含覆盖率）
uv run pytest --cov=src/ylhp_common_feishu_sdk

# 代码检查
uv run ruff check src/ tests/

# 格式化
uv run ruff format src/ tests/

# 构建
uv build
```

## 技术栈

- Python >= 3.12
- lark-oapi >= 1.5.3
- pydantic >= 2.12.5

## License

MIT
