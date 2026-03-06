"""Service 基类。

所有 Service（AuthService、ContactService、MessagingService）的公共基类。
提供:
  - lark.Client 引用（供子类调用官方 SDK）
  - FeishuConfig 引用（供 @with_retry 动态读取重试配置）
  - 统一的响应检查和日志记录
"""

from __future__ import annotations

import logging
from typing import Any

import lark_oapi as lark

from ylhp_common_feishu_sdk.config import FeishuConfig
from ylhp_common_feishu_sdk.exceptions import translate_error

logger = logging.getLogger("ylhp_common_feishu_sdk")


class BaseService:
    """Service 基类。

    所有 Service（AuthService、ContactService、MessagingService）的公共基类。
    提供统一的响应检查和日志记录功能。

    Attributes:
        _client: lark-oapi 客户端实例
        _config: SDK 配置实例

    Example:
        class MessagingService(BaseService):
            def send_text(self, open_id: str, text: str) -> str:
                # 使用 self._client 调用官方 SDK
                # 使用 self._config 获取配置
                ...
    """

    def __init__(self, client: lark.Client, config: FeishuConfig) -> None:
        """初始化 Service。

        Args:
            client: lark-oapi 客户端实例
            config: SDK 配置实例
        """
        self._client = client
        self._config = config

    def _check_response(self, resp: Any, operation: str) -> Any:
        """检查飞书 API 响应，失败时抛出语义化异常。

        Args:
            resp: lark-oapi 响应对象
            operation: 操作名称（用于日志和错误消息）

        Returns:
            原始响应对象（成功时）

        Raises:
            FeishuError: 响应失败时抛出对应的异常
        """
        if resp.success:
            return resp

        # 翻译为语义化异常
        raise translate_error(code=resp.code, msg=resp.msg, log_id=getattr(resp, "log_id", None))

    def _log_call(self, operation: str, **kwargs: Any) -> None:
        """记录 API 调用日志。

        Args:
            operation: 操作名称
            **kwargs: 调用参数（敏感信息会被脱敏）
        """
        logger.debug(f"API 调用: {operation}, 参数: {kwargs}")
