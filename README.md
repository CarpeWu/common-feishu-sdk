# ylhp-common-feishu-sdk

基于飞书官方 lark-oapi SDK 的薄封装层，为公司内部提供一行代码调用飞书 API 的能力。

## 特性

- **薄封装层**：不自建 HTTP 层和 Token 管理，完全依赖 lark-oapi 官方 SDK
- **多应用支持**：同一进程可同时操作多个飞书应用
- **类型安全**：所有方法返回类型化对象（dataclass），参数通过 Pydantic 校验
- **智能重试**：选择性重试机制，只对可恢复错误重试
- **日志脱敏**：自动脱敏 token、secret 等敏感信息

## 安装

```bash
uv add ylhp-common-feishu-sdk
```

或使用 pip：

```bash
pip install ylhp-common-feishu-sdk
```

## 快速开始

### 初始化客户端

```python
from ylhp_common_feishu_sdk import Feishu
from ylhp_common_feishu_sdk.config import FeishuConfig

config = FeishuConfig(
    app_id="your_app_id",
    app_secret="your_app_secret",
)

feishu = Feishu(config)
```

### H5 网页授权

```python
# 生成授权 URL
auth_url = feishu.auth.get_auth_url(redirect_uri="https://your-domain.com/callback", state="random_state")

# 通过 code 获取用户信息
user_info = feishu.auth.get_user_info(code="authorization_code")
print(user_info.open_id, user_info.name)
```

### 获取组织架构

```python
# 获取子部门列表
departments = feishu.contact.list_departments(department_id="0")

# 迭代获取所有子部门
for dept in feishu.contact.iter_departments(department_id="0"):
    print(dept.name, dept.open_department_id)

# 获取部门员工
users = feishu.contact.list_department_users(department_id="od_xxx")

# 迭代获取部门所有员工
for user in feishu.contact.iter_department_users(department_id="od_xxx"):
    print(user.name, user.open_id)
```

### 发送消息

```python
# 发送文本消息
feishu.message.send_text(open_id="ou_xxx", text="Hello!")

# 发送卡片消息
card = {
    "type": "template",
    "data": {
        "template_id": "your_template_id",
        "template_variable": {"title": "Hello"}
    }
}
feishu.message.send_card(open_id="ou_xxx", card=card)
```

## 模块说明

| 模块 | 说明 |
|------|------|
| `config` | 配置管理 |
| `auth` | H5 授权登录 |
| `contact` | 组织架构（部门、员工） |
| `message` | 消息推送（文本、卡片） |

## 开发指南

```bash
# 安装依赖
uv sync

# 运行测试
uv run pytest

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
