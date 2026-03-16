"""ylhp-common-feishu-sdk — 公司内部飞书 API SDK

快速开始::

    from ylhp_common_feishu_sdk import Feishu

    feishu = Feishu(app_id="cli_xxx", app_secret="xxx")

    # 获取部门列表
    result = feishu.contacts.list_departments()
    for dept in result.items:
        print(dept.name, dept.open_department_id)

    # 发送文本消息
    feishu.messages.send_text(open_id="ou_xxx", text="hello")

    # 发送卡片消息
    feishu.messages.send_card(
        receive_id="ou_xxx",
        card={"key": "value"},
        receive_id_type="open_id",
    )

    # H5 网页授权登录
    url = feishu.auth.build_authorize_url(redirect_uri="https://example.com/callback")
    user_info = feishu.auth.get_user_info(code="xxx")

核心模块:
    feishu.auth       — H5 网页授权登录
    feishu.contacts   — 组织架构（部门、员工）
    feishu.messages   — 消息推送（文本、卡片）

异常体系:
    FeishuError           — 基类
    FeishuAuthError       — 认证/权限错误（不重试）
    FeishuValidationError — 参数校验错误（不重试）
    FeishuServerError     — 服务端错误（自动重试）
    FeishuRateLimitError  — 限流错误（自动重试）

完整文档见本包目录下 README.md，或各模块 docstring。
"""

from __future__ import annotations

import os

README_PATH = os.path.join(os.path.dirname(__file__), "README.md")

__version__ = "1.0.1"

from ylhp_common_feishu_sdk.client import Feishu
from ylhp_common_feishu_sdk.config import FeishuConfig
from ylhp_common_feishu_sdk.exceptions import (
    FeishuAPIError,
    FeishuAuthError,
    FeishuConfigError,
    FeishuError,
    FeishuRateLimitError,
    FeishuServerError,
    FeishuValidationError,
    translate_error,
)
from ylhp_common_feishu_sdk.log import SensitiveFilter, setup_sdk_logger
from ylhp_common_feishu_sdk.models import (
    AuthCodeRequest,
    AuthorizeUrlParams,
    CardContent,
    Department,
    PageResult,
    ReplyTextRequest,
    SendMessageRequest,
    TextContent,
    UserApproval,
    UserDetail,
    UserInfo,
)

__all__ = [
    "__version__",
    # Client
    "Feishu",
    # Config
    "FeishuConfig",
    # Exceptions
    "FeishuError",
    "FeishuConfigError",
    "FeishuValidationError",
    "FeishuAPIError",
    "FeishuAuthError",
    "FeishuRateLimitError",
    "FeishuServerError",
    "translate_error",
    # Log
    "SensitiveFilter",
    "setup_sdk_logger",
    # Models
    "PageResult",
    "UserInfo",
    "Department",
    "UserDetail",
    "AuthorizeUrlParams",
    "AuthCodeRequest",
    # Messaging Models
    "TextContent",
    "CardContent",
    "SendMessageRequest",
    "ReplyTextRequest",
    # Attendance Models
    "UserApproval",
]
