"""消息发送服务。"""

from __future__ import annotations

from typing import Any

from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    ReplyMessageRequest,
    ReplyMessageRequestBody,
)
from pydantic import ValidationError

from ylhp_common_feishu_sdk._retry import with_retry
from ylhp_common_feishu_sdk.exceptions import FeishuValidationError
from ylhp_common_feishu_sdk.models import (
    CardContent,
    ReplyTextRequest,
    SendMessageRequest,
    TextContent,
)
from ylhp_common_feishu_sdk.services._base import BaseService


class MessagingService(BaseService):
    """消息发送服务。

    提供飞书 IM 消息发送能力，包括：
    - 发送个人文本消息（通过 open_id）
    - 发送群聊文本消息（通过 chat_id）
    - 发送交互式卡片消息
    - 回复指定消息

    所有发送方法都使用 @with_retry 装饰器，对 5xx 和 429 错误自动重试。

    Example:
        >>> feishu = Feishu(app_id="xxx", app_secret="yyy")
        >>> msg_id = feishu.messages.send_text("ou_xxx", "Hello World")
        >>> feishu.messages.reply_text(msg_id, "Reply content")
    """

    def _send_message(
        self,
        receive_id: str,
        msg_type: str,
        content: str,
        receive_id_type: str,
        operation: str,
    ) -> str:
        """内部通用消息发送方法。

        Args:
            receive_id: 接收者 ID（open_id / chat_id / user_id 等）
            msg_type: 消息类型（text / interactive / image 等）
            content: 消息内容（JSON 字符串）
            receive_id_type: 接收者 ID 类型
            operation: 操作名称（用于日志）

        Returns:
            消息 ID

        Raises:
            FeishuAPIError: API 调用失败
        """
        self._log_call(operation, receive_id=receive_id, msg_type=msg_type)

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
            text: 文本消息内容

        Returns:
            消息 ID

        Raises:
            FeishuValidationError: open_id 或 text 为空
            FeishuAuthError: 认证失败（不重试）
            FeishuServerError: 服务端错误（自动重试）
            FeishuRateLimitError: 限流错误（自动重试）

        Example:
            >>> msg_id = feishu.messages.send_text("ou_xxx", "Hello World")
        """
        try:
            # 使用 Pydantic 模型校验
            text_content = TextContent(text=text)
            _ = SendMessageRequest(
                receive_id=open_id,
                msg_type="text",
                content=text_content.to_json(),
            )
        except ValidationError as e:
            # 提取第一个错误字段
            error = e.errors()[0]
            field_name = error.get("loc", ("unknown",))[0]
            message = error.get("msg", "参数校验失败")
            raise FeishuValidationError(str(field_name), message) from e

        return self._send_message(open_id, "text", text_content.to_json(), "open_id", "send_text")

    @with_retry
    def send_text_to_chat(self, chat_id: str, text: str) -> str:
        """发送群聊文本消息（通过 chat_id）。

        Args:
            chat_id: 群聊的 chat_id
            text: 文本消息内容

        Returns:
            消息 ID

        Raises:
            FeishuValidationError: chat_id 或 text 为空
            FeishuAuthError: 认证失败（不重试）
            FeishuServerError: 服务端错误（自动重试）
            FeishuRateLimitError: 限流错误（自动重试）

        Example:
            >>> msg_id = feishu.messages.send_text_to_chat("oc_xxx", "Hello Group")
        """
        try:
            # 使用 Pydantic 模型校验
            text_content = TextContent(text=text)
            _ = SendMessageRequest(
                receive_id=chat_id,
                msg_type="text",
                content=text_content.to_json(),
            )
        except ValidationError as e:
            error = e.errors()[0]
            field_name = error.get("loc", ("unknown",))[0]
            message = error.get("msg", "参数校验失败")
            raise FeishuValidationError(str(field_name), message) from e

        return self._send_message(
            chat_id, "text", text_content.to_json(), "chat_id", "send_text_to_chat"
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
            card: 卡片内容（字典格式，遵循飞书卡片消息协议）
            receive_id_type: 接收者 ID 类型，可选值：
                "open_id"（默认）| "user_id" | "union_id" | "chat_id" | "email"

        Returns:
            消息 ID

        Raises:
            FeishuValidationError: receive_id 为空或 card 为空字典
            FeishuAuthError: 认证失败（不重试）
            FeishuServerError: 服务端错误（自动重试）
            FeishuRateLimitError: 限流错误（自动重试）

        Example:
            >>> card = {"elements": [{"tag": "div", "text": {"content": "Hello"}}]}
            >>> msg_id = feishu.messages.send_card("ou_xxx", card)
        """
        try:
            # 使用 Pydantic 模型校验
            card_content = CardContent(card=card)
            _ = SendMessageRequest(
                receive_id=receive_id,
                msg_type="interactive",
                content=card_content.to_json(),
            )
        except ValidationError as e:
            error = e.errors()[0]
            field_name = error.get("loc", ("unknown",))[0]
            message = error.get("msg", "参数校验失败")
            raise FeishuValidationError(str(field_name), message) from e

        return self._send_message(
            receive_id,
            "interactive",
            card_content.to_json(),
            receive_id_type,
            "send_card",
        )

    @with_retry
    def reply_text(self, message_id: str, text: str) -> str:
        """回复指定消息。

        Args:
            message_id: 被回复消息的 ID
            text: 回复的文本内容

        Returns:
            回复消息的 ID

        Raises:
            FeishuValidationError: message_id 或 text 为空
            FeishuAuthError: 认证失败（不重试）
            FeishuServerError: 服务端错误（自动重试）
            FeishuRateLimitError: 限流错误（自动重试）

        Example:
            >>> reply_id = feishu.messages.reply_text("om_xxx", "Reply content")
        """
        try:
            # 使用 Pydantic 模型校验
            reply_request = ReplyTextRequest(message_id=message_id, text=text)
        except ValidationError as e:
            error = e.errors()[0]
            field_name = error.get("loc", ("unknown",))[0]
            message = error.get("msg", "参数校验失败")
            raise FeishuValidationError(str(field_name), message) from e

        self._log_call("reply_text", message_id=reply_request.message_id)

        req = (
            ReplyMessageRequest.builder()
            .message_id(reply_request.message_id)
            .request_body(
                ReplyMessageRequestBody.builder()
                .msg_type("text")
                .content(reply_request.to_content_json())
                .build()
            )
            .build()
        )

        resp = self._client.im.v1.message.reply(req)
        self._check_response(resp, "reply_text")

        return resp.data.message_id
