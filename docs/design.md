# ylhp-common-feishu-sdk 需求与架构设计文档

## 第一部分：需求规格说明书（PRD）

### 1. 项目背景与目标

#### 1.1 问题陈述

公司内部多个项目需要与飞书 API 交互，具体场景包括：

- **H5 应用**：需要通过飞书 OAuth 2.0 授权获取员工身份（open_id），实现免登录
- **员工数据同步**：需要定期拉取组织架构（部门 + 员工）同步到 PostgreSQL
- **消息推送**：日报提醒、漏写通知、晨会材料推送等自动化消息

当前状态：
- 各项目各自调用飞书 REST API，散落大量重复代码
- Token 管理逻辑在各项目中重复实现，未处理并发刷新
- H5 授权登录流程每个项目各写一套，逻辑混乱
- 没有统一的错误处理和日志

#### 1.2 项目目标

构建一个基于飞书官方 `lark-oapi` SDK 的**薄封装层**，实现：

- **一行初始化，一行调用**
- **零 Token 管理**：自动获取、缓存、刷新 `tenant_access_token`
- **H5 登录开箱即用**：一行构建授权 URL，一行通过 code 获取用户身份
- **组织架构完整拉取**：部门树 + 员工列表，支持自动翻页，直接可写入数据库
- **消息推送简洁可靠**：文本消息、卡片消息一行发送
- **多应用支持**：同一进程中可同时连接多个飞书应用

#### 1.3 非目标（明确不做）

- ❌ 不替代官方 SDK，不自建 HTTP 传输层和 Token 刷新机制
- ❌ 不做事件订阅/回调服务器（属于独立项目）
- ❌ 不做异步版本（v2.0 再考虑）
- ❌ 不做多维表格、日历、审批等（MVP 后按需扩展）
- ❌ 不做 UI/Web 管理界面

---

### 2. 功能需求

#### 2.1 MVP 功能模块总览

```
ylhp-common-feishu-sdk MVP
├── 客户端管理 (Client) ⭐ 基础
│   ├── 工厂函数创建客户端实例
│   ├── 命名实例注册表（支持多应用）
│   └── 默认实例快捷访问
│
├── 认证管理 (Auth) ⭐ 基础
│   ├── Tenant Access Token 获取与缓存
│   └── H5 网页授权登录（OAuth 2.0）
│       ├── 构建授权 URL
│       └── 通过 code 获取 user_info (open_id)
│
├── 组织架构 (Contact) ⭐ 核心
│   ├── 获取子部门列表（含层级关系）
│   ├── 获取部门直属员工列表
│   ├── 获取用户详细信息（open_id, name, avatar）
│   └── 自动翻页迭代器（iter_departments / iter_department_users）
│
└── 消息推送 (Message) ⭐ 核心
    ├── 发送个人消息（通过 open_id）
    ├── 发送群聊消息（通过 chat_id）
    └── 卡片消息构建（interactive）
```

#### 2.2 MVP 功能需求明细

##### 模块零：客户端管理（Client）

| 需求编号 | 功能           | 接口签名                                                     | 验收标准                                                 |
| -------- | -------------- | ------------------------------------------------------------ | -------------------------------------------------------- |
| F-000a   | 创建客户端实例 | `feishu = Feishu(config)` 或 `feishu = Feishu(app_id=..., app_secret=...)` | 支持传入 FeishuConfig 或关键字参数；不传则从环境变量加载 |
| F-000b   | 注册命名实例   | `Feishu.register("app_a", config_a)`                         | 将实例存入全局注册表，可通过名称取回                     |
| F-000c   | 获取命名实例   | `feishu = Feishu.get("app_a")`                               | 从注册表取回已注册的实例；不存在则抛出 FeishuConfigError |
| F-000d   | 默认实例       | `Feishu.register("default", config)` 后 `Feishu.get()`       | `get()` 不传名称时返回 "default" 实例                    |

##### 模块一：认证管理（Auth）

| 需求编号 | 功能                         | 接口签名                                                     | 验收标准                                                     |
| -------- | ---------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| F-001    | Tenant Access Token 自动管理 | 内部自动，开发者无感                                         | Token 自动获取、内存缓存、过期前自动刷新；开发者无需手动调用任何 Token 方法 |
| F-002    | 构建 H5 网页授权 URL         | `feishu.auth.build_authorize_url(redirect_uri, state?) → str` | 返回完整的飞书 OAuth 授权跳转 URL，包含 app_id、redirect_uri、state 参数 |
| F-003    | 通过授权 code 获取用户身份   | `feishu.auth.get_user_info(code) → UserInfo`                 | 输入临时授权码 code，返回 `UserInfo(open_id="ou_xxx", name="张三", ...)` |

##### 模块二：组织架构（Contact）

| 需求编号 | 功能                         | 接口签名                                                     | 验收标准                                                     |
| -------- | ---------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| F-004    | 获取子部门列表（单页）       | `feishu.contacts.list_departments(parent_id?, page_size?, page_token?, fetch_child?) → PageResult[Department]` | 返回子部门列表；支持 fetch_child 递归获取所有后代部门；使用飞书 `/departments/:department_id/children` 接口 |
| F-004a   | 部门列表自动翻页迭代器       | `feishu.contacts.iter_departments(parent_id?, fetch_child?) → Iterator[Department]` | 自动处理分页，逐条产出部门对象                               |
| F-005    | 获取部门直属员工列表（单页） | `feishu.contacts.list_department_users(department_id, page_size?, page_token?) → PageResult[UserInfo]` | 使用飞书 `/users/find_by_department` 接口                    |
| F-005a   | 部门员工自动翻页迭代器       | `feishu.contacts.iter_department_users(department_id) → Iterator[UserInfo]` | 自动处理分页，逐条产出用户对象                               |
| F-006    | 获取用户详细信息             | `feishu.contacts.get_user(user_id, user_id_type?) → UserDetail` | 输入 open_id 或 user_id，返回完整用户信息                    |

##### 模块三：消息推送（Message）

| 需求编号 | 功能             | 接口签名                                                     | 验收标准                                       |
| -------- | ---------------- | ------------------------------------------------------------ | ---------------------------------------------- |
| F-007    | 发送个人文本消息 | `feishu.messages.send_text(open_id, text) → str`             | 通过 open_id 发送文本消息，返回 message_id     |
| F-008    | 发送群聊文本消息 | `feishu.messages.send_text_to_chat(chat_id, text) → str`     | 通过 chat_id 发送群聊文本消息，返回 message_id |
| F-009    | 发送卡片消息     | `feishu.messages.send_card(receive_id, card, receive_id_type?) → str` | 发送 interactive 类型的卡片消息                |
| F-010    | 回复消息         | `feishu.messages.reply_text(message_id, text) → str`         | 在会话中回复指定消息                           |

#### 2.3 MVP 验证清单

```
☐ 能创建多个独立的 Feishu 客户端实例（不同 app_id）
☐ 能通过命名注册表注册和获取客户端实例
☐ 能获取 Tenant Access Token（自动缓存/刷新）
☐ 能构建 H5 网页授权 URL（含 state 参数）
☐ 能通过授权 code 获取用户 open_id
☐ 能获取子部门列表（含层级）
☐ 能通过迭代器自动翻页获取全部子部门
☐ 能获取部门直属员工列表
☐ 能通过迭代器自动翻页获取部门全部员工
☐ 能发送个人文本消息
☐ 能发送卡片消息（interactive）
☐ 重试最终失败时日志包含总重试次数和总耗时
```

#### 2.4 P1 需求（MVP 之后）

| 需求编号 | 功能                        | 优先级 |
| -------- | --------------------------- | ------ |
| F-011    | 发送富文本消息（post 格式） | P1     |
| F-012    | 发送图片消息（自动上传）    | P1     |
| F-013    | 发送文件消息                | P1     |
| F-014    | 批量发送消息                | P1     |
| F-015    | 搜索用户（模糊查询）        | P1     |
| F-016    | 获取用户通过邮箱/手机号     | P1     |
| F-017    | 刷新 user_access_token      | P1     |
| F-018    | 群组管理（创建群/拉人）     | P2     |
| F-019    | 多维表格 CRUD               | P2     |

---

### 3. 非功能需求

| 编号   | 类别     | 要求                                                         |
| ------ | -------- | ------------------------------------------------------------ |
| NF-001 | 性能     | 单次 API 调用端到端延迟 < 2s（网络正常时）                   |
| NF-002 | 可靠性   | 仅对 5xx 和 429 错误自动重试，重试次数和等待时间从实例配置动态读取；认证错误和参数错误不重试；最终失败时记录总重试次数和耗时 |
| NF-003 | 安全性   | 日志中禁止出现完整 Token、app_secret                         |
| NF-004 | 兼容性   | Python >= 3.12                                               |
| NF-005 | 可测试性 | 核心 Service 方法测试覆盖率 >= 80%                           |
| NF-006 | 文档     | README 含 quickstart，每个公共方法有 docstring               |
| NF-007 | 多应用   | 支持同一进程中同时操作多个飞书应用                           |

---

### 4. 技术约束

- **核心依赖**：`lark-oapi >= 1.5.3`（官方 SDK 负责 Token 管理和 HTTP 通信）
- **数据校验**：`pydantic >= 2.12.5`
- **包管理**：`uv`（使用 dependency-groups 管理开发依赖）
- **代码规范**：`ruff >= 0.15.2`
- **测试框架**：`pytest >= 9.0.2`

---

## 第二部分：架构设计文档

### 1. 架构总览

#### 1.1 分层架构图

```
┌─────────────────────────────────────────────────────────────┐
│                     业务调用层（同事的代码）                     │
│                                                             │
│  # 单应用（最简用法）                                         │
│  feishu = Feishu()                                          │
│  feishu.messages.send_text("ou_xxx", "Hello!")              │
│                                                             │
│  # 多应用                                                   │
│  Feishu.register("hr", config_hr)                           │
│  Feishu.register("bot", config_bot)                         │
│  hr = Feishu.get("hr")                                      │
│  bot = Feishu.get("bot")                                    │
│  hr.contacts.iter_departments()                             │
│  bot.messages.send_text("ou_xxx", "来自机器人")               │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│          ylhp-common-feishu-sdk 内部薄封装层                   │
│                                                             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Feishu (Facade — 普通类，非单例)                        │ │
│  │  ├── 每个实例持有独立的 lark.Client + Config              │ │
│  │  │                                                     │ │
│  │  ├── .auth      → AuthService                          │ │
│  │  ├── .contacts  → ContactService                       │ │
│  │  └── .messages  → MessagingService                     │ │
│  │                                                        │ │
│  │  类方法:                                                │ │
│  │  ├── Feishu.register(name, config) → Feishu            │ │
│  │  ├── Feishu.get(name?) → Feishu                        │ │
│  │  └── Feishu.remove(name) → None                        │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌──────────────┐ ┌───────────────┐ ┌───────────────────┐   │
│  │  models.py   │ │ exceptions.py │ │ log.py            │   │
│  │  Pydantic    │ │ 分级异常树     │ │ 标准库 logging     │   │
│  │  参数校验     │ │ + 可重试判定   │ │ 脱敏 Filter        │   │
│  └──────────────┘ └───────────────┘ └───────────────────┘   │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  _retry.py — 从 Service 实例动态读取重试配置            │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│               lark-oapi 官方 SDK (>= 1.5.3)                  │
│  • tenant_access_token 自动获取 & 刷新                        │
│  • HTTP 连接池 & 请求管理 (基于 requests 库)                   │
│  • 飞书协议适配（JSON 转义、分页、Builder 模式）                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                 ┌─────────▼──────────┐
                 │  open.feishu.cn    │
                 └────────────────────┘
```

#### 1.2 飞书 API 与 lark-oapi 方法映射

