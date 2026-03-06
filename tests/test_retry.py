"""测试 _retry 模块。

测试用例覆盖:
- 从 config 动态读取重试参数
- 仅对 retryable=True 的异常重试
- 对 retryable=False 的异常不重试
- 指数退避
- FeishuRateLimitError 使用 retry_after
- 最终失败时记录统计信息
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from ylhp_common_feishu_sdk._retry import with_retry
from ylhp_common_feishu_sdk.config import FeishuConfig
from ylhp_common_feishu_sdk.exceptions import (
    FeishuAPIError,
    FeishuAuthError,
    FeishuRateLimitError,
    FeishuServerError,
    FeishuValidationError,
)


class MockService:
    """模拟 Service 类，用于测试 with_retry 装饰器。"""

    def __init__(self, config: FeishuConfig) -> None:
        self._config = config
        self.call_count = 0
        self.call_times: list[float] = []

    @with_retry
    def success_method(self) -> str:
        """成功方法。"""
        self.call_count += 1
        self.call_times.append(time.monotonic())
        return "success"

    @with_retry
    def server_error_method(self) -> str:
        """抛出 FeishuServerError 的方法。"""
        self.call_count += 1
        self.call_times.append(time.monotonic())
        raise FeishuServerError(code=99991500, msg="Internal error", log_id="log123")

    @with_retry
    def auth_error_method(self) -> str:
        """抛出 FeishuAuthError 的方法。"""
        self.call_count += 1
        raise FeishuAuthError(code=99991660, msg="Auth error", log_id="log456")

    @with_retry
    def validation_error_method(self) -> str:
        """抛出 FeishuValidationError 的方法。"""
        self.call_count += 1
        raise FeishuValidationError(field="open_id", detail="不能为空")

    @with_retry
    def api_error_method(self) -> str:
        """抛出 FeishuAPIError 的方法。"""
        self.call_count += 1
        raise FeishuAPIError(code=99991363, msg="API error", log_id="log789")

    @with_retry
    def rate_limit_method(self, retry_after: float | None = None) -> str:
        """抛出 FeishuRateLimitError 的方法。"""
        self.call_count += 1
        self.call_times.append(time.monotonic())
        raise FeishuRateLimitError(
            code=99991400, msg="Rate limit", log_id="log999", retry_after=retry_after
        )

    @with_retry
    def eventually_succeed_method(self, succeed_on_attempt: int = 2) -> str:
        """第 N 次调用才成功的方法。"""
        self.call_count += 1
        self.call_times.append(time.monotonic())
        if self.call_count < succeed_on_attempt:
            raise FeishuServerError(code=99991500, msg="Temporary error", log_id="log000")
        return "eventual_success"


class TestWithRetry:
    """测试 with_retry 装饰器。"""

    def test_success_no_retry(self) -> None:
        """成功调用不需要重试。"""
        config = FeishuConfig(app_id="test", app_secret="secret", max_retries=3)
        service = MockService(config)

        result = service.success_method()

        assert result == "success"
        assert service.call_count == 1

    def test_retry_on_server_error(self) -> None:
        """FeishuServerError 应该触发重试。"""
        config = FeishuConfig(
            app_id="test", app_secret="secret", max_retries=2, retry_wait_seconds=0.01
        )
        service = MockService(config)

        with pytest.raises(FeishuServerError):
            service.server_error_method()

        # 初始调用 + 2 次重试 = 3 次
        assert service.call_count == 3

    def test_no_retry_on_auth_error(self) -> None:
        """FeishuAuthError 不应该重试。"""
        config = FeishuConfig(app_id="test", app_secret="secret", max_retries=3)
        service = MockService(config)

        with pytest.raises(FeishuAuthError):
            service.auth_error_method()

        # 只调用一次，不重试
        assert service.call_count == 1

    def test_no_retry_on_validation_error(self) -> None:
        """FeishuValidationError 不应该重试。"""
        config = FeishuConfig(app_id="test", app_secret="secret", max_retries=3)
        service = MockService(config)

        with pytest.raises(FeishuValidationError):
            service.validation_error_method()

        assert service.call_count == 1

    def test_no_retry_on_generic_api_error(self) -> None:
        """FeishuAPIError 不应该重试。"""
        config = FeishuConfig(app_id="test", app_secret="secret", max_retries=3)
        service = MockService(config)

        with pytest.raises(FeishuAPIError):
            service.api_error_method()

        assert service.call_count == 1

    def test_rate_limit_uses_retry_after(self) -> None:
        """FeishuRateLimitError 应该使用 retry_after 作为等待时间。"""
        config = FeishuConfig(
            app_id="test", app_secret="secret", max_retries=2, retry_wait_seconds=1.0
        )
        service = MockService(config)

        start = time.monotonic()
        with pytest.raises(FeishuRateLimitError):
            service.rate_limit_method(retry_after=0.01)
        elapsed = time.monotonic() - start

        # 应该使用 retry_after=0.01 而不是 base_wait=1.0
        # 3 次调用，每次等待 0.01 秒，总时间应该远小于 1 秒
        assert elapsed < 0.5
        assert service.call_count == 3

    def test_retry_success_on_second_attempt(self) -> None:
        """第二次尝试成功应该返回结果。"""
        config = FeishuConfig(
            app_id="test", app_secret="secret", max_retries=3, retry_wait_seconds=0.01
        )
        service = MockService(config)

        result = service.eventually_succeed_method(succeed_on_attempt=2)

        assert result == "eventual_success"
        assert service.call_count == 2

    def test_max_retries_exhausted(self) -> None:
        """超过最大重试次数后应该抛出异常。"""
        config = FeishuConfig(
            app_id="test", app_secret="secret", max_retries=2, retry_wait_seconds=0.01
        )
        service = MockService(config)

        # succeed_on_attempt=5 意味着需要 5 次才能成功，但 max_retries=2 只允许 3 次
        with pytest.raises(FeishuServerError):
            service.eventually_succeed_method(succeed_on_attempt=5)

        assert service.call_count == 3  # 初始 + 2 次重试

    def test_exponential_backoff(self) -> None:
        """重试应该使用指数退避。"""
        config = FeishuConfig(
            app_id="test", app_secret="secret", max_retries=2, retry_wait_seconds=0.05
        )
        service = MockService(config)

        start = time.monotonic()
        with pytest.raises(FeishuServerError):
            service.server_error_method()
        elapsed = time.monotonic() - start

        # 指数退避: 第1次重试等待 0.05s, 第2次重试等待 0.1s
        # 总等待时间应该约 0.15s
        assert elapsed >= 0.1  # 至少等待 0.05 + 0.1 = 0.15s（允许一些误差）
        assert service.call_count == 3

    def test_final_failure_logs_stats(self) -> None:
        """最终失败时应该记录统计信息。"""
        config = FeishuConfig(
            app_id="test", app_secret="secret", max_retries=2, retry_wait_seconds=0.01
        )
        service = MockService(config)

        with patch("ylhp_common_feishu_sdk._retry.logger") as mock_logger:
            with pytest.raises(FeishuServerError):
                service.server_error_method()

            # 应该记录警告日志，包含重试次数和耗时
            assert mock_logger.warning.called
            warning_call = mock_logger.warning.call_args[0][0]
            assert "重试" in warning_call or "retry" in warning_call.lower()


class TestWithRetryBoundary:
    """测试 with_retry 边界情况。"""

    def test_retry_preserves_function_metadata(self) -> None:
        """保留原函数 __name__, __doc__。"""
        assert MockService.success_method.__name__ == "success_method"
        assert MockService.server_error_method.__name__ == "server_error_method"

    def test_retry_zero_max_retries(self) -> None:
        """max_retries=0 时不重试（只调用一次）。"""
        config = FeishuConfig(
            app_id="test", app_secret="secret", max_retries=0, retry_wait_seconds=0.01
        )
        service = MockService(config)

        with pytest.raises(FeishuServerError):
            service.server_error_method()

        # 只调用一次，不重试
        assert service.call_count == 1

    def test_retry_zero_wait(self) -> None:
        """retry_wait_seconds=0 立即重试。"""
        config = FeishuConfig(
            app_id="test", app_secret="secret", max_retries=2, retry_wait_seconds=0
        )
        service = MockService(config)

        start = time.monotonic()
        with pytest.raises(FeishuServerError):
            service.server_error_method()
        elapsed = time.monotonic() - start

        # 等待时间接近 0
        assert elapsed < 0.1
        assert service.call_count == 3

    def test_retry_different_retryable_exceptions(self) -> None:
        """不同可重试异常 (ServerError vs RateLimitError)。"""
        config = FeishuConfig(
            app_id="test", app_secret="secret", max_retries=2, retry_wait_seconds=0.01
        )
        service = MockService(config)

        # RateLimitError 也是 retryable=True
        with pytest.raises(FeishuRateLimitError):
            service.rate_limit_method(retry_after=0.01)

        assert service.call_count == 3

    def test_retry_preserves_return_type(self) -> None:
        """返回类型正确。"""
        config = FeishuConfig(app_id="test", app_secret="secret", max_retries=3)
        service = MockService(config)

        result = service.success_method()
        assert isinstance(result, str)
        assert result == "success"

    def test_concurrent_retry_calls(self) -> None:
        """并发重试调用独立。"""
        import concurrent.futures

        config = FeishuConfig(
            app_id="test", app_secret="secret", max_retries=2, retry_wait_seconds=0.01
        )

        errors: list[Exception] = []
        results: list[str] = []

        def call_success() -> None:
            try:
                service = MockService(config)
                result = service.eventually_succeed_method(succeed_on_attempt=1)
                results.append(result)
            except Exception as e:
                errors.append(e)

        def call_server_error() -> None:
            try:
                service = MockService(config)
                service.server_error_method()
            except FeishuServerError:
                pass  # Expected
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10):
            futures = []
            for _ in range(5):
                futures.append(
                    concurrent.futures.ThreadPoolExecutor(max_workers=1).submit(call_success)
                )
            for _ in range(5):
                futures.append(
                    concurrent.futures.ThreadPoolExecutor(max_workers=1).submit(call_server_error)
                )

        assert len(errors) == 0
        assert len(results) == 5

    def test_eventually_succeed_different_attempts(self) -> None:
        """不同尝试次数后成功。"""
        config = FeishuConfig(
            app_id="test", app_secret="secret", max_retries=5, retry_wait_seconds=0.01
        )
        service = MockService(config)

        # 第 3 次成功
        result = service.eventually_succeed_method(succeed_on_attempt=3)
        assert result == "eventual_success"
        assert service.call_count == 3

        # 重置
        service2 = MockService(config)
        # 第 5 次成功
        result2 = service2.eventually_succeed_method(succeed_on_attempt=5)
        assert result2 == "eventual_success"
        assert service2.call_count == 5
