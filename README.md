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
    "elements": [
        {"tag": "div", "text": {"content": "Hello from SDK!", "tag": "plain_text"}}
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
hr.contacts.iter_departments()
bot.messages.send_text("ou_xxx", "来自机器人")
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
    feishu.messages.send_text("ou_xxx", "Hello")
except FeishuValidationError as e:
    print(f"参数错误: {e.message}")
except FeishuAuthError as e:
    print(f"认证失败: {e.message}")
except FeishuRateLimitError as e:
    print(f"触发限流: {e.message}")
except FeishuServerError as e:
    print(f"服务端错误: {e.message}")
```

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
| `log_level` | `FEISHU_LOG_LEVEL` | `INFO` | SDK 日志级别 |
| `timeout` | `FEISHU_TIMEOUT` | `10` | HTTP 请求超时时间（秒） |
| `max_retries` | `FEISHU_MAX_RETRIES` | `3` | 最大重试次数 |
| `retry_wait_seconds` | `FEISHU_RETRY_WAIT_SECONDS` | `1.0` | 重试基础等待时间（秒） |

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
| `list_departments(...)` | 获取子部门列表（单页） | `PageResult[Department]` |
| `iter_departments(...)` | 迭代获取所有子部门 | `Iterator[Department]` |
| `list_department_users(department_id, ...)` | 获取部门员工列表（单页） | `PageResult[UserInfo]` |
| `iter_department_users(department_id, ...)` | 迭代获取部门所有员工 | `Iterator[UserInfo]` |
| `get_user(user_id, user_id_type="open_id")` | 获取用户详细信息 | `UserDetail` |

### MessagingService

| 方法 | 说明 | 返回类型 |
|------|------|---------|
| `send_text(open_id, text)` | 发送个人文本消息 | `str` (message_id) |
| `send_text_to_chat(chat_id, text)` | 发送群聊文本消息 | `str` (message_id) |
| `send_card(receive_id, card, receive_id_type="open_id")` | 发送卡片消息 | `str` (message_id) |
| `reply_text(message_id, text)` | 回复消息 | `str` (message_id) |

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
