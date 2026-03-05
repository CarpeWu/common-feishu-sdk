"""ylhp-common-feishu-sdk 公共导出。

基于飞书官方 lark-oapi SDK 的薄封装层。
"""

from __future__ import annotations

__version__ = "0.1.0"

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
from ylhp_common_feishu_sdk.models import PageResult

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
]
