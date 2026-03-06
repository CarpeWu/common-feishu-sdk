"""测试 services/_base.py 模块。

测试用例覆盖:
- BaseService 初始化
- _check_response 成功/失败处理
- _log_call 日志记录
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ylhp_common_feishu_sdk.config import FeishuConfig
from ylhp_common_feishu_sdk.exceptions import FeishuAPIError
from ylhp_common_feishu_sdk.services._base import BaseService


class MockBaseService(BaseService):
    """用于测试的 BaseService 子类。"""

    def test_method(self) -> str:
        """测试方法。"""
        self._log_call("test_method", param1="value1", param2="value2")
        return "test_result"


class TestBaseService:
    """测试 BaseService 基类。"""

    def test_init(self) -> None:
        """BaseService 初始化。"""
        config = FeishuConfig(app_id="test_app", app_secret="test_secret")
        client = MagicMock()
        service = MockBaseService(client, config)

        assert service._client is client
        assert service._config is config

    def test_check_response_success(self) -> None:
        """_check_response 成功时不抛出异常。"""
        config = FeishuConfig(app_id="test_app", app_secret="test_secret")
        client = MagicMock()
        service = MockBaseService(client, config)

        # 模拟成功响应
        response = MagicMock()
        response.success = True

        # 应该不抛出异常
        result = service._check_response(response, "test_operation")
        assert result is response

    def test_check_response_failure(self) -> None:
        """_check_response 失败时抛出异常。"""
        config = FeishuConfig(app_id="test_app", app_secret="test_secret")
        client = MagicMock()
        service = MockBaseService(client, config)

        # 模拟失败响应
        response = MagicMock()
        response.success = False
        response.code = 99991363
        response.msg = "Invalid parameter"
        response.request_id = "req_log_123"

        with pytest.raises(FeishuAPIError) as exc_info:
            service._check_response(response, "test_operation")

        assert exc_info.value.code == 99991363
        assert exc_info.value.msg == "Invalid parameter"

    def test_log_call(self) -> None:
        """_log_call 记录日志。"""
        config = FeishuConfig(app_id="test_app", app_secret="test_secret")
        client = MagicMock()
        service = MockBaseService(client, config)

        with patch("ylhp_common_feishu_sdk.services._base.logger") as mock_logger:
            service._log_call("test_operation", param1="value1", param2="value2")

            # 应该记录 debug 日志
            assert mock_logger.debug.called
            call_args = mock_logger.debug.call_args[0][0]
            assert "test_operation" in call_args


class TestBaseServiceBoundary:
    """测试 BaseService 边界情况。"""

    def test_check_response_with_none_log_id(self) -> None:
        """响应 log_id 为 None 时正确处理。"""
        config = FeishuConfig(app_id="test_app", app_secret="test_secret")
        client = MagicMock()
        service = MockBaseService(client, config)

        # 模拟失败响应，log_id 为 None
        response = MagicMock()
        response.success = False
        response.code = 99991363
        response.msg = "Error"
        # 模拟 getattr 返回 None
        with patch("ylhp_common_feishu_sdk.services._base.getattr") as mock_getattr:
            mock_getattr.return_value = None
            with pytest.raises(FeishuAPIError) as exc_info:
                service._check_response(response, "test_operation")

    def test_log_call_with_no_params(self) -> None:
        """无参数调用 _log_call。"""
        config = FeishuConfig(app_id="test_app", app_secret="test_secret")
        client = MagicMock()
        service = MockBaseService(client, config)

        with patch("ylhp_common_feishu_sdk.services._base.logger") as mock_logger:
            service._log_call("empty_operation")

            assert mock_logger.debug.called
            call_args = mock_logger.debug.call_args[0][0]
            assert "empty_operation" in call_args

    def test_service_has_client_reference(self) -> None:
        """_client 引用正确。"""
        config = FeishuConfig(app_id="test_app", app_secret="test_secret")
        client = MagicMock()
        service = MockBaseService(client, config)

        assert service._client is client

    def test_service_has_config_reference(self) -> None:
        """_config 引用正确。"""
        config = FeishuConfig(app_id="test_app", app_secret="test_secret")
        client = MagicMock()
        service = MockBaseService(client, config)

        assert service._config is config

    def test_subclass_can_add_methods(self) -> None:
        """子类可以添加新方法。"""

        class ExtendedService(BaseService):
            def custom_operation(self, value: str) -> str:
                self._log_call("custom_operation", value=value)
                return f"processed: {value}"

        config = FeishuConfig(app_id="test_app", app_secret="test_secret")
        client = MagicMock()
        service = ExtendedService(client, config)

        result = service.custom_operation("test")
        assert result == "processed: test"

    def test_multiple_services_independent(self) -> None:
        """多个 Service 实例相互独立。"""

        class CounterService(BaseService):
            def __init__(self, client: MagicMock, config: FeishuConfig) -> None:
                super().__init__(client, config)
                self.counter = 0

            def increment(self) -> int:
                self.counter += 1
                return self.counter

        config = FeishuConfig(app_id="test_app", app_secret="test_secret")
        client = MagicMock()

        service1 = CounterService(client, config)
        service2 = CounterService(client, config)

        service1.increment()
        service1.increment()
        service2.increment()

        assert service1.counter == 2
        assert service2.counter == 1