| SDK 方法                      | 飞书 API 路径                              | lark-oapi 方法                                | Request 类                     |
| ----------------------------- | ------------------------------------------ | --------------------------------------------- | ------------------------------ |
| `list_departments()`          | `GET /contact/v3/departments/:id/children` | `client.contact.v3.department.children()`     | `ChildrenDepartmentRequest`    |
| `list_department_users()`     | `GET /contact/v3/users/find_by_department` | `client.contact.v3.user.find_by_department()` | `FindByDepartmentUserRequest`  |
| `get_user()`                  | `GET /contact/v3/users/:user_id`           | `client.contact.v3.user.get()`                | `GetUserRequest`               |
| `send_text()` / `send_card()` | `POST /im/v1/messages`                     | `client.im.v1.message.create()`               | `CreateMessageRequest`         |
| `reply_text()`                | `POST /im/v1/messages/:message_id/reply`   | `client.im.v1.message.reply()`                | `ReplyMessageRequest`          |
| code → token                  | `POST /authen/v1/oidc/access_token`        | `client.authen.v1.oidc_access_token.create()` | `CreateOidcAccessTokenRequest` |
| token → user_info             | `GET /authen/v1/user_info`                 | `client.authen.v1.user_info.get()`            | `GetUserInfoRequest`           |

#### 1.3 客户端生命周期

```
                 创建方式 1: 直接实例化
                 ┌─────────────────────────────────────┐
                 │  feishu = Feishu()                   │
                 │  feishu = Feishu(config=my_config)    │
                 │  feishu = Feishu(app_id="x", ...)    │
                 │                                     │
                 │  → 独立实例，不进入注册表              │
                 │  → 适合简单场景 / 临时使用             │
                 └─────────────────────────────────────┘

                 创建方式 2: 注册到命名注册表
                 ┌─────────────────────────────────────┐
                 │  Feishu.register("hr", config_hr)    │
                 │  Feishu.register("bot", config_bot)  │
                 │                                     │
                 │  → 实例存入全局注册表                  │
                 │  → 后续通过 Feishu.get("hr") 取回     │
                 │  → 适合多应用 / 全局共享               │
                 └─────────────────────────────────────┘

                 ┌─────────────────────────────────────┐
                 │  注册表 (_registry)                   │
                 │  ┌──────────┬─────────────────────┐ │
                 │  │ "hr"     │ Feishu(config_hr)    │ │
                 │  ├──────────┼─────────────────────┤ │
                 │  │ "bot"    │ Feishu(config_bot)   │ │
                 │  ├──────────┼─────────────────────┤ │
                 │  │ "default"│ Feishu(config_def)   │ │
                 │  └──────────┴─────────────────────┘ │
                 │                                     │
                 │  Feishu.get("hr")     → hr 实例      │
                 │  Feishu.get("bot")    → bot 实例     │
                 │  Feishu.get()         → default 实例 │
                 │  Feishu.remove("bot") → 移除 bot     │
                 └─────────────────────────────────────┘
```

#### 1.4 H5 授权登录数据流

```
用户浏览器              H5 后端               ylhp_common_feishu_sdk          飞书
    │                    │                      │                  │
    │  访问H5页面         │                      │                  │
    │──────────────────>│                      │                  │
    │                    │                      │                  │
    │                    │  build_authorize_url  │                  │
    │                    │  (redirect_uri)       │                  │
    │                    │─────────────────────>│                  │
    │                    │                      │                  │
    │                    │  ← 授权URL            │                  │
    │                    │<─────────────────────│                  │
    │                    │                      │                  │
    │  ← 302 重定向到飞书  │                      │                  │
    │<──────────────────│                      │                  │
    │                    │                      │                  │
    │  用户在飞书中点击授权  │                      │                  │
    │──────────────────────────────────────────────────────────>│
    │                    │                      │                  │
    │  ← 302 回调 redirect_uri?code=xxx&state=yyy               │
    │<─────────────────────────────────────────────────────────│
    │                    │                      │                  │
    │  GET /callback?code=xxx&state=yyy         │                  │
    │──────────────────>│                      │                  │
    │                    │                      │                  │
    │                    │  ① 校验 state 防 CSRF │                  │
    │                    │                      │                  │
    │                    │  get_user_info(code)  │                  │
    │                    │─────────────────────>│                  │
    │                    │                      │                  │
    │                    │                      │ 步骤1: code换     │
    │                    │                      │ user_access_token │
    │                    │                      │ (不重试,code一次性)│
    │                    │                      │────────────────>│
    │                    │                      │                  │
    │                    │                      │ ← token          │
    │                    │                      │<────────────────│
    │                    │                      │                  │
    │                    │                      │ 步骤2: token换    │
    │                    │                      │ 用户信息          │
    │                    │                      │ (可重试,token可复用)│
    │                    │                      │────────────────>│
    │                    │                      │                  │
    │                    │                      │ ← user_info      │
    │                    │                      │<────────────────│
    │                    │                      │                  │
    │                    │  ← UserInfo          │                  │
    │                    │<─────────────────────│                  │
    │                    │                      │                  │
    │  ← 登录成功，设置session                    │                  │
    │<──────────────────│                      │                  │
```

#### 1.5 消息推送数据流

```
业务代码               ylhp_common_feishu_sdk              lark-oapi           飞书服务器
  │                       │                       │                   │
  │  send_text            │                       │                   │
  │  ("ou_xxx", "Hello")  │                       │                   │
  │──────────────────────>│                       │                   │
  │                       │                       │                   │
  │                       │ 1. Pydantic校验        │                   │
  │                       │    失败 → raise        │                   │
  │                       │    (retryable=False    │                   │
  │                       │     立即抛出)           │                   │
  │                       │                       │                   │
  │                       │ 2. json.dumps(         │                   │
  │                       │    {"text":"Hello"})  │                   │
  │                       │                       │                   │
  │                       │ 3. 构造 Builder 请求    │                   │
  │                       │    + 选择性重试         │                   │
  │                       │    (从 self._config    │                   │
  │                       │     动态读取重试参数)    │                   │
  │                       │──────────────────────>│                   │
  │                       │                       │                   │
  │                       │                       │ 自动注入Token       │
  │                       │                       │ (过期则自动刷新)     │
  │                       │                       │──────────────────>│
  │                       │                       │                   │
  │                       │                       │ ← HTTP Response    │
  │                       │                       │<──────────────────│
  │                       │                       │                   │
  │                       │ ← lark Response       │                   │
  │                       │<──────────────────────│                   │
  │                       │                       │                   │
  │                       │ 4. check_response()   │                   │
  │                       │    成功 → 返回data     │                   │
  │                       │    5xx/429 → 重试      │                   │
  │                       │    认证错误 → 直接抛出   │                   │
  │                       │    业务错误 → 直接抛出   │                   │
  │                       │                       │                   │
  │  ← message_id        │                       │                   │
  │<──────────────────────│                       │                   │
```

---

### 2. 项目目录结构

```
ylhp-common-feishu-sdk/
├── pyproject.toml                    # 项目元数据、依赖、工具配置
├── uv.lock                           # 锁定依赖版本
├── README.md                         # quickstart + 使用指南
├── CHANGELOG.md                      # 版本变更记录
├── CLAUDE.md                         # Claude Code 项目规则
├── .env.example                      # 环境变量模板
├── .gitignore
│
├── src/
│   └── ylhp_common_feishu_sdk/
│       ├── __init__.py               # 公共导出: Feishu, 异常类, 模型类, __version__
│       ├── client.py                 # Feishu 主类 (Facade + 工厂 + 命名注册表)
│       ├── config.py                 # FeishuConfig (dataclass + 环境变量)
│       ├── exceptions.py             # 异常体系 (分级 + retryable 属性)
│       ├── log.py                    # 标准库 logging + 脱敏 Filter
│       ├── models.py                 # Pydantic 入参模型 + Pydantic 出参模型（frozen）
│       ├── _retry.py                 # 动态重试装饰器
│       │
│       └── services/
│           ├── __init__.py
│           ├── _base.py              # BaseService 基类
│           ├── auth.py               # AuthService
│           ├── messaging.py          # MessagingService
│           └── contact.py            # ContactService
│
├── tests/
│   ├── conftest.py                   # pytest fixtures
│   ├── test_config.py
│   ├── test_client.py
│   ├── test_exceptions.py
│   ├── test_log.py
│   ├── test_retry.py
│   └── services/
│       ├── test_auth.py
│       ├── test_messaging.py
│       └── test_contact.py
│
└── examples/
    ├── 01_send_text.py               # 发送文本消息（最简用法）
    ├── 02_send_card.py               # 发送卡片消息
    ├── 03_h5_login.py                # H5 网页授权登录流程
    ├── 04_sync_org_structure.py      # 同步组织架构到数据库
    ├── 05_daily_reminder.py          # 日报提醒自动化
    └── 06_multi_app.py               # 多应用场景
```

---

### 3. 核心模块详细设计

#### 3.1 `config.py` — 配置管理

```python
"""
文件: src/ylhp_common_feishu_sdk/config.py
职责: SDK 配置管理

设计决策:
  - 使用 @dataclass(frozen=True) 保证实例创建后不可变
  - 优先使用显式参数，其次从环境变量加载
  - 校验在 __post_init__ 中完成，失败时抛 FeishuConfigError
  - 不使用 Pydantic（config 是内部基础设施，Pydantic 用于 API 入参校验）
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class FeishuConfig:
    """飞书 SDK 配置。

    三种使用方式（优先级从高到低）：
    1. 直接传参: FeishuConfig(app_id="xxx", app_secret="yyy")
    2. 环境变量: FeishuConfig()  # 自动读取 FEISHU_APP_ID 等
    3. 混合: FeishuConfig(app_id="xxx")  # app_secret 从环境变量读取

    Attributes:
        app_id: 飞书应用的 App ID
        app_secret: 飞书应用的 App Secret
        domain: 飞书 API 域名，默认 https://open.feishu.cn（私有化部署时修改）
        log_level: SDK 内部日志级别
        timeout: HTTP 请求超时时间（秒）
        max_retries: 最大重试次数
        retry_wait_seconds: 重试基础等待时间（秒），实际等待 = base * 2^attempt

    Example:
        >>> config = FeishuConfig(app_id="cli_xxx", app_secret="yyy")
        >>> config = FeishuConfig()  # 从 FEISHU_APP_ID / FEISHU_APP_SECRET 环境变量读取
    """

    app_id: str = field(default="")
    app_secret: str = field(default="")
    domain: str = field(default="")
    log_level: str = field(default="")
    timeout: int | None = field(default=None)
    max_retries: int | None = field(default=None)
    retry_wait_seconds: float | None = field(default=None)

    def __post_init__(self) -> None:
        # frozen=True 下修改字段需要用 object.__setattr__
        _set = object.__setattr__

        _set(self, "app_id", self.app_id or os.getenv("FEISHU_APP_ID", ""))
        _set(self, "app_secret", self.app_secret or os.getenv("FEISHU_APP_SECRET", ""))
        _set(
            self,
            "domain",
            self.domain or os.getenv("FEISHU_DOMAIN", "https://open.feishu.cn"),
        )
        _set(
            self,
            "log_level",
            (self.log_level or os.getenv("FEISHU_LOG_LEVEL", "INFO")).upper(),
        )
        _set(
            self,
            "timeout",
            self.timeout if self.timeout is not None else int(os.getenv("FEISHU_TIMEOUT", "10")),
        )
        _set(
            self,
            "max_retries",
            self.max_retries if self.max_retries is not None else int(os.getenv("FEISHU_MAX_RETRIES", "3")),
        )
        _set(
            self,
            "retry_wait_seconds",
            self.retry_wait_seconds if self.retry_wait_seconds is not None
            else float(os.getenv("FEISHU_RETRY_WAIT_SECONDS", "1.0")),
        )

        # 校验
        from .exceptions import FeishuConfigError

        if not self.app_id:
            raise FeishuConfigError(
                "app_id 未配置。请传入参数或设置环境变量 FEISHU_APP_ID。"
            )
        if not self.app_secret:
            raise FeishuConfigError(
                "app_secret 未配置。请传入参数或设置环境变量 FEISHU_APP_SECRET。"
            )
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR"}
        if self.log_level not in valid_levels:
            raise FeishuConfigError(
                f"无效的 log_level: {self.log_level!r}。有效值: {valid_levels}"
            )
```

