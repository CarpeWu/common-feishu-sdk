"""测试 exceptions 模块。

测试用例覆盖：
- 错误码翻译为对应异常类型
- 消息关键词匹配
- log_id 在异常消息中
- retryable 属性正确性
- 未知错误码触发 warning 日志
"""

from __future__ import annotations

import logging

import pytest

# 这些导入在实现后会成功
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


class TestTranslateError:
    """测试 translate_error 函数。"""

    def test_translate_auth_error(self) -> None:
        """认证错误码应该翻译为 FeishuAuthError。"""
        # code=99991660 是 access_token invalid
        err = translate_error(99991660, "access_token invalid", "log_123")
        assert isinstance(err, FeishuAuthError)
        assert err.code == 99991660
        assert err.msg == "access_token invalid"
        assert err.log_id == "log_123"
        assert err.retryable is False

    def test_translate_rate_limit(self) -> None:
        """限流错误码应该翻译为 FeishuRateLimitError。"""
        # code=99991400 是 rate limit
        err = translate_error(99991400, "rate limit exceeded", "log_456")
        assert isinstance(err, FeishuRateLimitError)
        assert err.code == 99991400
        assert err.msg == "rate limit exceeded"
        assert err.log_id == "log_456"
        assert err.retryable is True

    def test_translate_server_error(self) -> None:
        """服务端错误码应该翻译为 FeishuServerError。"""
        # code=99991500 是 internal server error
        err = translate_error(99991500, "internal server error", "log_789")
        assert isinstance(err, FeishuServerError)
        assert err.code == 99991500
        assert err.msg == "internal server error"
        assert err.log_id == "log_789"
        assert err.retryable is True

    def test_translate_generic(self) -> None:
        """未知错误码应该降级为 FeishuAPIError。"""
        err = translate_error(99999, "unknown error", "log_xxx")
        assert isinstance(err, FeishuAPIError)
        assert err.code == 99999
        assert err.msg == "unknown error"
        assert err.log_id == "log_xxx"
        assert err.retryable is False

    def test_translate_by_msg_keyword_token(self) -> None:
        """消息含 'token' 关键词应该翻译为 FeishuAuthError。"""
        err = translate_error(12345, "token expired", "log_1")
        assert isinstance(err, FeishuAuthError)

    def test_translate_by_msg_keyword_rate(self) -> None:
        """消息含 'rate' 关键词应该翻译为 FeishuRateLimitError。"""
        err = translate_error(12345, "rate limit", "log_2")
        assert isinstance(err, FeishuRateLimitError)

    def test_translate_by_msg_keyword_internal(self) -> None:
        """消息含 'internal' 关键词应该翻译为 FeishuServerError。"""
        err = translate_error(12345, "internal error", "log_3")
        assert isinstance(err, FeishuServerError)


class TestExceptionAttributes:
    """测试异常类属性。"""

    def test_log_id_in_message(self) -> None:
        """异常消息应该包含 log_id。"""
        err = FeishuAPIError(10001, "test error", "log_test")
        msg = str(err)
        assert "log_id=log_test" in msg

    def test_retryable_attributes(self) -> None:
        """各异常类 retryable 值应该正确。"""
        # 不可重试
        assert FeishuError().retryable is False
        assert FeishuConfigError("config error").retryable is False
        assert FeishuValidationError("field", "detail").retryable is False
        assert FeishuAPIError(10001, "msg").retryable is False
        assert FeishuAuthError(10003, "auth error").retryable is False

        # 可重试
        assert FeishuRateLimitError(99991400, "rate limit").retryable is True
        assert FeishuServerError(99991500, "server error").retryable is True

    def test_validation_error_message(self) -> None:
        """FeishuValidationError 消息格式正确。"""
        err = FeishuValidationError("user_id", "不能为空")
        assert err.field == "user_id"
        assert err.detail == "不能为空"
        assert "user_id" in str(err)
        assert "不能为空" in str(err)

    def test_rate_limit_retry_after(self) -> None:
        """FeishuRateLimitError 包含 retry_after 属性。"""
        err = FeishuRateLimitError(99991400, "rate limit", "log_1", retry_after=5.0)
        assert err.retry_after == 5.0

        # 默认为 None
        err2 = FeishuRateLimitError(99991400, "rate limit")
        assert err2.retry_after is None


class TestUnknownCodeWarning:
    """测试未知错误码触发 warning 日志。"""

    def test_unknown_code_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """未知错误码应该触发 logger.warning。"""
        with caplog.at_level(logging.WARNING, logger="ylhp_common_feishu_sdk"):
            err = translate_error(88888, "mystery error", "log_unknown")

        # 应该有一个 warning 日志
        assert len(caplog.records) >= 1
        assert any("未知飞书错误码" in r.message for r in caplog.records)
        # 返回 FeishuAPIError 作为兜底
        assert isinstance(err, FeishuAPIError)
