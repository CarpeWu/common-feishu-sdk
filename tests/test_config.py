"""测试 config 模块。

测试用例覆盖:
- 环境变量加载
- 显式参数覆盖环境变量
- 必填字段校验
- 不可变性 (frozen)
- 默认值
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from ylhp_common_feishu_sdk.config import FeishuConfig


class TestFeishuConfigFromEnv:
    """测试从环境变量加载配置。"""

    def test_load_from_env_vars(self) -> None:
        """应该从环境变量加载配置。"""
        env = {
            "FEISHU_APP_ID": "cli_test_001",
            "FEISHU_APP_SECRET": "test_secret_001",
            "FEISHU_LOG_LEVEL": "DEBUG",
        }
        with patch.dict(os.environ, env, clear=False):
            # 清除可能存在的其他 FEISHU_ 变量
            config = FeishuConfig()
            assert config.app_id == "cli_test_001"
            assert config.app_secret == "test_secret_001"
            assert config.log_level == "DEBUG"

    def test_default_values(self) -> None:
        """默认值应该正确。"""
        env = {
            "FEISHU_APP_ID": "cli_test",
            "FEISHU_APP_SECRET": "secret",
        }
        with patch.dict(os.environ, env, clear=False):
            config = FeishuConfig()
            assert config.domain == "https://open.feishu.cn"
            assert config.log_level == "INFO"
            assert config.timeout == 10
            assert config.max_retries == 3
            assert config.retry_wait_seconds == 1.0


class TestFeishuConfigExplicit:
    """测试显式参数。"""

    def test_explicit_params_override_env(self) -> None:
        """显式参数应该覆盖环境变量。"""
        env = {
            "FEISHU_APP_ID": "env_app_id",
            "FEISHU_APP_SECRET": "env_secret",
            "FEISHU_LOG_LEVEL": "DEBUG",
        }
        with patch.dict(os.environ, env, clear=False):
            config = FeishuConfig(
                app_id="explicit_app_id",
                app_secret="explicit_secret",
                log_level="WARNING",
            )
            assert config.app_id == "explicit_app_id"
            assert config.app_secret == "explicit_secret"
            assert config.log_level == "WARNING"

    def test_partial_explicit_params(self) -> None:
        """部分显式参数，其余从环境变量加载。"""
        env = {
            "FEISHU_APP_SECRET": "env_secret",
        }
        with patch.dict(os.environ, env, clear=False):
            config = FeishuConfig(app_id="explicit_app_id")
            assert config.app_id == "explicit_app_id"
            assert config.app_secret == "env_secret"


class TestFeishuConfigValidation:
    """测试配置校验。"""

    def test_missing_app_id_raises(self) -> None:
        """缺少 app_id 应该抛出 FeishuConfigError。"""
        from ylhp_common_feishu_sdk.exceptions import FeishuConfigError

        env = {"FEISHU_APP_SECRET": "secret"}
        with patch.dict(os.environ, env, clear=False):
            # 移除可能存在的 FEISHU_APP_ID
            os.environ.pop("FEISHU_APP_ID", None)
            with pytest.raises(FeishuConfigError, match="app_id"):
                FeishuConfig()

    def test_missing_app_secret_raises(self) -> None:
        """缺少 app_secret 应该抛出 FeishuConfigError。"""
        from ylhp_common_feishu_sdk.exceptions import FeishuConfigError

        env = {"FEISHU_APP_ID": "cli_test"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("FEISHU_APP_SECRET", None)
            with pytest.raises(FeishuConfigError, match="app_secret"):
                FeishuConfig()

    def test_invalid_log_level_raises(self) -> None:
        """无效的 log_level 应该抛出 FeishuConfigError。"""
        from ylhp_common_feishu_sdk.exceptions import FeishuConfigError

        with pytest.raises(FeishuConfigError, match="log_level"):
            FeishuConfig(
                app_id="test",
                app_secret="secret",
                log_level="INVALID",  # type: ignore[arg-type]
            )


class TestFeishuConfigImmutable:
    """测试配置不可变性。"""

    def test_frozen_immutable(self) -> None:
        """frozen=True 应该禁止修改属性。"""
        config = FeishuConfig(app_id="test", app_secret="secret")
        with pytest.raises((AttributeError, TypeError)):
            config.app_id = "new_value"  # type: ignore[misc]

    def test_frozen_immutable_other_field(self) -> None:
        """其他字段也不应该能修改。"""
        config = FeishuConfig(app_id="test", app_secret="secret")
        with pytest.raises((AttributeError, TypeError)):
            config.log_level = "DEBUG"  # type: ignore[misc]


class TestFeishuConfigBoundary:
    """测试配置边界情况。"""

    def test_config_timeout_range(self) -> None:
        """timeout 边界值。"""
        # timeout=1 是最小有效值
        config = FeishuConfig(app_id="test", app_secret="secret", timeout=1)
        assert config.timeout == 1

        # 大值
        config2 = FeishuConfig(app_id="test", app_secret="secret", timeout=300)
        assert config2.timeout == 300

    def test_config_max_retries_range(self) -> None:
        """max_retries 边界值。"""
        # max_retries=1 是最小有效值
        config = FeishuConfig(app_id="test", app_secret="secret", max_retries=1)
        assert config.max_retries == 1

        config2 = FeishuConfig(app_id="test", app_secret="secret", max_retries=10)
        assert config2.max_retries == 10

    def test_config_log_level_case_insensitive(self) -> None:
        """log_level 大小写不敏感。"""
        config1 = FeishuConfig(app_id="test", app_secret="secret", log_level="debug")
        assert config1.log_level == "DEBUG"

        config2 = FeishuConfig(app_id="test", app_secret="secret", log_level="Warning")
        assert config2.log_level == "WARNING"

    def test_config_equality(self) -> None:
        """相同值的配置相等。"""
        config1 = FeishuConfig(app_id="test", app_secret="secret")
        config2 = FeishuConfig(app_id="test", app_secret="secret")
        assert config1 == config2

    def test_config_inequality(self) -> None:
        """不同值的配置不相等。"""
        config1 = FeishuConfig(app_id="test1", app_secret="secret")
        config2 = FeishuConfig(app_id="test2", app_secret="secret")
        assert config1 != config2

    def test_config_hash(self) -> None:
        """相同值的配置 hash 相同。"""
        config1 = FeishuConfig(app_id="test", app_secret="secret")
        config2 = FeishuConfig(app_id="test", app_secret="secret")
        assert hash(config1) == hash(config2)

    def test_concurrent_config_creation(self) -> None:
        """并发创建配置对象。"""
        import concurrent.futures

        errors: list[Exception] = []

        def create_config(i: int) -> None:
            try:
                for _ in range(100):
                    config = FeishuConfig(app_id=f"app_{i}", app_secret=f"secret_{i}")
                    assert config.app_id == f"app_{i}"
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10):
            list(concurrent.futures.ThreadPoolExecutor(max_workers=10).map(create_config, range(10)))

        assert len(errors) == 0

    def test_config_timeout_zero(self) -> None:
        """timeout=0 应该被保留。"""
        config = FeishuConfig(app_id="test", app_secret="secret", timeout=0)
        assert config.timeout == 0

    def test_config_max_retries_zero(self) -> None:
        """max_retries=0 应该被保留（禁用重试）。"""
        config = FeishuConfig(app_id="test", app_secret="secret", max_retries=0)
        assert config.max_retries == 0

    def test_config_retry_wait_seconds_zero(self) -> None:
        """retry_wait_seconds=0 应该被保留。"""
        config = FeishuConfig(app_id="test", app_secret="secret", retry_wait_seconds=0)
        assert config.retry_wait_seconds == 0.0