---

#### 3.2 `exceptions.py` — 异常体系

```python
"""
文件: src/ylhp_common_feishu_sdk/exceptions.py
职责: SDK 统一异常体系

设计决策:
  - 基类 FeishuError 包含 retryable 属性，供重试装饰器判断
  - 按照语义分为: 配置错误、校验错误、认证错误、限流、服务端错误、通用API错误
  - translate_error() 将飞书错误码映射为对应异常类
  - 未知错误码降级为 FeishuAPIError (retryable=False)，并记录 warning 日志
"""
from __future__ import annotations

import logging

logger = logging.getLogger("ylhp_common_feishu_sdk")


class FeishuError(Exception):
    """飞书 SDK 基础异常。

    Attributes:
        retryable: 该异常是否可以通过重试恢复
    """

    retryable: bool = False

    def __init__(self, message: str = "") -> None:
        self.message = message
        super().__init__(message)


class FeishuConfigError(FeishuError):
    """配置错误（缺少必要配置、配置冲突等）。不可重试。"""

    retryable = False


class FeishuValidationError(FeishuError):
    """参数校验错误（Pydantic 校验失败等）。不可重试。

    Attributes:
        field: 校验失败的字段名
        detail: 详细错误信息
    """

    retryable = False

    def __init__(self, field: str, detail: str) -> None:
        self.field = field
        self.detail = detail
        super().__init__(f"参数校验失败: {field} - {detail}")


class FeishuAPIError(FeishuError):
    """飞书 API 通用业务错误。不可重试。

    Attributes:
        code: 飞书错误码
        msg: 飞书错误消息
        log_id: 飞书请求日志 ID（用于向飞书技术支持提交工单）
    """

    retryable = False

    def __init__(self, code: int, msg: str, log_id: str | None = None) -> None:
        self.code = code
        self.msg = msg
        self.log_id = log_id
        super().__init__(f"飞书 API 错误 [{code}]: {msg} (log_id={log_id})")


class FeishuAuthError(FeishuAPIError):
    """认证/授权错误（Token 无效、权限不足、OAuth code 过期等）。不可重试。"""

    retryable = False


class FeishuRateLimitError(FeishuAPIError):
    """请求频率限制（HTTP 429）。可重试。

    Attributes:
        retry_after: 建议等待秒数（从响应头解析，可能为 None）
    """

    retryable = True

    def __init__(
        self,
        code: int,
        msg: str,
        log_id: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(code, msg, log_id)
        self.retry_after = retry_after


class FeishuServerError(FeishuAPIError):
    """飞书服务端错误（5xx 类）。可重试。"""

    retryable = True


# ── 错误码分类集合 ──

_AUTH_CODES: frozenset[int] = frozenset(
    {
        99991660,  # access_token invalid
        99991661,  # access_token expired
        99991662,  # access_token reused
        99991663,  # tenant_access_token invalid
        99991664,  # tenant_access_token expired
        99991665,  # app_access_token invalid
        99991668,  # insufficient scope
        99991669,  # app not available
        10003,     # invalid app_id
        10014,     # app_secret error
    }
)

_RATE_LIMIT_CODES: frozenset[int] = frozenset(
    {
        99991400,  # rate limit
        99991429,  # too many requests
    }
)

_SERVER_ERROR_CODES: frozenset[int] = frozenset(
    {
        99991500,  # internal server error
        99991501,  # service unavailable
        99991502,  # bad gateway
        99991503,  # gateway timeout
        99991504,  # upstream timeout
    }
)


def translate_error(
    code: int, msg: str, log_id: str | None = None
) -> FeishuAPIError:
    """将飞书错误码翻译为语义化异常。

    Args:
        code: 飞书 API 错误码
        msg: 飞书 API 错误消息
        log_id: 请求日志 ID

    Returns:
        对应的异常实例（FeishuAuthError / FeishuRateLimitError /
        FeishuServerError / FeishuAPIError）
    """
    if code in _AUTH_CODES:
        return FeishuAuthError(code, msg, log_id)
    if code in _RATE_LIMIT_CODES:
        return FeishuRateLimitError(code, msg, log_id)
    if code in _SERVER_ERROR_CODES:
        return FeishuServerError(code, msg, log_id)

    # 兜底策略：检查 msg 关键词
    msg_lower = msg.lower() if msg else ""
    if any(kw in msg_lower for kw in ("token", "auth", "permission", "forbidden")):
        return FeishuAuthError(code, msg, log_id)
    if any(kw in msg_lower for kw in ("rate", "limit", "throttl")):
        return FeishuRateLimitError(code, msg, log_id)
    if any(kw in msg_lower for kw in ("internal", "server error", "unavailable")):
        return FeishuServerError(code, msg, log_id)

    # 未知错误码 — 记录 warning 便于后续补充
    logger.warning(
        "未知飞书错误码 %d，降级为 FeishuAPIError (msg=%s, log_id=%s)",
        code,
        msg,
        log_id,
    )
    return FeishuAPIError(code, msg, log_id)
```

---

#### 3.3 `log.py` — 日志与脱敏

```python
"""
文件: src/ylhp_common_feishu_sdk/log.py
职责:
  - SDK 专用 logger（日志冒泡给宿主应用）
  - 日志脱敏 Filter（防止 token/secret 泄露）

设计决策:
  - 使用标准库 logging 的 named logger ("ylhp_common_feishu_sdk")
  - propagate=True（默认），日志自然冒泡给宿主应用的 root logger
  - 添加 NullHandler 防止宿主未配置日志时出现警告
  - SensitiveFilter 挂在 logger 上，日志向上传播前已完成脱敏
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any


class SensitiveFilter(logging.Filter):
    """日志脱敏过滤器。

    匹配并掩码以下敏感信息：
    - JWT token: "eyJ..." → "eyJ***"
    - tenant_access_token: "t-xxx" → "t-***"
    - app_access_token: "a-xxx" → "a-***"
    - App Secret: "app_secret": "xxx" → "app_secret": "***"
    - App ID: "cli_xxx" → "cli_xxx***"（保留前8位）
    - URL code: "?code=xxx" → "?code=***"
    - JSON code: "code": "xxx" → "code": "***"
    - Bearer token: "Bearer xxx" → "Bearer ***"
    """

    # 脱敏规则: (正则模式, 替换字符串或 callable)
    _PATTERNS: list[tuple[re.Pattern[str], str | Callable[[re.Match[str]], str]]] = [
        # 1. JWT 格式 token (user_access_token, refresh_token)
        (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"), "eyJ***"),

        # 2. tenant_access_token (t-前缀 + 至少20字符)
        (re.compile(r"\bt-[A-Za-z0-9_-]{20,}\b"), "t-***"),

        # 3. app_access_token (a-前缀 + 至少20字符)
        (re.compile(r"\ba-[A-Za-z0-9_-]{20,}\b"), "a-***"),

        # 4. App Secret (限定 JSON key 上下文)
        # 匹配: "app_secret": / "client_secret": / "secret": / "app_Secret":
        (
            re.compile(
                r'("(?:app_?secret|client_secret|secret)"\s*:\s*")([A-Za-z0-9_]{8,})(")',
                re.IGNORECASE,
            ),
            r"\1***\3",
        ),

        # 5. App ID (cli_前缀 + 至少16位)
        # 保留前8位用于调试: cli_a879***
        (
            re.compile(r"\bcli_[a-z0-9]{16,}\b"),
            lambda m: f"{m.group()[:8]}***",
        ),

        # 6. URL 中的授权码 code 参数
        (re.compile(r"([?&]code=)[A-Za-z0-9_-]{16,}"), r"\1***"),

        # 7. JSON code 字段 (字符串值，数字 code 不匹配)
        (re.compile(r'("code"\s*:\s*")([A-Za-z0-9_-]{16,})(")'), r"\1***\3"),

        # 8. Bearer Authorization Header (兜底)
        (re.compile(r"(Bearer\s+)\S{20,}", re.IGNORECASE), r"\1***"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """过滤并脱敏日志记录。

        Args:
            record: 日志记录对象

        Returns:
            总是返回 True（允许记录通过），但会修改 record.msg 和 record.args
        """
        # 脱敏 msg
        if isinstance(record.msg, str):
            record.msg = self._mask(record.msg)

        # 脱敏 args (格式化参数)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._mask_value(v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self._mask_value(a) for a in record.args)

        return True

    def _mask(self, text: str) -> str:
        """对字符串应用所有脱敏规则。"""
        for pattern, repl in self._PATTERNS:
            text = pattern.sub(repl, text)
        return text

    def _mask_value(self, value: Any) -> Any:
        """递归脱敏任意值（处理嵌套 dict/list）。"""
        if isinstance(value, str):
            return self._mask(value)
        elif isinstance(value, dict):
            return {k: self._mask_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._mask_value(item) for item in value]
        return value


def setup_sdk_logger(level: str = "INFO") -> logging.Logger:
    """配置 SDK 专用 logger。

    - logger name: "ylhp_common_feishu_sdk"
    - propagate: False（不传播到 root logger）
    - 添加 SensitiveFilter 脱敏
    - 幂等: 多次调用不会重复添加 handler

    Args:
        level: 日志级别（DEBUG / INFO / WARNING / ERROR）

    Returns:
        配置好的 logger 实例
    """
    logger = logging.getLogger("ylhp_common_feishu_sdk")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 幂等：只在没有 NullHandler 时添加
    if not any(isinstance(h, logging.NullHandler) for h in logger.handlers):
        logger.addHandler(logging.NullHandler())

    # 幂等：只在没有 SensitiveFilter 时添加
    if not any(isinstance(f, SensitiveFilter) for f in logger.filters):
        logger.addFilter(SensitiveFilter())

    return logger
```

---

#### 3.4 `models.py` — 数据模型

