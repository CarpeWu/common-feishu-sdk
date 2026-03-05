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
