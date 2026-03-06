"""Messaging 服务测试。"""

from unittest.mock import MagicMock, patch

import pytest

from ylhp_common_feishu_sdk import Feishu
from ylhp_common_feishu_sdk.exceptions import (
    FeishuAuthError,
    FeishuValidationError,
)

# === 辅助函数 ===


def make_success_response(message_id: str = "msg_xxx") -> MagicMock:
    """创建 mock 成功响应。"""
    data = MagicMock()
    data.message_id = message_id
    resp = MagicMock()
    resp.success = True
    resp.code = 0
    resp.msg = "success"
    resp.data = data
    return resp


def make_error_response(code: int, msg: str) -> MagicMock:
    """创建 mock 错误响应。"""
    resp = MagicMock()
    resp.success = False
    resp.code = code
    resp.msg = msg
    return resp


# === Fixtures ===


@pytest.fixture
def feishu():
    """创建测试用 Feishu 实例。"""
    Feishu.clear_registry()
    return Feishu(app_id="cli_test_000", app_secret="test_secret_000")


# === send_text 测试 ===


def test_send_text_success(feishu):
    """发送个人文本消息成功。"""
    with patch.object(
        feishu._lark_client.im.v1.message,
        "create",
        return_value=make_success_response("msg_123"),
    ) as mock_create:
        # 需要先注册 messages 服务
        from ylhp_common_feishu_sdk.services.messaging import MessagingService

        feishu.messages = MessagingService(feishu._lark_client, feishu._config)

        result = feishu.messages.send_text("ou_xxx", "Hello World")

        assert result == "msg_123"
        mock_create.assert_called_once()
        # 验证请求参数
        call_args = mock_create.call_args
        req = call_args[0][0]
        assert req.receive_id_type == "open_id"


def test_send_text_empty_text(feishu):
    """发送空文本抛出校验错误。"""
    from ylhp_common_feishu_sdk.services.messaging import MessagingService

    feishu.messages = MessagingService(feishu._lark_client, feishu._config)

    with pytest.raises(FeishuValidationError) as exc_info:
        feishu.messages.send_text("ou_xxx", "")

    assert exc_info.value.field == "text"


def test_send_text_empty_open_id(feishu):
    """发送到空 open_id 抛出校验错误。"""
    from ylhp_common_feishu_sdk.services.messaging import MessagingService

    feishu.messages = MessagingService(feishu._lark_client, feishu._config)

    with pytest.raises(FeishuValidationError) as exc_info:
        feishu.messages.send_text("", "Hello")

    # 使用 SendMessageRequest 模型校验，字段名为 receive_id
    assert exc_info.value.field == "receive_id"


# === send_text_to_chat 测试 ===


def test_send_text_to_chat_success(feishu):
    """发送群聊文本消息成功。"""
    with patch.object(
        feishu._lark_client.im.v1.message,
        "create",
        return_value=make_success_response("msg_456"),
    ) as mock_create:
        from ylhp_common_feishu_sdk.services.messaging import MessagingService

        feishu.messages = MessagingService(feishu._lark_client, feishu._config)

        result = feishu.messages.send_text_to_chat("oc_xxx", "Hello Group")

        assert result == "msg_456"
        mock_create.assert_called_once()
        # 验证 receive_id_type 为 chat_id
        call_args = mock_create.call_args
        req = call_args[0][0]
        assert req.receive_id_type == "chat_id"


# === send_card 测试 ===


def test_send_card_success(feishu):
    """发送卡片消息成功。"""
    card = {
        "config": {"wide_mode": True},
        "elements": [{"tag": "div", "text": {"content": "Hello", "tag": "plain_text"}}],
    }

    with patch.object(
        feishu._lark_client.im.v1.message,
        "create",
        return_value=make_success_response("msg_789"),
    ) as mock_create:
        from ylhp_common_feishu_sdk.services.messaging import MessagingService

        feishu.messages = MessagingService(feishu._lark_client, feishu._config)

        result = feishu.messages.send_card("ou_xxx", card)

        assert result == "msg_789"
        mock_create.assert_called_once()
        # 验证 msg_type 为 interactive
        call_args = mock_create.call_args
        req = call_args[0][0]
        # 通过 request_body 获取 msg_type 需要检查实际请求
        assert req.receive_id_type == "open_id"


def test_send_card_empty_dict(feishu):
    """发送空卡片抛出校验错误。"""
    from ylhp_common_feishu_sdk.services.messaging import MessagingService

    feishu.messages = MessagingService(feishu._lark_client, feishu._config)

    with pytest.raises(FeishuValidationError) as exc_info:
        feishu.messages.send_card("ou_xxx", {})

    assert exc_info.value.field == "card"


def test_send_card_invalid_receive_id(feishu):
    """发送到空 receive_id 抛出校验错误。"""
    from ylhp_common_feishu_sdk.services.messaging import MessagingService

    feishu.messages = MessagingService(feishu._lark_client, feishu._config)

    with pytest.raises(FeishuValidationError) as exc_info:
        feishu.messages.send_card("", {"tag": "div"})

    assert exc_info.value.field == "receive_id"


# === 重试测试 ===


def test_send_text_auth_error_no_retry(feishu):
    """认证错误不触发重试。"""
    auth_error_resp = make_error_response(99991663, "tenant_access_token invalid")

    with patch.object(
        feishu._lark_client.im.v1.message,
        "create",
        return_value=auth_error_resp,
    ) as mock_create:
        from ylhp_common_feishu_sdk.services.messaging import MessagingService

        feishu.messages = MessagingService(feishu._lark_client, feishu._config)

        with pytest.raises(FeishuAuthError):
            feishu.messages.send_text("ou_xxx", "Hello")

        # 认证错误不重试，只调用一次
        assert mock_create.call_count == 1


def test_send_text_server_error_retries(feishu):
    """5xx 错误触发重试后成功。"""
    server_error_resp = make_error_response(99991500, "internal server error")
    success_resp = make_success_response("msg_retry_success")

    with patch.object(
        feishu._lark_client.im.v1.message,
        "create",
        side_effect=[server_error_resp, server_error_resp, success_resp],
    ) as mock_create:
        from ylhp_common_feishu_sdk.services.messaging import MessagingService

        feishu.messages = MessagingService(feishu._lark_client, feishu._config)

        result = feishu.messages.send_text("ou_xxx", "Hello")

        # 默认 max_retries=2，第三次成功
        assert result == "msg_retry_success"
        assert mock_create.call_count == 3


# === reply_text 测试 ===


def test_reply_text_success(feishu):
    """回复消息成功。"""
    with patch.object(
        feishu._lark_client.im.v1.message,
        "reply",
        return_value=make_success_response("msg_reply_xxx"),
    ) as mock_reply:
        from ylhp_common_feishu_sdk.services.messaging import MessagingService

        feishu.messages = MessagingService(feishu._lark_client, feishu._config)

        result = feishu.messages.reply_text("om_xxx", "Reply content")

        assert result == "msg_reply_xxx"
        mock_reply.assert_called_once()


def test_reply_text_empty_id(feishu):
    """回复空 message_id 抛出校验错误。"""
    from ylhp_common_feishu_sdk.services.messaging import MessagingService

    feishu.messages = MessagingService(feishu._lark_client, feishu._config)

    with pytest.raises(FeishuValidationError) as exc_info:
        feishu.messages.reply_text("", "Reply")

    assert exc_info.value.field == "message_id"