```python
"""
文件: src/ylhp_common_feishu_sdk/models.py
职责: SDK 全部数据模型

设计决策 — 统一使用 Pydantic:
  - 入参（BaseModel）: 调用 API 前严格校验，校验失败立即报错，不发请求
  - 出参（BaseModel + frozen=True）: 从 API 响应构造，from_attributes=True 直接解析 lark-oapi 对象

为什么出参也用 Pydantic:
  - from_attributes=True 可直接解析 lark-oapi 原生对象，无需手动提取字段
  - extra="ignore" 容忍飞书新增字段，不报错
  - frozen=True 保证不可变且可哈希
  - 统一技术栈，Service 层用 model_validate() 替代散落的 getattr
"""
from __future__ import annotations

import json
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, computed_field, field_validator

# ══════════════════════════════════════════
# 入参模型（Pydantic — 严格校验）
# ══════════════════════════════════════════


class AuthorizeUrlParams(BaseModel):
    """构建授权 URL 的入参。"""

    redirect_uri: str
    state: str = ""

    @field_validator("redirect_uri")
    @classmethod
    def validate_redirect_uri(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            from .exceptions import FeishuValidationError

            raise FeishuValidationError(
                "redirect_uri", "必须以 http:// 或 https:// 开头"
            )
        return v


class AuthCodeRequest(BaseModel):
    """code 换 token 的入参。"""

    code: str

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not v or not v.strip():
            from .exceptions import FeishuValidationError

            raise FeishuValidationError("code", "授权码不能为空")
        return v.strip()


class TextContent(BaseModel):
    """文本消息内容。"""

    text: str

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        if not v or not v.strip():
            from .exceptions import FeishuValidationError

            raise FeishuValidationError("text", "消息文本不能为空")
        return v

    def to_json(self) -> str:
        return json.dumps({"text": self.text}, ensure_ascii=False)


class CardContent(BaseModel):
    """卡片消息内容。"""

    card: dict[str, Any]

    @field_validator("card")
    @classmethod
    def validate_card(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not v:
            from .exceptions import FeishuValidationError

            raise FeishuValidationError("card", "卡片内容不能为空字典")
        return v

    def to_json(self) -> str:
        return json.dumps(self.card, ensure_ascii=False)


class SendMessageRequest(BaseModel):
    """发送消息的统一入参。"""

    receive_id: str
    receive_id_type: str = "open_id"
    msg_type: str
    content: str

    @field_validator("receive_id")
    @classmethod
    def validate_receive_id(cls, v: str) -> str:
        if not v or not v.strip():
            from .exceptions import FeishuValidationError

            raise FeishuValidationError("receive_id", "接收者 ID 不能为空")
        return v.strip()


# ══════════════════════════════════════════
# 出参模型（Pydantic BaseModel — 不可变）
# ══════════════════════════════════════════

# 出参模型统一配置
_OUT_CONFIG = ConfigDict(
    from_attributes=True,  # 直接解析 lark-oapi 原生对象
    extra="ignore",        # 飞书新增字段时静默忽略
    frozen=True,           # 不可变且可哈希
)

T = TypeVar("T")


class UserInfo(BaseModel):
    """用户基本信息（H5 登录返回 / 部门员工列表条目）。"""

    model_config = _OUT_CONFIG
    open_id: str
    name: str
    en_name: str | None = None
    avatar_url: str | None = None
    email: str | None = None
    mobile: str | None = None
    tenant_key: str | None = None
    department_ids: list[str] = []


class UserDetail(BaseModel):
    """用户详细信息（get_user 返回）。"""

    model_config = _OUT_CONFIG
    open_id: str
    name: str
    en_name: str | None = None
    avatar_url: str | None = None
    email: str | None = None
    mobile: str | None = None
    department_ids: list[str] = []
    job_title: str | None = None
    is_activated: bool | None = None
    is_frozen: bool | None = None
    is_resigned: bool | None = None


class Department(BaseModel):
    """部门信息。"""

    model_config = _OUT_CONFIG
    department_id: str
    open_department_id: str
    name: str
    parent_department_id: str | None = None
    leader_user_id: str | None = None
    member_count: int | None = None


class PageResult[T](BaseModel):
    """分页查询结果。

    Attributes:
        items: 当前页的数据列表
        page_token: 下一页的分页标记（无下一页时为 None）
        has_more: 是否还有更多数据
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)
    items: list[T]
    page_token: str | None = None
    has_more: bool = False
```

---

#### 3.5 `_retry.py` — 动态重试装饰器

```python
"""
文件: src/ylhp_common_feishu_sdk/_retry.py
职责: 提供选择性重试装饰器，从 Service 实例动态读取重试配置

设计决策:
  - 不使用 tenacity 库，手动实现保持最小依赖
  - 仅重试 retryable=True 的异常 (FeishuServerError, FeishuRateLimitError)
  - 重试参数从 self._config 动态读取，不同实例可有不同配置
  - 装饰器要求被装饰方法的 self 拥有 _config 属性
    (FeishuConfig 类型，含 max_retries 和 retry_wait_seconds)
  - 最终失败时记录总重试次数和总耗时
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from .exceptions import FeishuError, FeishuRateLimitError

logger = logging.getLogger("ylhp_common_feishu_sdk")

R = TypeVar("R")


def with_retry(func: Callable[..., R]) -> Callable[..., R]:
    """选择性重试装饰器。

    从被装饰方法所在 Service 实例的 self._config 动态读取
    max_retries 和 retry_wait_seconds。

    仅对 retryable=True 的 FeishuError 子类进行重试。
    其他异常（包括 FeishuAuthError、FeishuValidationError、
    FeishuAPIError、Pydantic ValidationError）立即抛出。

    要求:
        被装饰方法的 self 必须拥有 _config 属性（FeishuConfig 类型）。
        所有继承 BaseService 的类均满足此条件。

    Usage:
        class MessagingService(BaseService):
            @with_retry
            def send_text(self, open_id: str, text: str) -> str:
                ...
    """

    @wraps(func)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> R:
        # 从实例动态读取重试配置
        max_retries: int = self._config.max_retries
        base_wait: float = self._config.retry_wait_seconds

        last_exception: Exception | None = None
        start_time = time.monotonic()

        for attempt in range(max_retries + 1):
            try:
                return func(self, *args, **kwargs)
            except FeishuError as e:
                if not e.retryable:
                    raise

                last_exception = e

                if attempt >= max_retries:
                    break

                # 计算等待时间
                if isinstance(e, FeishuRateLimitError) and e.retry_after:
                    wait_time = e.retry_after
                else:
                    wait_time = base_wait * (2**attempt)

                logger.warning(
                    "API 调用失败，准备重试 [%s, attempt=%d/%d, wait=%.1fs, error=%s, code=%s]",
                    func.__name__,
                    attempt + 1,
                    max_retries,
                    wait_time,
                    type(e).__name__,
                    getattr(e, "code", None),
                )
                time.sleep(wait_time)

        # 所有重试耗尽 — 记录统计信息
        elapsed = time.monotonic() - start_time
        logger.error(
            "API 调用最终失败 [%s, 总重试=%d次, 总耗时=%.1fs, 最后错误=%s, code=%s, msg=%s]",
            func.__name__,
            max_retries,
            elapsed,
            type(last_exception).__name__,
            getattr(last_exception, "code", None),
            getattr(last_exception, "msg", None),
        )
        raise last_exception  # type: ignore[misc]

    return wrapper  # type: ignore[return-value]
```

---

#### 3.6 `services/_base.py` — Service 基类

```python
"""
文件: src/ylhp_common_feishu_sdk/services/_base.py
职责: 所有 Service 的基类，提供:
  - lark client 引用
  - FeishuConfig 引用（供 @with_retry 动态读取重试配置）
  - 统一的响应检查和日志记录
"""
from __future__ import annotations

import logging
from typing import Any

import lark_oapi as lark

from ..config import FeishuConfig
from ..exceptions import translate_error

logger = logging.getLogger("ylhp_common_feishu_sdk")


class BaseService:
    """Service 基类。

    所有 Service 继承此类，获得:
    - self._client: lark-oapi 客户端
    - self._config: SDK 配置（供 @with_retry 读取重试参数）
    - self._check_response(): 统一响应检查
    - self._log_call(): 日志记录
    """

    def __init__(self, client: lark.Client, config: FeishuConfig) -> None:
        self._client = client
        self._config = config

    def _check_response(self, resp: Any, operation: str) -> None:
        """检查飞书 API 响应，失败时抛出对应异常。

        Args:
            resp: lark-oapi 响应对象
            operation: 操作名称（日志标识）

        Raises:
            FeishuAuthError / FeishuRateLimitError / FeishuServerError / FeishuAPIError
        """
        get_log_id = getattr(resp, "get_log_id", None)
        log_id = get_log_id() if callable(get_log_id) else None

        if resp.success():
            logger.info("API 调用成功: %s (log_id=%s)", operation, log_id)
            return

        logger.error(
            "API 调用失败: %s code=%s msg=%s (log_id=%s)",
            operation,
            resp.code,
            resp.msg,
            log_id,
        )
        raise translate_error(resp.code, resp.msg, log_id)

    def _log_call(self, operation: str, **kwargs: Any) -> None:
        """记录 API 调用开始。"""
        logger.info("API 调用开始: %s %s", operation, kwargs)
```

---

#### 3.7 `services/auth.py` — 认证与 H5 授权服务

```python
"""
文件: src/ylhp_common_feishu_sdk/services/auth.py
职责: H5 网页授权登录相关接口

覆盖需求:
  F-001: Tenant Access Token 自动管理（由 lark-oapi 内部处理）
  F-002: 构建 H5 网页授权 URL
  F-003: 通过授权 code 获取用户身份

⚠️ 重试策略特殊处理:
  get_user_info 内部分两步，code 是一次性的，不能整体重试。
  步骤1（code→token）不重试，步骤2（token→user_info）单独重试。
"""
from __future__ import annotations

import logging
from urllib.parse import quote_plus

import lark_oapi as lark
from lark_oapi.api.authen.v1 import (
    CreateOidcAccessTokenRequest,
    CreateOidcAccessTokenRequestBody,
    GetUserInfoRequest,
)

from .._retry import with_retry
from ..config import FeishuConfig
from ..models import AuthCodeRequest, AuthorizeUrlParams, UserInfo
from ._base import BaseService

logger = logging.getLogger("ylhp_common_feishu_sdk")


class AuthService(BaseService):
    """H5 网页授权登录服务。

    Usage:
        feishu = Feishu()

        # 1. 构建授权 URL
        url = feishu.auth.build_authorize_url("https://myapp.com/callback", state="random")

        # 2. 用户授权后，在回调中获取用户信息
        user = feishu.auth.get_user_info(code="xxx")
        print(user.open_id, user.name)
    """

    def __init__(self, client: lark.Client, config: FeishuConfig) -> None:
        super().__init__(client, config)

    def build_authorize_url(
        self,
        redirect_uri: str,
        state: str = "",
    ) -> str:
        """构建 H5 网页授权跳转 URL。

        Args:
            redirect_uri: 授权完成后的回调地址，须与飞书后台配置的一致
            state: 自定义状态参数，建议传入随机值用于防 CSRF 攻击

        Returns:
            完整的飞书 OAuth 授权 URL

        Raises:
            FeishuValidationError: redirect_uri 格式不正确

        Note:
            state 参数的生成与校验由业务方负责。

        Example:
            >>> url = feishu.auth.build_authorize_url(
            ...     "https://myapp.com/callback",
            ...     state="random_csrf_token"
            ... )
        """
        params = AuthorizeUrlParams(redirect_uri=redirect_uri, state=state)

        self._log_call("build_authorize_url", redirect_uri=redirect_uri)

        domain = self._config.domain.rstrip("/")
        encoded_uri = quote_plus(params.redirect_uri)
        url = (
            f"{domain}/open-apis/authen/v1/authorize"
            f"?app_id={self._config.app_id}"
            f"&redirect_uri={encoded_uri}"
            f"&response_type=code"
        )
        if params.state:
            url += f"&state={quote_plus(params.state)}"

        return url

    def get_user_info(self, code: str) -> UserInfo:
        """通过授权 code 获取用户身份信息。

        内部分两步:
        1. 用 code 换取 user_access_token（不重试——code 是一次性的）
        2. 用 user_access_token 获取用户详细信息（可重试——token 短期内可复用）

        Args:
            code: 飞书回调时传递的临时授权码（一次性，5 分钟内有效）

        Returns:
            UserInfo 对象，包含 open_id、name 等字段

        Raises:
            FeishuValidationError: code 为空
            FeishuAuthError: code 无效或已过期
            FeishuAPIError: 其他 API 错误

        Example:
            >>> user = feishu.auth.get_user_info("code_from_callback")
            >>> print(user.open_id, user.name)
        """
        auth_req = AuthCodeRequest(code=code)

        self._log_call("get_user_info")

        # 步骤1: code 换 user_access_token（不重试，code 一次性）
        user_access_token = self._exchange_code_for_token(auth_req.code)

        # 步骤2: user_access_token 换用户信息（可重试）
        return self._fetch_user_info(user_access_token)

    def _exchange_code_for_token(self, code: str) -> str:
        """步骤1: 用授权 code 换取 user_access_token。不重试。"""
        token_req = (
            CreateOidcAccessTokenRequest.builder()
            .request_body(
                CreateOidcAccessTokenRequestBody.builder()
                .grant_type("authorization_code")
                .code(code)
                .build()
            )
            .build()
        )

        token_resp = self._client.authen.v1.oidc_access_token.create(token_req)
        self._check_response(token_resp, "exchange_code_for_token")

        return token_resp.data.access_token

    @with_retry
    def _fetch_user_info(self, user_access_token: str) -> UserInfo:
        """步骤2: 用 user_access_token 获取用户信息。可重试。"""
        user_info_req = GetUserInfoRequest.builder().build()

        option = (
            lark.RequestOption.builder()
            .user_access_token(user_access_token)
            .build()
        )

        user_info_resp = self._client.authen.v1.user_info.get(
            user_info_req, option=option
        )
        self._check_response(user_info_resp, "fetch_user_info")

        data = user_info_resp.data
        return UserInfo(
            open_id=data.open_id,
            name=data.name,
            en_name=getattr(data, "en_name", None),
            avatar_url=getattr(data, "avatar_url", None),
            email=getattr(data, "email", None),
            mobile=getattr(data, "mobile", None),
            tenant_key=getattr(data, "tenant_key", None),
        )
```

