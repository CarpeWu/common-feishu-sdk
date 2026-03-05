"""测试 client 模块。

测试用例覆盖:
- 三种初始化方式
- 命名注册表
- 线程安全
- 服务属性
"""

from __future__ import annotations

import threading
from typing import Any

import pytest

from ylhp_common_feishu_sdk import Feishu
from ylhp_common_feishu_sdk.config import FeishuConfig
from ylhp_common_feishu_sdk.exceptions import FeishuConfigError


class TestFeishuInit:
    """测试 Feishu 初始化。"""

    def test_init_with_config(self) -> None:
        """使用 FeishuConfig 初始化。"""
        config = FeishuConfig(app_id="cli_test", app_secret="secret")
        feishu = Feishu(config=config)
        assert feishu.config.app_id == "cli_test"
        assert feishu.config.app_secret == "secret"

    def test_init_with_kwargs(self) -> None:
        """使用关键字参数初始化。"""
        feishu = Feishu(app_id="cli_kwargs", app_secret="kwargs_secret")
        assert feishu.config.app_id == "cli_kwargs"
        assert feishu.config.app_secret == "kwargs_secret"

    def test_init_with_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """从环境变量初始化。"""
        monkeypatch.setenv("FEISHU_APP_ID", "cli_env")
        monkeypatch.setenv("FEISHU_APP_SECRET", "env_secret")
        feishu = Feishu()
        assert feishu.config.app_id == "cli_env"
        assert feishu.config.app_secret == "env_secret"

    def test_independent_instances(self) -> None:
        """每次实例化创建独立实例。"""
        config1 = FeishuConfig(app_id="app1", app_secret="secret1")
        config2 = FeishuConfig(app_id="app2", app_secret="secret2")
        feishu1 = Feishu(config=config1)
        feishu2 = Feishu(config=config2)
        assert feishu1 is not feishu2
        assert feishu1.config.app_id != feishu2.config.app_id


class TestFeishuRegistry:
    """测试命名注册表。"""

    def test_register_and_get(self) -> None:
        """注册后可以通过名称获取。"""
        config = FeishuConfig(app_id="cli_registry", app_secret="secret")
        feishu = Feishu.register("test_app", config)
        assert feishu is not None
        retrieved = Feishu.get("test_app")
        assert retrieved is feishu

    def test_register_duplicate_raises(self) -> None:
        """重复注册同名实例应该抛出错误。"""
        config = FeishuConfig(app_id="cli_dup", app_secret="secret")
        Feishu.register("dup_app", config)
        with pytest.raises(FeishuConfigError):
            Feishu.register("dup_app", config)

    def test_get_nonexistent_raises(self) -> None:
        """获取不存在的实例应该抛出错误。"""
        with pytest.raises(FeishuConfigError):
            Feishu.get("nonexistent_app")

    def test_get_default(self) -> None:
        """不传名称时返回 default 实例。"""
        config = FeishuConfig(app_id="cli_default", app_secret="secret")
        Feishu.register("default", config)
        feishu = Feishu.get()
        assert feishu.config.app_id == "cli_default"

    def test_remove_and_reregister(self) -> None:
        """移除后可以重新注册。"""
        config = FeishuConfig(app_id="cli_remove", app_secret="secret")
        Feishu.register("to_remove", config)
        Feishu.remove("to_remove")
        with pytest.raises(FeishuConfigError):
            Feishu.get("to_remove")
        # 重新注册
        Feishu.register("to_remove", config)
        assert Feishu.get("to_remove") is not None

    def test_remove_nonexistent_raises(self) -> None:
        """移除不存在的实例应该抛出错误。"""
        with pytest.raises(FeishuConfigError):
            Feishu.remove("nonexistent")

    def test_registered_names(self) -> None:
        """返回所有已注册名称。"""
        config = FeishuConfig(app_id="cli_names", app_secret="secret")
        Feishu.register("names_app1", config)
        Feishu.register("names_app2", config)
        names = Feishu.registered_names()
        assert "names_app1" in names
        assert "names_app2" in names

    def test_clear_registry(self) -> None:
        """清空注册表。"""
        config = FeishuConfig(app_id="cli_clear", app_secret="secret")
        Feishu.register("clear_app", config)
        Feishu.clear_registry()
        assert len(Feishu.registered_names()) == 0


class TestFeishuThreadSafety:
    """测试线程安全。"""

    def test_concurrent_register(self) -> None:
        """并发注册不同名称应该成功。"""
        results: dict[str, Any] = {}
        errors: list[Exception] = []

        def register_app(name: str, app_id: str) -> None:
            try:
                config = FeishuConfig(app_id=app_id, app_secret=f"{name}_secret")
                feishu = Feishu.register(name, config)
                results[name] = feishu
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=register_app, args=(f"thread_{i}", f"cli_thread_{i}"))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 所有线程应该成功
        assert len(errors) == 0
        assert len(results) == 10


class TestFeishuProperties:
    """测试属性。"""

    def test_config_property(self) -> None:
        """config 属性返回配置对象。"""
        config = FeishuConfig(app_id="cli_prop", app_secret="secret")
        feishu = Feishu(config=config)
        assert feishu.config is config

    def test_repr(self) -> None:
        """repr 包含 app_id。"""
        config = FeishuConfig(app_id="cli_repr", app_secret="secret")
        feishu = Feishu(config=config)
        assert "cli_repr" in repr(feishu)
