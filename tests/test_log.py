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
        """Bearer token 应该被掩码（20+ 字符）。"""
        flt = SensitiveFilter()
        record = self._create_record("Authorization: Bearer sk-abc123def456ghi789xyz")
        # filter 返回 True 允许记录通过
        assert flt.filter(record) is True
        # 检查消息被脱敏
        assert "Bearer ***" in record.msg
        assert "sk-abc123def456ghi789xyz" not in record.msg

    def test_sanitize_feishu_token(self) -> None:
        """飞书 token (t-xxx) 应该被掩码（20+ 字符）。"""
        flt = SensitiveFilter()
        record = self._create_record("Token: t-abc123def456ghi789xyz0123 used")
        assert flt.filter(record) is True
        assert "t-***" in record.msg
        assert "t-abc123def456ghi789xyz0123" not in record.msg

    def test_sanitize_app_secret(self) -> None:
        """app_secret 值应该被掩码（JSON 上下文）。"""
        flt = SensitiveFilter()
        record = self._create_record('"app_secret": "my_super_secret_value_123"')
        assert flt.filter(record) is True
        assert "***" in record.msg
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


class TestSensitiveFilterExtended:
    """测试 SensitiveFilter 扩展场景。"""

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

    def test_sanitize_multiple_secrets(self) -> None:
        """一条消息包含多个敏感信息。"""
        flt = SensitiveFilter()
        record = self._create_record(
            'Bearer sk-abc123def456ghi789xyz and t-abc123def456ghi789xyz01 and "app_secret": "mysecretpassword"'
        )
        flt.filter(record)
        assert "sk-abc123def456ghi789xyz" not in record.msg
        assert "t-abc123def456ghi789xyz01" not in record.msg
        assert "mysecretpassword" not in record.msg
        assert record.msg.count("***") >= 2  # 至少两个脱敏

    def test_sanitize_nested_json(self) -> None:
        """JSON 字符串中的敏感信息。"""
        flt = SensitiveFilter()
        record = self._create_record('{"token": "Bearer sk-json123abc456def789ghi", "secret": "abc"}')
        flt.filter(record)
        assert "sk-json123abc456def789ghi" not in record.msg

    def test_sanitize_url_params(self) -> None:
        """URL 参数中的 token。"""
        flt = SensitiveFilter()
        record = self._create_record("URL: https://api.com?access_token=t-urltoken123abc456def78")
        flt.filter(record)
        # t- 开头的 token 应该被脱敏
        assert "t-urltoken123abc456def78" not in record.msg

    def test_sanitize_long_token(self) -> None:
        """超长 token 的脱敏。"""
        flt = SensitiveFilter()
        long_token = "t-" + "a" * 100
        record = self._create_record(f"Token: {long_token}")
        flt.filter(record)
        assert long_token not in record.msg
        assert "t-***" in record.msg

    def test_filter_preserves_log_record_attributes(self) -> None:
        """脱敏后 LogRecord 其他属性不变。"""
        flt = SensitiveFilter()
        record = self._create_record("Test message")
        record.levelno = logging.INFO
        record.lineno = 42
        record.funcName = "test_func"

        original_levelno = record.levelno
        original_lineno = record.lineno
        original_func = record.funcName

        flt.filter(record)

        assert record.levelno == original_levelno
        assert record.lineno == original_lineno
        assert record.funcName == original_func

    def test_filter_sanitize_args(self) -> None:
        """脱敏后 args 中的敏感信息被处理。"""
        flt = SensitiveFilter()
        record = self._create_record("Token: %s")
        jwt = "eyJhbGciOiJFUzI1NiJ9.eyJqdGkiOiIxMjMifQ.SflKxwRJS"
        record.args = (jwt,)
        flt.filter(record)
        # args 不再被清空，而是被脱敏
        assert record.args != ()
        assert "eyJ***" in str(record.args)
        assert jwt not in str(record.args)

    def test_concurrent_logging(self) -> None:
        """并发日志脱敏线程安全。"""
        import concurrent.futures

        flt = SensitiveFilter()
        errors: list[Exception] = []

        def log_sensitive(i: int) -> None:
            try:
                for j in range(50):
                    # 使用 20+ 字符的 token 满足新的脱敏规则
                    record = self._create_record(f"Bearer sk-{i}0o{o:03d}-{j}")
                    flt.filter(record)
                    assert f"sk-{i:0{03d}-{j:03d}" not in record.msg
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10):
            list(concurrent.futures.ThreadPoolExecutor(max_workers=10).map(log_sensitive, range(10)))

        assert len(errors) == 0

    def test_sanitize_jwt_token(self) -> None:
        """JWT 格式的 user_access_token 应该被脱敏。"""
        flt = SensitiveFilter()
        jwt = "eyJhbGciOiJFUzI1NiIsImtpZCI6IjEyMyJ9.eyJqdGkiOiIxMjMifQ.SflKxwRJS"
        record = self._create_record(f"Token: {jwt}")
        flt.filter(record)
        assert "eyJ***" in record.msg
        assert jwt not in record.msg

    def test_sanitize_app_access_token(self) -> None:
        """app_access_token (a-前缀) 应该被脱敏。"""
        flt = SensitiveFilter()
        record = self._create_record("Token: a-x9087poiuytrewqlkjhgfdsazxcvbnm12")
        flt.filter(record)
        assert "a-***" in record.msg
        assert "a-x9087poiuytrewqlkjhgfdsazxcvbnm12" not in record.msg

    def test_sanitize_app_id(self) -> None:
        """App ID 应该被部分脱敏（保留前8位）。"""
        flt = SensitiveFilter()
        record = self._create_record("App ID: cli_a879249bcfba100b")
        flt.filter(record)
        assert "cli_a879***" in record.msg
        assert "cli_a879249bcfba100b" not in record.msg

    def test_sanitize_url_code_param(self) -> None:
        """URL 中的 code 参数应该被脱敏。"""
        flt = SensitiveFilter()
        record = self._create_record("URL: http://localhost?code=abcdef1234567890abcd&state=xyz")
        flt.filter(record)
        assert "code=***" in record.msg
        assert "abcdef1234567890abcd" not in record.msg

    def test_sanitize_json_code_field(self) -> None:
        """JSON 中的 code 字符串值应该被脱敏。"""
        flt = SensitiveFilter()
        record = self._create_record('"code": "abcdef1234567890abcdef"')
        flt.filter(record)
        assert '"code": "***"' in record.msg
        assert "abcdef1234567890abcdef" not in record.msg

    def test_no_false_positive_numeric_code(self) -> None:
        """数字类型的 code 不应被脱敏。"""
        flt = SensitiveFilter()
        record = self._create_record('"code": 0')
        flt.filter(record)
        assert '"code": 0' in record.msg

    def test_no_false_positive_short_token(self) -> None:
        """短于最小长度的 token 不应被脱敏。"""
        flt = SensitiveFilter()
        record = self._create_record("Token: t-short")
        flt.filter(record)
        assert "t-short" in record.msg  # 少于20字符，不脱敏

    def test_app_secret_case_insensitive(self) -> None:
        """App Secret 匹配应该大小写不敏感。"""
        flt = SensitiveFilter()
        record = self._create_record('"app_Secret": "mysecretpassword123"')
        flt.filter(record)
        assert "***" in record.msg
        assert "mysecretpassword123" not in record.msg

    def test_sanitize_nested_args_dict(self) -> None:
        """record.args 嵌套字典中的敏感信息应该被递归脱敏。"""
        flt = SensitiveFilter()
        record = self._create_record("请求: %s")
        jwt = "eyJhbGciOiJFUzI1NiJ9.eyJqdGkiOiIxMjMifQ.SflKxwRJS"
        record.args = ({"data": {"token": jwt}},)
        flt.filter(record)
        assert "eyJ***" in str(record.args)
        assert jwt not in str(record.args)

    def test_sanitize_args_dict(self) -> None:
        """record.args 为 dict 时也应该被脱敏。"""
        flt = SensitiveFilter()
        record = self._create_record("Token: %(token)s")
        jwt = "eyJhbGciOiJFUzI1NiJ9.eyJqdGkiOiIxMjMifQ.SflKxwRJS"
        record.args = {"token": jwt}
        flt.filter(record)
        assert "eyJ***" in str(record.args)
        assert jwt not in str(record.args)


class TestSensitiveFilterNewRules:
    """测试新增的脱敏规则。"""

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

    def test_sanitize_app_access_token(self) -> None:
        """app_access_token (a-前缀) 应该被脱敏。"""
        flt = SensitiveFilter()
        record = self._create_record("Token: a-x9087poiuytrewqlkjhgfdsazxcvbnm12")
        flt.filter(record)
        assert "a-***" in record.msg
        assert "a-x9087poiuytrewqlkjhgfdsazxcvbnm12" not in record.msg

    def test_app_secret_case_insensitive(self) -> None:
        """App Secret 匹配应该大小写不敏感。"""
        flt = SensitiveFilter()
        record = self._create_record('"app_Secret": "mysecretpassword123"')
        flt.filter(record)
        assert "***" in record.msg
        assert "mysecretpassword123" not in record.msg

    def test_app_secret_client_secret(self) -> None:
        """client_secret 也应该被脱敏。"""
        flt = SensitiveFilter()
        record = self._create_record('"client_secret": "myclientsecret12345"')
        flt.filter(record)
        assert "***" in record.msg
        assert "myclientsecret12345" not in record.msg