---

#### 3.8 `services/messaging.py` — 消息服务

```python
"""
文件: src/ylhp_common_feishu_sdk/services/messaging.py
职责: 飞书 IM 消息发送

覆盖需求: F-007 ~ F-010

飞书 API 映射:
  send_text / send_card → POST /im/v1/messages → client.im.v1.message.create()
  reply_text → POST /im/v1/messages/:message_id/reply → client.im.v1.message.reply()
"""
from __future__ import annotations

from typing import Any

from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    ReplyMessageRequest,
    ReplyMessageRequestBody,
)

from .._retry import with_retry
from ..exceptions import FeishuValidationError
from ..models import CardContent, SendMessageRequest, TextContent
from ._base import BaseService


class MessagingService(BaseService):
    """消息发送服务。

    Usage:
        feishu = Feishu()
        feishu.messages.send_text("ou_xxx", "Hello!")
        feishu.messages.send_text_to_chat("oc_xxx", "群公告")
        feishu.messages.send_card("ou_xxx", {"elements": [...]})
    """

    def _send_message(
        self,
        receive_id: str,
        msg_type: str,
        content: str,
        receive_id_type: str,
        operation: str,
    ) -> str:
        """内部通用消息发送方法。"""
        self._log_call(
            operation, receive_id=receive_id, receive_id_type=receive_id_type
        )

        req = (
            CreateMessageRequest.builder()
            .receive_id_type(receive_id_type)
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(receive_id)
                .msg_type(msg_type)
                .content(content)
                .build()
            )
            .build()
        )

        resp = self._client.im.v1.message.create(req)
        self._check_response(resp, operation)
        return resp.data.message_id

    @with_retry
    def send_text(self, open_id: str, text: str) -> str:
        """发送个人文本消息（通过 open_id）。

        Args:
            open_id: 接收者的 open_id
            text: 文本内容

        Returns:
            message_id

        Raises:
            FeishuValidationError: open_id 或 text 为空
            FeishuAuthError: 权限不足
            FeishuServerError: 服务端错误（自动重试）

        Example:
            >>> mid = feishu.messages.send_text("ou_xxx", "Hello!")
            >>> print(f"消息已发送: {mid}")
        """
        content = TextContent(text=text)
        params = SendMessageRequest(
            receive_id=open_id,
            receive_id_type="open_id",
            msg_type="text",
            content=content.to_json(),
        )
        return self._send_message(
            receive_id=params.receive_id,
            msg_type=params.msg_type,
            content=params.content,
            receive_id_type=params.receive_id_type,
            operation="send_text",
        )

    @with_retry
    def send_text_to_chat(self, chat_id: str, text: str) -> str:
        """发送群聊文本消息（通过 chat_id）。

        Args:
            chat_id: 群聊 ID
            text: 文本内容

        Returns:
            message_id

        Example:
            >>> feishu.messages.send_text_to_chat("oc_xxx", "群公告")
        """
        content = TextContent(text=text)
        params = SendMessageRequest(
            receive_id=chat_id,
            receive_id_type="chat_id",
            msg_type="text",
            content=content.to_json(),
        )
        return self._send_message(
            receive_id=params.receive_id,
            msg_type=params.msg_type,
            content=params.content,
            receive_id_type=params.receive_id_type,
            operation="send_text_to_chat",
        )

    @with_retry
    def send_card(
        self,
        receive_id: str,
        card: dict[str, Any],
        receive_id_type: str = "open_id",
    ) -> str:
        """发送交互式卡片消息。

        Args:
            receive_id: 接收者 ID
            card: 卡片 JSON 结构（dict）
            receive_id_type: ID 类型，默认 "open_id"

        Returns:
            message_id

        Raises:
            FeishuValidationError: card 为空字典

        Example:
            >>> card = {"header": {...}, "elements": [...]}
            >>> feishu.messages.send_card("ou_xxx", card)
        """
        card_content = CardContent(card=card)
        params = SendMessageRequest(
            receive_id=receive_id,
            receive_id_type=receive_id_type,
            msg_type="interactive",
            content=card_content.to_json(),
        )
        return self._send_message(
            receive_id=params.receive_id,
            msg_type=params.msg_type,
            content=params.content,
            receive_id_type=params.receive_id_type,
            operation="send_card",
        )

    @with_retry
    def reply_text(self, message_id: str, text: str) -> str:
        """回复指定消息。

        Args:
            message_id: 要回复的消息 ID
            text: 回复文本

        Returns:
            新消息的 message_id

        Example:
            >>> feishu.messages.reply_text("om_xxx", "收到！")
        """
        if not message_id or not message_id.strip():
            raise FeishuValidationError("message_id", "message_id 不能为空")

        content = TextContent(text=text)

        self._log_call("reply_text", message_id=message_id)

        req = (
            ReplyMessageRequest.builder()
            .message_id(message_id)
            .request_body(
                ReplyMessageRequestBody.builder()
                .msg_type("text")
                .content(content.to_json())
                .build()
            )
            .build()
        )

        resp = self._client.im.v1.message.reply(req)
        self._check_response(resp, "reply_text")
        return resp.data.message_id
```

---

#### 3.9 `services/contact.py` — 组织架构服务

```python
"""
文件: src/ylhp_common_feishu_sdk/services/contact.py
职责: 飞书通讯录 / 组织架构相关接口

覆盖需求:
  F-004:  list_departments (获取子部门列表，单页)
  F-004a: iter_departments (自动翻页迭代器)
  F-005:  list_department_users (获取部门直属员工列表，单页)
  F-005a: iter_department_users (自动翻页迭代器)
  F-006:  get_user (获取用户详细信息)

飞书 API 映射:
  list_departments     → GET /contact/v3/departments/:id/children
                         client.contact.v3.department.children(req)
                         ChildrenDepartmentRequest

  list_department_users → GET /contact/v3/users/find_by_department
                          client.contact.v3.user.find_by_department(req)
                          FindByDepartmentUserRequest

  get_user             → GET /contact/v3/users/:user_id
                         client.contact.v3.user.get(req)
                         GetUserRequest

参考文档:
  - 获取子部门列表: https://open.feishu.cn/document/server-docs/contact-v3/department/children
  - 获取部门直属用户列表: https://open.feishu.cn/document/server-docs/contact-v3/user/find_by_department
  - 获取单个用户信息: https://open.feishu.cn/document/server-docs/contact-v3/user/get
"""
from __future__ import annotations

from collections.abc import Iterator

from lark_oapi.api.contact.v3 import (
    ChildrenDepartmentRequest,
    FindByDepartmentUserRequest,
    GetUserRequest,
)

from .._retry import with_retry
from ..exceptions import FeishuValidationError
from ..models import Department, PageResult, UserDetail, UserInfo
from ._base import BaseService


class ContactService(BaseService):
    """组织架构服务。

    提供子部门列表、部门直属员工列表、用户详情三个核心接口。
    每个列表接口均有两个版本:
    - list_xxx: 单页查询，返回 PageResult，适合需要精确控制分页的场景
    - iter_xxx: 自动翻页迭代器，逐条产出，适合全量拉取

    Usage:
        feishu = Feishu()

        # 方式1: 自动翻页（推荐）
        for dept in feishu.contacts.iter_departments():
            print(dept.name)

        # 方式2: 手动翻页
        result = feishu.contacts.list_departments()
        while result.has_more:
            result = feishu.contacts.list_departments(page_token=result.page_token)
    """

    @with_retry
    def list_departments(
        self,
        parent_department_id: str = "0",
        page_size: int = 50,
        page_token: str | None = None,
        fetch_child: bool = False,
    ) -> PageResult[Department]:
        """获取子部门列表（单页）。

        使用飞书 API: GET /contact/v3/departments/:department_id/children
        lark-oapi 方法: client.contact.v3.department.children()

        Args:
            parent_department_id: 父部门 ID，默认 "0" 表示根部门
            page_size: 每页数量，1-50
            page_token: 分页标记

        Returns:
            PageResult[Department]，含 items、page_token、has_more

        Raises:
            FeishuValidationError: page_size 超出范围
            FeishuAuthError: 权限不足（不重试）
            FeishuServerError: 服务端错误（自动重试）

        Example:
            >>> result = feishu.contacts.list_departments()
            >>> for dept in result.items:
            ...     print(dept.name, dept.open_department_id)
        """
        if page_size < 1 or page_size > 50:
            raise FeishuValidationError("page_size", "须在 1-50 之间")

        self._log_call(
            "list_departments",
            parent_department_id=parent_department_id,
        )

        builder = (
            ChildrenDepartmentRequest.builder()
            .department_id(parent_department_id)
            .page_size(page_size)
            .department_id_type("open_department_id")
        )
        if page_token:
            builder = builder.page_token(page_token)

        req = builder.build()
        resp = self._client.contact.v3.department.children(req)
        self._check_response(resp, "list_departments")

        items: list[Department] = []
        if resp.data and resp.data.items:
            for dept in resp.data.items:
                items.append(
                    Department(
                        department_id=dept.department_id,
                        open_department_id=dept.open_department_id,
                        name=dept.name,
                        parent_department_id=getattr(
                            dept, "parent_department_id", None
                        ),
                        leader_user_id=getattr(dept, "leader_user_id", None),
                        member_count=getattr(dept, "member_count", None),
                    )
                )

        return PageResult(
            items=items,
            page_token=getattr(resp.data, "page_token", None),
            has_more=getattr(resp.data, "has_more", False),
        )

    def iter_departments(
        self,
        parent_department_id: str = "0",
        page_size: int = 50,
    ) -> Iterator[Department]:
        """自动翻页获取全部子部门（生成器）。

        内部自动处理分页，调用者无需关心 page_token。
        每页请求均由 list_departments 发出（含重试逻辑）。

        Args:
            parent_department_id: 父部门 ID，默认 "0" 表示根部门
            page_size: 每页数量

        Yields:
            Department 对象

        Example:
            >>> for dept in feishu.contacts.iter_departments():
            ...     print(dept.name, dept.open_department_id)
        """
        page_token: str | None = None
        while True:
            result = self.list_departments(
                parent_department_id=parent_department_id,
                page_size=page_size,
                page_token=page_token,
            )
            yield from result.items
            if not result.has_more:
                break
            page_token = result.page_token

    @with_retry
    def list_department_users(
        self,
        department_id: str,
        page_size: int = 50,
        page_token: str | None = None,
    ) -> PageResult[UserInfo]:
        """获取部门直属员工列表（单页）。

        使用飞书 API: GET /contact/v3/users/find_by_department
        lark-oapi 方法: client.contact.v3.user.find_by_department()

        Args:
            department_id: 部门的 open_department_id
            page_size: 每页数量，1-50
            page_token: 分页标记

        Returns:
            PageResult[UserInfo]

        Raises:
            FeishuValidationError: department_id 为空或 page_size 超出范围

        Example:
            >>> result = feishu.contacts.list_department_users("od_xxx")
            >>> for user in result.items:
            ...     print(user.name, user.open_id)
        """
        if not department_id:
            raise FeishuValidationError("department_id", "不能为空")
        if page_size < 1 or page_size > 50:
            raise FeishuValidationError("page_size", "须在 1-50 之间")

        self._log_call("list_department_users", department_id=department_id)

        builder = (
            ChildrenDepartmentRequest.builder()
            .department_id(parent_department_id)
            .page_size(page_size)
            .fetch_child(fetch_child)
            .department_id_type("open_department_id")
        )
        if page_token:
            builder = builder.page_token(page_token)

        req = builder.build()
        resp = self._client.contact.v3.user.find_by_department(req)
        self._check_response(resp, "list_department_users")

        items: list[UserInfo] = []
        if resp.data and resp.data.items:
            for user in resp.data.items:
                avatar = getattr(user, "avatar", None)
                items.append(
                    UserInfo(
                        open_id=user.open_id,
                        name=user.name,
                        union_id=getattr(user, "union_id", None),
                        employee_no=getattr(user, "employee_no", None),
                        avatar_url=(
                            getattr(avatar, "avatar_72", None) if avatar else None
                        ),
                        email=getattr(user, "email", None),
                        mobile=getattr(user, "mobile", None),
                        department_ids=getattr(user, "department_ids", []),
                    )
                )

        return PageResult(
            items=items,
            page_token=getattr(resp.data, "page_token", None),
            has_more=getattr(resp.data, "has_more", False),
        )

    def iter_department_users(
        self,
        department_id: str,
        page_size: int = 50,
        fetch_child: bool = False,
    ) -> Iterator[UserInfo]:
        """自动翻页获取部门全部直属员工（生成器）。

        Args:
            department_id: 部门的 open_department_id
            page_size: 每页数量

        Yields:
            UserInfo 对象

        Example:
            >>> for user in feishu.contacts.iter_department_users("od_xxx"):
            ...     print(user.name, user.open_id)
        """
        page_token: str | None = None
        while True:
            result = self.list_department_users(
                department_id=department_id,
                page_size=page_size,
                page_token=page_token,
                fetch_child=fetch_child,
            )
            yield from result.items
            if not result.has_more:
                break
            page_token = result.page_token

    @with_retry
    def get_user(
        self,
        user_id: str,
        user_id_type: str = "open_id",
    ) -> UserDetail:
        """获取用户详细信息。

        使用飞书 API: GET /contact/v3/users/:user_id
        lark-oapi 方法: client.contact.v3.user.get()

        Args:
            user_id: 用户 ID
            user_id_type: ID 类型，默认 "open_id"

        Returns:
            UserDetail 对象

        Raises:
            FeishuValidationError: user_id 为空

        Example:
            >>> user = feishu.contacts.get_user("ou_xxx")
            >>> print(user.name, user.is_activated)
        """
        if not user_id:
            raise FeishuValidationError("user_id", "不能为空")

        self._log_call("get_user", user_id=user_id)

        req = (
            GetUserRequest.builder()
            .user_id(user_id)
            .user_id_type(user_id_type)
            .build()
        )

        resp = self._client.contact.v3.user.get(req)
        self._check_response(resp, "get_user")

        user = resp.data.user
        avatar = getattr(user, "avatar", None)
        status = getattr(user, "status", None)

        return UserDetail(
            open_id=user.open_id,
            name=user.name,
            union_id=getattr(user, "union_id", None),
            employee_no=getattr(user, "employee_no", None),
            en_name=getattr(user, "en_name", None),
            avatar_url=getattr(avatar, "avatar_72", None) if avatar else None,
            email=getattr(user, "email", None),
            mobile=getattr(user, "mobile", None),
            department_ids=getattr(user, "department_ids", []),
            job_title=getattr(user, "job_title", None),
            is_activated=(
                getattr(status, "is_activated", None) if status else None
            ),
            is_frozen=getattr(status, "is_frozen", None) if status else None,
            is_resigned=(
                getattr(status, "is_resigned", None) if status else None
            ),
        )
```

