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
        assert FeishuError("error").retryable is False
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
        # 确保 logger 传播到 caplog
        sdk_logger = logging.getLogger("ylhp_common_feishu_sdk")
        original_propagate = sdk_logger.propagate
        sdk_logger.propagate = True

        try:
            with caplog.at_level(logging.WARNING, logger="ylhp_common_feishu_sdk"):
                err = translate_error(88888, "mystery error", "log_unknown")

            # 应该有一个 warning 日志
            assert len(caplog.records) >= 1
            assert any("未知飞书错误码" in r.message for r in caplog.records)
            # 返回 FeishuAPIError 作为兜底
            assert isinstance(err, FeishuAPIError)
        finally:
            sdk_logger.propagate = original_propagate


class TestExceptionBoundary:
    """测试异常边界情况。"""

    def test_translate_with_none_log_id(self) -> None:
        """log_id=None 时消息格式正确。"""
        err = translate_error(99991660, "auth error", None)
        assert isinstance(err, FeishuAuthError)
        assert err.log_id is None
        msg = str(err)
        assert "log_id=None" in msg

    def test_translate_with_chinese_message(self) -> None:
        """中文错误消息正确处理。"""
        err = translate_error(99991500, "服务器内部错误", "log_cn")
        assert isinstance(err, FeishuServerError)
        assert err.msg == "服务器内部错误"

    def test_translate_empty_response(self) -> None:
        """code/msg 为空时的降级处理。"""
        # msg 为空
        err = translate_error(12345, "", "log_empty")
        assert isinstance(err, FeishuAPIError)
        assert err.msg == ""

        # msg 为 None (传入空字符串会被转为 "")
        err2 = translate_error(99999, "", None)
        assert isinstance(err2, FeishuAPIError)

    def test_feishu_error_str(self) -> None:
        """__str__ 方法返回完整信息。"""
        err = FeishuAPIError(10001, "test error message", "log_str")
        msg = str(err)
        assert "10001" in msg
        assert "test error message" in msg
        assert "log_str" in msg

    def test_feishu_error_repr(self) -> None:
        """__repr__ 方法返回可解析格式。"""
        err = FeishuAPIError(10001, "test", "log_repr")
        repr_str = repr(err)
        assert "FeishuAPIError" in repr_str

    def test_concurrent_translate(self) -> None:
        """并发调用 translate_error 线程安全。"""
        import concurrent.futures

        errors: list[Exception] = []

        def translate_many(i: int) -> None:
            try:
                for j in range(100):
                    err = translate_error(99991660, f"error_{i}_{j}", f"log_{i}_{j}")
                    assert isinstance(err, FeishuAuthError)
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10):
            list(
                concurrent.futures.ThreadPoolExecutor(max_workers=10).map(translate_many, range(10))
            )

        assert len(errors) == 0
