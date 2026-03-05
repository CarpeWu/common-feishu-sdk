"""测试 log 模块。

测试用例覆盖:
- 日志脱敏过滤器
- SDK logger 配置
- 幂等性
- 日志级别设置
"""

from __future__ import annotations

import logging

from ylhp_common_feishu_sdk.log import SensitiveFilter, setup_sdk_logger


class TestSensitiveFilter:
    """测试 SensitiveFilter 日志脱敏。"""

    def _create_record(self, msg: str) -> logging.LogRecord:
        """创建测试用的 LogRecord。"""
        return logging.LogRecord(
            name="ylhp_common_feishu_sdk",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg=msg,
            args=(),
            exc_info=None,
        )

    def test_sanitize_bearer_token(self) -> None:
        """Bearer token 应该被掩码。"""
        flt = SensitiveFilter()
        record = self._create_record("Authorization: Bearer sk-abc123def456")
        # filter 返回 True 允许记录通过
        assert flt.filter(record) is True
        # 检查消息被脱敏
        assert "Bearer ***" in record.msg
        assert "sk-abc123def456" not in record.msg

    def test_sanitize_feishu_token(self) -> None:
        """飞书 token (t-xxx) 应该被掩码。"""
        flt = SensitiveFilter()
        record = self._create_record("Token: t-abc123def456ghi789 used")
        assert flt.filter(record) is True
        assert "t-****" in record.msg
        assert "t-abc123def456ghi789" not in record.msg

    def test_sanitize_app_secret(self) -> None:
        """app_secret 值应该被掩码。"""
        flt = SensitiveFilter()
        record = self._create_record("Config: app_secret='my_super_secret_value_123'")
        assert flt.filter(record) is True
        assert "****" in record.msg
        assert "my_super_secret_value_123" not in record.msg

    def test_nonsensitive_unchanged(self) -> None:
        """非敏感字段不应该被修改。"""
        flt = SensitiveFilter()
        original_msg = "Normal log message without sensitive data"
        record = self._create_record(original_msg)
        assert flt.filter(record) is True
        assert record.msg == original_msg


class TestSetupSdkLogger:
    """测试 setup_sdk_logger 函数。"""

    def test_sdk_logger_independent(self) -> None:
        """SDK logger 不应该影响 root logger。"""
        # 清理已有的 handler
        sdk_logger = logging.getLogger("ylhp_common_feishu_sdk")
        sdk_logger.handlers.clear()

        # 设置 SDK logger
        logger = setup_sdk_logger("DEBUG")

        # 检查 propagate 为 False
        assert logger.propagate is False

        # 检查 root logger 不受影响
        root_logger = logging.getLogger()
        # root logger 不应该有 ylhp_common_feishu_sdk 的 handler
        assert all(h not in logger.handlers for h in root_logger.handlers)

    def test_setup_idempotent(self) -> None:
        """多次调用 setup_sdk_logger 不应该重复添加 handler。"""
        # 清理已有的 handler
        sdk_logger = logging.getLogger("ylhp_common_feishu_sdk")
        sdk_logger.handlers.clear()

        # 第一次设置
        logger1 = setup_sdk_logger("INFO")
        handler_count = len(logger1.handlers)

        # 第二次设置
        logger2 = setup_sdk_logger("DEBUG")

        # handler 数量不应该增加
        assert len(logger2.handlers) == handler_count
        assert logger2 is logger1  # 应该返回同一个 logger 实例

    def test_log_level_set(self) -> None:
        """日志级别应该正确设置。"""
        # 清理已有的 handler
        sdk_logger = logging.getLogger("ylhp_common_feishu_sdk")
        sdk_logger.handlers.clear()

        logger = setup_sdk_logger("WARNING")
        assert logger.level == logging.WARNING

        logger = setup_sdk_logger("debug")
        assert logger.level == logging.DEBUG