---

#### 3.10 `client.py` — 主入口（Facade + 工厂 + 命名注册表）

```python
"""
文件: src/ylhp_common_feishu_sdk/client.py
职责:
  - SDK 唯一公共入口 (Facade)
  - 普通类，每次 Feishu() 创建独立实例
  - 线程安全的命名注册表 (类级别)，支持多应用场景
  - 初始化官方 lark-oapi 客户端
  - 注册各业务 Service

设计决策:
  - 彻底放弃单例模式
  - Feishu() 直接创建实例，简单场景零学习成本
  - Feishu.register() / Feishu.get() 支持多应用全局共享
  - 注册表是可选功能，不强制使用
"""
from __future__ import annotations

import threading
from typing import ClassVar

import lark_oapi as lark

from .config import FeishuConfig
from .exceptions import FeishuConfigError
from .log import setup_sdk_logger
from .services.auth import AuthService
from .services.contact import ContactService
from .services.messaging import MessagingService


class Feishu:
    """飞书 SDK 统一入口。

    普通类（非单例），每次实例化创建独立的客户端。
    可选地通过类级别注册表实现命名实例的全局共享。

    Attributes:
        auth: H5 网页授权登录服务
        messages: 消息发送服务
        contacts: 组织架构服务

    Usage — 单应用（最简）:
        feishu = Feishu()  # 从环境变量加载配置
        feishu.messages.send_text("ou_xxx", "Hello!")

    Usage — 显式配置:
        config = FeishuConfig(app_id="cli_xxx", app_secret="xxx")
        feishu = Feishu(config=config)

    Usage — 多应用:
        Feishu.register("hr", FeishuConfig(app_id="hr_app", app_secret="hr_secret"))
        Feishu.register("bot", FeishuConfig(app_id="bot_app", app_secret="bot_secret"))

        hr = Feishu.get("hr")
        bot = Feishu.get("bot")

        hr.contacts.iter_departments()
        bot.messages.send_text("ou_xxx", "来自机器人")

    Usage — 默认实例:
        Feishu.register("default", config)
        feishu = Feishu.get()  # 等同于 Feishu.get("default")
    """

    # ─── 类级别注册表（线程安全）───
    _registry: ClassVar[dict[str, Feishu]] = {}
    _registry_lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(
        self,
        config: FeishuConfig | None = None,
        *,
        app_id: str = "",
        app_secret: str = "",
        **kwargs: object,
    ) -> None:
        """创建飞书客户端实例。

        三种初始化方式（优先级从高到低）：
        1. 传入 FeishuConfig 对象
        2. 传入关键字参数 (app_id, app_secret, ...)
        3. 从环境变量自动加载

        Args:
            config: 完整配置对象（优先级最高）
            app_id: 飞书 App ID（快捷方式）
            app_secret: 飞书 App Secret（快捷方式）
            **kwargs: 其他 FeishuConfig 支持的参数
        """
        if config is not None:
            self._config = config
        elif app_id:
            self._config = FeishuConfig(
                app_id=app_id, app_secret=app_secret, **kwargs  # type: ignore[arg-type]
            )
        else:
            self._config = FeishuConfig()

        # 1. 日志（SDK 专属 logger，不污染宿主应用）
        setup_sdk_logger(self._config.log_level)

        # 2. 官方 lark-oapi 客户端
        log_level_map = {
            "DEBUG": lark.LogLevel.DEBUG,
            "INFO": lark.LogLevel.INFO,
            "WARNING": lark.LogLevel.WARN,
            "ERROR": lark.LogLevel.ERROR,
        }
        self._lark_client: lark.Client = (
            lark.Client.builder()
            .app_id(self._config.app_id)
            .app_secret(self._config.app_secret)
            .domain(self._config.domain)
            .timeout(self._config.timeout)
            .log_level(
                log_level_map.get(self._config.log_level, lark.LogLevel.INFO)
            )
            .build()
        )

        # 3. 注册 Services（每个 Service 持有 config 引用）
        self.auth = AuthService(self._lark_client, self._config)
        self.messages = MessagingService(self._lark_client, self._config)
        self.contacts = ContactService(self._lark_client, self._config)

    # ─── 命名注册表 API ───

    @classmethod
    def register(cls, name: str, config: FeishuConfig) -> Feishu:
        """创建客户端实例并注册到全局注册表。

        如果同名实例已存在，会抛出错误（防止意外覆盖）。
        若需覆盖，请先 remove() 再 register()。

        Args:
            name: 实例名称（如 "default", "hr", "bot"）
            config: 飞书配置

        Returns:
            创建的 Feishu 实例

        Raises:
            FeishuConfigError: 同名实例已注册

        Example:
            >>> Feishu.register("hr", FeishuConfig(app_id="hr_app", app_secret="xxx"))
            >>> hr = Feishu.get("hr")
        """
        with cls._registry_lock:
            if name in cls._registry:
                existing = cls._registry[name]
                raise FeishuConfigError(
                    f'名为 "{name}" 的实例已注册 '
                    f"(app_id={existing._config.app_id})。"
                    f'若需覆盖，请先调用 Feishu.remove("{name}")。'
                )
            instance = cls(config=config)
            cls._registry[name] = instance
            return instance

    @classmethod
    def get(cls, name: str = "default") -> Feishu:
        """从注册表获取已注册的命名实例。

        Args:
            name: 实例名称，默认 "default"

        Returns:
            已注册的 Feishu 实例

        Raises:
            FeishuConfigError: 实例不存在

        Example:
            >>> feishu = Feishu.get()           # 获取 "default"
            >>> hr = Feishu.get("hr")           # 获取 "hr"
        """
        with cls._registry_lock:
            if name not in cls._registry:
                available = list(cls._registry.keys()) or ["(无)"]
                raise FeishuConfigError(
                    f'未找到名为 "{name}" 的实例。'
                    f"已注册的实例: {', '.join(available)}。"
                    f'请先调用 Feishu.register("{name}", config) 注册。'
                )
            return cls._registry[name]

    @classmethod
    def remove(cls, name: str) -> None:
        """从注册表移除命名实例。

        Args:
            name: 实例名称

        Raises:
            FeishuConfigError: 实例不存在
        """
        with cls._registry_lock:
            if name not in cls._registry:
                raise FeishuConfigError(
                    f'未找到名为 "{name}" 的实例，无法移除。'
                )
            del cls._registry[name]

    @classmethod
    def clear_registry(cls) -> None:
        """清空注册表。仅用于测试。"""
        with cls._registry_lock:
            cls._registry.clear()

    @classmethod
    def registered_names(cls) -> list[str]:
        """返回已注册的所有实例名称。"""
        with cls._registry_lock:
            return list(cls._registry.keys())

    # ─── 底层访问 ───

    @property
    def config(self) -> FeishuConfig:
        """获取当前实例的配置（只读）。"""
        return self._config

    @property
    def lark_client(self) -> lark.Client:
        """获取底层 lark-oapi 客户端（用于访问 SDK 未封装的接口）。"""
        return self._lark_client

    def __repr__(self) -> str:
        return f"Feishu(app_id={self._config.app_id!r})"
```

---

#### 3.11 `__init__.py` — 公共导出

```python
"""
ylhp-common-feishu-sdk — 公司内部飞书 Python SDK

Usage — 最简:
    from ylhp_common_feishu_sdk import Feishu
    feishu = Feishu()
    feishu.messages.send_text("ou_xxx", "Hello!")

Usage — 多应用:
    from ylhp_common_feishu_sdk import Feishu, FeishuConfig
    Feishu.register("hr", FeishuConfig(app_id="hr_app", app_secret="xxx"))
    Feishu.register("bot", FeishuConfig(app_id="bot_app", app_secret="xxx"))
    hr = Feishu.get("hr")
    bot = Feishu.get("bot")
"""
from .client import Feishu
from .config import FeishuConfig
from .exceptions import (
    FeishuAPIError,
    FeishuAuthError,
    FeishuConfigError,
    FeishuError,
    FeishuRateLimitError,
    FeishuServerError,
    FeishuValidationError,
)
from .models import Department, PageResult, UserDetail, UserInfo

__all__ = [
    # 主入口
    "Feishu",
    "FeishuConfig",
    # 异常类
    "FeishuError",
    "FeishuConfigError",
    "FeishuValidationError",
    "FeishuAPIError",
    "FeishuAuthError",
    "FeishuRateLimitError",
    "FeishuServerError",
    # 数据模型
    "UserInfo",
    "UserDetail",
    "Department",
    "PageResult",
]
__version__ = "1.0.0"
```

---

### 4. 测试策略

#### 4.1 测试目录结构

```
tests/
├── conftest.py              # 全局 fixtures
├── test_config.py           # 配置管理测试
├── test_client.py           # 工厂 + 注册表 + 多实例
├── test_exceptions.py       # 异常体系测试
├── test_log.py              # 日志脱敏测试
├── test_retry.py            # 动态重试配置测试
└── services/
    ├── test_auth.py         # 认证授权测试
    ├── test_messaging.py    # 消息发送测试
    └── test_contact.py      # 组织架构测试
```

#### 4.2 `conftest.py`

```python
"""全局测试 fixtures。

Mock 策略: 直接 mock lark.Client 的方法调用返回值，
不拦截 HTTP 层。
"""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, create_autospec

import lark_oapi as lark
import pytest

from ylhp_common_feishu_sdk import Feishu
from ylhp_common_feishu_sdk.config import FeishuConfig


@pytest.fixture(autouse=True)
def clean_registry() -> Generator[None, None, None]:
    """每个测试前后清空注册表。"""
    Feishu.clear_registry()
    yield
    Feishu.clear_registry()


@pytest.fixture()
def test_config() -> FeishuConfig:
    return FeishuConfig(
        app_id="cli_test_000",
        app_secret="test_secret_000",
        log_level="DEBUG",
        timeout=5,
    )


@pytest.fixture()
def another_config() -> FeishuConfig:
    """另一个配置，用于多应用测试。"""
    return FeishuConfig(
        app_id="cli_test_999",
        app_secret="test_secret_999",
        log_level="INFO",
    )


@pytest.fixture()
def mock_lark_client() -> MagicMock:
    """创建 mock 的 lark.Client。"""
    return create_autospec(lark.Client, instance=True)


@pytest.fixture()
def feishu(test_config: FeishuConfig) -> Feishu:
    """创建一个测试用的 Feishu 实例。"""
    return Feishu(config=test_config)


def make_success_response(data: object = None) -> MagicMock:
    """构造模拟的成功响应。"""
    resp = MagicMock()
    resp.success.return_value = True
    resp.code = 0
    resp.msg = "success"
    resp.data = data
    resp.get_log_id.return_value = "test_log_id"
    return resp


def make_error_response(
    code: int, msg: str, log_id: str = "err_log"
) -> MagicMock:
    """构造模拟的错误响应。"""
    resp = MagicMock()
    resp.success.return_value = False
    resp.code = code
    resp.msg = msg
    resp.get_log_id.return_value = log_id
    return resp
```

#### 4.3 完整测试用例表

| 测试文件               | 用例                                           | 验证点                                                    |
| ---------------------- | ---------------------------------------------- | --------------------------------------------------------- |
| **test_client.py**     | `test_create_independent_instances`            | 两次 `Feishu()` 是不同实例                                |
| **test_client.py**     | `test_create_from_kwargs`                      | `Feishu(app_id="x", app_secret="y")` 正常工作             |
| **test_client.py**     | `test_create_from_env`                         | 不传参时从环境变量加载                                    |
| **test_client.py**     | `test_register_and_get`                        | `register` 后 `get` 返回同一实例                          |
| **test_client.py**     | `test_register_duplicate_raises`               | 同名注册两次抛出 `FeishuConfigError`                      |
| **test_client.py**     | `test_get_nonexistent_raises`                  | `get("xxx")` 抛出错误，消息含已注册名称                   |
| **test_client.py**     | `test_get_default`                             | `register("default", config)` 后 `get()` 返回默认实例     |
| **test_client.py**     | `test_remove_and_reregister`                   | `remove` 后可重新 `register`                              |
| **test_client.py**     | `test_remove_nonexistent_raises`               | `remove("xxx")` 抛出错误                                  |
| **test_client.py**     | `test_registered_names`                        | 返回所有已注册名称                                        |
| **test_client.py**     | `test_clear_registry`                          | 清空后 `registered_names()` 为空                          |
| **test_client.py**     | `test_multi_app_isolation`                     | 两个实例操作互不影响                                      |
| **test_client.py**     | `test_thread_safety_register`                  | 10 线程并发注册不同名称                                   |
| **test_client.py**     | `test_services_registered`                     | `feishu.auth`/`.messages`/`.contacts` 均非 None           |
| **test_client.py**     | `test_repr`                                    | `repr(feishu)` 包含 app_id                                |
| **test_client.py**     | `test_config_property`                         | `feishu.config` 返回配置对象                              |
| **test_config.py**     | `test_from_env_vars`                           | 环境变量正确加载                                          |
| **test_config.py**     | `test_explicit_overrides_env`                  | 显式参数覆盖环境变量                                      |
| **test_config.py**     | `test_missing_app_id_raises`                   | 缺少 app_id 抛 FeishuConfigError                          |
| **test_config.py**     | `test_missing_app_secret_raises`               | 缺少 app_secret 抛 FeishuConfigError                      |
| **test_config.py**     | `test_invalid_log_level`                       | 无效 log_level 抛 FeishuConfigError                       |
| **test_config.py**     | `test_frozen_immutable`                        | 创建后不可修改属性                                        |
| **test_config.py**     | `test_default_values`                          | domain、timeout 等默认值正确                              |
| **test_config.py**     | `test_equality_same_values`                    | 相同值的两个 config `==` 为 True                          |
| **test_config.py**     | `test_equality_different_values`               | 不同值的 config `==` 为 False                             |
| **test_exceptions.py** | `test_translate_auth_error`                    | code=99991660 → `FeishuAuthError`                         |
| **test_exceptions.py** | `test_translate_rate_limit`                    | code=99991400 → `FeishuRateLimitError`                    |
| **test_exceptions.py** | `test_translate_server_error`                  | code=99991500 → `FeishuServerError`                       |
| **test_exceptions.py** | `test_translate_generic`                       | 未知 code → `FeishuAPIError`                              |
| **test_exceptions.py** | `test_translate_by_msg_keyword`                | msg 含 "token" → `FeishuAuthError`                        |
| **test_exceptions.py** | `test_log_id_in_message`                       | 异常消息包含 log_id                                       |
| **test_exceptions.py** | `test_retryable_attributes`                    | 各异常类 retryable 值正确                                 |
| **test_exceptions.py** | `test_unknown_code_logs_warning`               | 未知码触发 logger.warning                                 |
| **test_retry.py**      | `test_retry_reads_config_dynamically`          | 不同 config 的实例有不同重试次数                          |
| **test_retry.py**      | `test_retry_on_server_error`                   | `FeishuServerError` 触发重试                              |
| **test_retry.py**      | `test_no_retry_on_auth_error`                  | `FeishuAuthError` 立即抛出                                |
| **test_retry.py**      | `test_no_retry_on_validation_error`            | `FeishuValidationError` 立即抛出                          |
| **test_retry.py**      | `test_no_retry_on_generic_api_error`           | 未知业务错误立即抛出                                      |
| **test_retry.py**      | `test_rate_limit_retry_after`                  | 使用 retry_after 值等待                                   |
| **test_retry.py**      | `test_max_retries_exhausted`                   | 达到最大重试次数后抛出                                    |
| **test_retry.py**      | `test_retry_success_on_second_attempt`         | 第1次失败第2次成功                                        |
| **test_retry.py**      | `test_final_failure_logs_stats`                | 最终失败时日志包含总重试次数和总耗时                      |
| **test_log.py**        | `test_sanitize_bearer_token`                   | `"Bearer xxx"` → `"Bearer ***"`                           |
| **test_log.py**        | `test_sanitize_feishu_token`                   | `"t-abcdefgh"` → `"t-****"`                               |
| **test_log.py**        | `test_sanitize_app_secret`                     | `app_secret` 值被掩码                                     |
| **test_log.py**        | `test_nonsensitive_unchanged`                  | 非敏感字段不被修改                                        |
| **test_log.py**        | `test_sdk_logger_independent`                  | 不影响 root logger                                        |
| **test_log.py**        | `test_setup_idempotent`                        | 多次 setup 不重复添加 handler                             |
| **test_auth.py**       | `test_build_authorize_url_format`              | URL 包含 app_id、redirect_uri、response_type              |
| **test_auth.py**       | `test_build_authorize_url_with_state`          | state 参数正确拼接                                        |
| **test_auth.py**       | `test_build_authorize_url_without_state`       | 不传 state 时 URL 不含 state                              |
| **test_auth.py**       | `test_build_authorize_url_uses_config_domain`  | 使用 config.domain                                        |
| **test_auth.py**       | `test_build_authorize_url_invalid_uri`         | 非 http(s) 触发 ValidationError                           |
| **test_auth.py**       | `test_get_user_info_success`                   | 两步调用成功，返回 UserInfo                               |
| **test_auth.py**       | `test_get_user_info_empty_code`                | 空 code 触发校验错误                                      |
| **test_auth.py**       | `test_get_user_info_invalid_code`              | 无效 code 抛出 AuthError                                  |
| **test_auth.py**       | `test_get_user_info_step1_no_retry`            | 步骤1失败不重试                                           |
| **test_auth.py**       | `test_get_user_info_step2_retries`             | 步骤2失败可重试                                           |
| **test_messaging.py**  | `test_send_text_success`                       | 成功返回 message_id                                       |
| **test_messaging.py**  | `test_send_text_empty_text`                    | 空文本触发校验错误                                        |
| **test_messaging.py**  | `test_send_text_empty_open_id`                 | 空 open_id 触发校验错误                                   |
| **test_messaging.py**  | `test_send_text_to_chat_success`               | receive_id_type 为 "chat_id"                              |
| **test_messaging.py**  | `test_send_card_success`                       | card dict 正确序列化，msg_type 为 "interactive"           |
| **test_messaging.py**  | `test_send_card_empty_dict`                    | 空字典触发 ValidationError                                |
| **test_messaging.py**  | `test_send_card_invalid_receive_id`            | 空 receive_id 触发校验错误                                |
| **test_messaging.py**  | `test_send_text_auth_error_no_retry`           | 认证错误不重试                                            |
| **test_messaging.py**  | `test_send_text_server_error_retries`          | 5xx 触发重试后成功                                        |
| **test_messaging.py**  | `test_reply_text_success`                      | 成功回复                                                  |
| **test_messaging.py**  | `test_reply_text_empty_id`                     | 空 message_id 触发校验错误                                |
| **test_contact.py**    | `test_list_departments_success`                | 返回 PageResult[Department]，使用 `department.children()` |
| **test_contact.py**    | `test_list_departments_pagination`             | has_more=True 时返回 page_token                           |
| **test_contact.py**    | `test_list_departments_empty_result`           | 空列表返回 `PageResult(items=[], has_more=False)`         |
| **test_contact.py**    | `test_list_departments_permission_denied`      | Mock 权限不足错误码，抛出 `FeishuAuthError`               |
| **test_contact.py**    | `test_list_departments_invalid_page_size`      | page_size=100 触发校验错误                                |
| **test_contact.py**    | `test_iter_departments_auto_pagination`        | Mock 3 页数据，迭代器产出全部                             |
| **test_contact.py**    | `test_list_department_users_success`           | 使用 `user.find_by_department()`                          |
| **test_contact.py**    | `test_list_department_users_empty_id`          | 空 department_id 触发校验错误                             |
| **test_contact.py**    | `test_list_department_users_empty_result`      | 空员工列表                                                |
| **test_contact.py**    | `test_list_department_users_permission_denied` | 权限不足                                                  |
| **test_contact.py**    | `test_iter_department_users_auto_pagination`   | 自动翻页                                                  |
| **test_contact.py**    | `test_get_user_success`                        | 返回 UserDetail                                           |
| **test_contact.py**    | `test_get_user_empty_id`                       | 空 user_id 触发校验错误                                   |
| **test_contact.py**    | `test_get_user_not_found`                      | 用户不存在抛出 FeishuAPIError                             |

---

### 5. 工程化配置

#### 5.1 `pyproject.toml`

```toml
[project]
name = "ylhp-common-feishu-sdk"
version = "1.0.0"
description = "公司内部飞书 API Python SDK — 一行代码搞定飞书"
readme = "README.md"
requires-python = ">=3.12"
dependencies = []

[dependency-groups]
dev = [
    "lark-oapi>=1.5.3",
    "pydantic>=2.12.5",
    "pytest>=9.0.2",
    "ruff>=0.15.2",
]

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "SIM", "RUF"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--tb=short -q"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

#### 5.2 `.env.example`

```bash
# 飞书应用凭证（必填）
FEISHU_APP_ID=cli_your_app_id
FEISHU_APP_SECRET=your_app_secret

# 可选配置
FEISHU_DOMAIN=https://open.feishu.cn
FEISHU_LOG_LEVEL=INFO
FEISHU_TIMEOUT=10
FEISHU_MAX_RETRIES=3
FEISHU_RETRY_WAIT_SECONDS=1.0
```

#### 5.3 `.gitignore`

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/

# 虚拟环境
.venv/

# IDE
.idea/
.vscode/
*.swp

# 环境变量
.env

# 测试
.pytest_cache/
htmlcov/
.coverage

# uv
uv.lock
```

---

### 6. 实施计划

| 阶段        | 天数      | 交付内容                                                     | Claude Code 指令                                             |
| ----------- | --------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| **Day 1**   | 第 1 天   | 项目骨架 + config + exceptions + log + models + _retry       | `按照架构文档初始化项目 ylhp-common-feishu-sdk，实现 config.py、exceptions.py、log.py、models.py、_retry.py（注意最终失败的统计日志），编写对应测试` |
| **Day 2**   | 第 2 天   | BaseService + AuthService + MessagingService + 测试          | `实现 services/_base.py、services/auth.py（code 不重试）、services/messaging.py，编写 test_auth.py 和 test_messaging.py，含卡片消息测试` |
| **Day 3**   | 第 3 天   | ContactService + client.py + __init__.py + 全部测试 + README | `实现 services/contact.py（注意使用 ChildrenDepartmentRequest + department.children() 和 FindByDepartmentUserRequest + user.find_by_department()），实现 client.py（工厂+注册表），补充空列表和权限错误测试` |
| **Day 4-5** | 第 4-5 天 | examples + 集成验证 + 文档完善                               | `创建 examples/ 下 6 个示例脚本，验证 MVP 清单全部通过`      |

---

### 7. CLAUDE.md — Claude Code 项目配置

```markdown
# CLAUDE.md

## 项目概述
ylhp-common-feishu-sdk：基于飞书官方 lark-oapi SDK 的薄封装层，
为公司内部提供一行代码调用飞书 API 的能力。
三个 MVP 模块：Auth（H5授权登录）、Contact（组织架构）、Message（消息推送）。
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
```

---

### 8. 使用示例（同事视角）

```python
# ===== examples/01_send_text.py =====
"""日报提醒：发送个人文本消息（最简用法）"""
from ylhp_common_feishu_sdk import Feishu

# 从环境变量加载配置，创建实例
feishu = Feishu()
mid = feishu.messages.send_text("ou_xxx", "请今天完成日报填写 📝")
print(f"消息已发送: {mid}")


# ===== examples/02_send_card.py =====
"""晨会材料推送：发送卡片消息到群"""
from ylhp_common_feishu_sdk import Feishu

feishu = Feishu()
card = {
    "config": {"wide_screen_mode": True},
    "header": {"title": {"content": "📋 今日晨会材料", "tag": "plain_text"}},
    "elements": [
        {
            "tag": "div",
            "text": {
                "content": "1. 昨日进展\n2. 今日计划\n3. 风险事项",
                "tag": "lark_md",
            },
        },
        {
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {"content": "查看详情", "tag": "plain_text"},
                    "url": "https://docs.company.com/daily",
                    "type": "primary",
                }
            ],
        },
    ],
}
feishu.messages.send_card("oc_xxx", card, receive_id_type="chat_id")


# ===== examples/03_h5_login.py =====
"""H5 网页授权登录流程（Flask 示例，含 state CSRF 防护）"""
import secrets

from flask import Flask, redirect, request, session

from ylhp_common_feishu_sdk import Feishu, FeishuAuthError

app = Flask(__name__)
app.secret_key = "your-secret-key"
feishu = Feishu()


@app.route("/login")
def login():
    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state
    url = feishu.auth.build_authorize_url(
        redirect_uri="https://myapp.com/callback",
        state=state,
    )
    return redirect(url)


@app.route("/callback")
def callback():
    # 校验 state 防 CSRF
    returned_state = request.args.get("state", "")
    expected_state = session.pop("oauth_state", "")
    if not returned_state or returned_state != expected_state:
        return "CSRF 校验失败", 403

    code = request.args.get("code")
    if not code:
        return "缺少授权码", 400

    try:
        user = feishu.auth.get_user_info(code)
    except FeishuAuthError as e:
        return f"授权失败: {e.msg}", 401

    session["open_id"] = user.open_id
    session["name"] = user.name
    return f"登录成功！欢迎 {user.name}"


# ===== examples/04_sync_org_structure.py =====
"""同步组织架构到数据库（使用自动翻页迭代器）"""
from ylhp_common_feishu_sdk import Feishu

feishu = Feishu()

# 获取所有顶级部门
all_departments = list(feishu.contacts.iter_departments())
print(f"共 {len(all_departments)} 个部门")

for dept in all_departments:
    print(f"\n部门: {dept.name} ({dept.open_department_id})")

    # 获取部门直属员工
    for user in feishu.contacts.iter_department_users(dept.open_department_id):
        print(f"  {user.name} ({user.open_id})")
        # TODO: db.upsert(user)


# ===== examples/05_daily_reminder.py =====
"""日报漏写提醒"""
from ylhp_common_feishu_sdk import Feishu, FeishuAPIError, FeishuAuthError

feishu = Feishu()

missing_users = [
    {"open_id": "ou_aaa", "name": "张三"},
    {"open_id": "ou_bbb", "name": "李四"},
]

for user in missing_users:
    try:
        feishu.messages.send_text(
            user["open_id"],
            f"⏰ {user['name']}，你今天的日报还没写哦～请尽快完成！",
        )
        print(f"✅ 已提醒 {user['name']}")
    except FeishuAuthError as e:
        print(f"❌ 权限不足: {e.msg}")
    except FeishuAPIError as e:
        print(f"❌ 失败: {e.msg} (log_id={e.log_id})")


# ===== examples/06_multi_app.py =====
"""⭐ 多应用场景：同时操作 HR 系统和机器人"""
from ylhp_common_feishu_sdk import Feishu, FeishuConfig

# 注册多个应用
Feishu.register(
    "hr",
    FeishuConfig(app_id="cli_hr_app_id", app_secret="hr_secret"),
)
Feishu.register(
    "bot",
    FeishuConfig(app_id="cli_bot_app_id", app_secret="bot_secret"),
)

# 获取实例
hr = Feishu.get("hr")
bot = Feishu.get("bot")

# HR 应用：拉取组织架构
for dept in hr.contacts.iter_departments():
    print(f"部门: {dept.name}")
    for user in hr.contacts.iter_department_users(dept.open_department_id):
        print(f"  员工: {user.name}")

# Bot 应用：发送消息
bot.messages.send_text("ou_xxx", "这条消息来自机器人应用 🤖")
bot.messages.send_text_to_chat("oc_xxx", "群消息")

# 查看已注册的应用
print(f"已注册应用: {Feishu.registered_names()}")  # ["hr", "bot"]
```

---

### 9. 变更历史

| 版本   | 主要变更                                                     |
| ------ | ------------------------------------------------------------ |
| v1.1.0 | 初始设计                                                     |
| v1.2.0 | 修复 OAuth code 重试死锁；引入选择性重试；标准库 logging 替换 structlog；dataclass 响应模型；自动翻页迭代器 |
| v1.3.0 | 彻底放弃单例模式，改为工厂 + 命名注册表；`@with_retry` 从 `self._config` 动态读取 |
| v1.4.0 | 修正通讯录 API 方法名（`children` / `find_by_department`）；重试最终失败增加统计日志；补充测试用例；P1 预留 user_access_token 刷新 |

#### 累计已解决问题

| #    | 问题                    | 严重程度 | 解决版本 | 方案                                                  |
| ---- | ----------------------- | -------- | -------- | ----------------------------------------------------- |
| 1    | OAuth code 重试死锁     | 🔴 致命   | v1.2.0   | 拆分两步，步骤1不重试                                 |
| 2    | 无差别重试所有错误      | 🔴 致命   | v1.2.0   | 异常 `retryable` 属性 + 选择性重试                    |
| 3    | 单例传参静默忽略        | 🔴 致命   | v1.3.0   | 彻底放弃单例，改为工厂 + 注册表                       |
| 4    | 单例不支持多应用        | 🟡 架构   | v1.3.0   | 工厂模式 + 命名注册表                                 |
| 5    | 重试参数硬编码          | 🟡 中等   | v1.3.0   | `@with_retry` 从 `self._config` 动态读取              |
| 6    | 通讯录 API 方法名错误   | 🟡 中等   | v1.4.0   | `department.children()` + `user.find_by_department()` |
| 7    | 授权 URL 硬编码域名     | 🟡 中等   | v1.2.0   | 使用 `self._config.domain`                            |
| 8    | structlog 全局副作用    | 🟡 中等   | v1.2.0   | 标准库 logging named logger                           |
| 9    | 返回 dict 无类型提示    | 🟡 中等   | v1.2.0   | dataclass 响应模型                                    |
| 10   | 分页需手动翻页          | 🟡 中等   | v1.2.0   | iter_xxx 自动翻页迭代器                               |
| 11   | 测试 mock HTTP 层不可靠 | 🟡 中等   | v1.2.0   | mock lark.Client 方法层                               |
| 12   | Python 版本不一致       | 🟡 中等   | v1.2.0   | 统一 >=3.12                                           |
| 13   | 重试最终失败缺少统计    | 🟢 低     | v1.4.0   | 记录总重试次数和总耗时                                |
| 14   | 测试用例不足            | 🟢 低     | v1.4.0   | 补充空列表、权限错误、卡片消息测试                    |
| 15   | 错误码粗糙判断          | 🟢 低     | v1.2.0   | 精确码集合 + msg 关键词兜底                           |
| 16   | 示例缺少 state 校验     | 🟢 低     | v1.2.0   | 示例增加完整 CSRF 防护                                |
| 17   | 脱敏保留 token 前缀     | 🟢 低     | v1.2.0   | `Bearer ***` 整体掩码                                 |

---

### 10. 已知限制与后续规划

| 限制                                              | 影响                                           | 计划                                             |
| ------------------------------------------------- | ---------------------------------------------- | ------------------------------------------------ |
| 多进程部署各 worker 独立管理 token                | 可能产生冗余的 token 刷新请求                  | 中低并发影响不大；高并发可考虑 Redis token cache |
| 错误码集合需手动维护                              | 飞书新增错误码时可能漏分类                     | 对未知错误码 log warning，便于后续补充           |
| user_access_token 未缓存/刷新                     | H5 场景每次 code 换取的 token 用完即弃         | P1 实现 refresh_user_token（F-017）              |
| `lark-oapi` 的 `.domain()` 接受字符串尚未完全验证 | 私有化部署可能有问题                           | 实施时在私有化环境中验证                         |

