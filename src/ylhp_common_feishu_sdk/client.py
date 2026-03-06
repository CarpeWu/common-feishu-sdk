"""Feishu SDK 主类（Facade 模式）。

设计决策:
  - 普通类（非单例），每次实例化创建独立客户端
  - 支持三种初始化方式: config 对象、关键字参数、环境变量
  - 命名注册表支持多应用场景（线程安全）
  - 每个实例持有独立的 lark.Client + FeishuConfig
"""

from __future__ import annotations

import threading
from typing import Any

import lark_oapi as lark

from ylhp_common_feishu_sdk.config import FeishuConfig
from ylhp_common_feishu_sdk.exceptions import FeishuConfigError
from ylhp_common_feishu_sdk.log import setup_sdk_logger
from ylhp_common_feishu_sdk.services.auth import AuthService
from ylhp_common_feishu_sdk.services.contact import ContactService
from ylhp_common_feishu_sdk.services.messaging import MessagingService


class Feishu:
    """飞书 SDK 主类。

    三种初始化方式（优先级从高到低）：
    1. 传入 FeishuConfig 对象
    2. 传入关键字参数 (app_id, app_secret, ...)
    3. 从环境变量自动加载

    Attributes:
        config: 当前实例的配置（只读）
        lark_client: 底层 lark-oapi 客户端（用于访问 SDK 未封装的接口）

    Example:
        # 直接实例化
        feishu = Feishu(app_id="xxx", app_secret="yyy")

        # 命名注册
        Feishu.register("hr", FeishuConfig(app_id="hr_app", app_secret="hr_secret"))
        hr = Feishu.get("hr")
    """

    # ─── 类级别注册表（线程安全）───
    _registry: dict[str, Feishu] = {}
    _registry_lock: threading.Lock = threading.Lock()

    def __init__(
        self,
        config: FeishuConfig | None = None,
        *,
        app_id: str = "",
        app_secret: str = "",
        **kwargs: Any,
    ) -> None:
        """创建飞书客户端实例。

        Args:
            config: 完整配置对象（优先级最高）
            app_id: 飞书 App ID（快捷方式）
            app_secret: 飞书 App Secret（快捷方式）
            **kwargs: 其他 FeishuConfig 支持的参数
        """
        if config is not None:
            self._config = config
        elif app_id:
            self._config = FeishuConfig(app_id=app_id, app_secret=app_secret, **kwargs)
        else:
            self._config = FeishuConfig()

        # 1. 日志（SDK 专属 logger，不污染宿主应用）
        setup_sdk_logger(self._config.log_level)

        # 2. 官方 lark-oapi 客户端
        log_level_map = {
            "DEBUG": lark.LogLevel.DEBUG,
            "INFO": lark.LogLevel.INFO,
            "WARNING": lark.LogLevel.WARNING,
            "ERROR": lark.LogLevel.ERROR,
        }
        self._lark_client: lark.Client = (
            lark.Client.builder()
            .app_id(self._config.app_id)
            .app_secret(self._config.app_secret)
            .domain(self._config.domain)
            .timeout(self._config.timeout)
            .log_level(log_level_map.get(self._config.log_level, lark.LogLevel.INFO))
            .build()
        )

        # 3. 注册 Services（每个 Service 持有 config 引用）
        self.auth = AuthService(self._lark_client, self._config)
        self.messages = MessagingService(self._lark_client, self._config)
        self.contacts = ContactService(self._lark_client, self._config)

    # ─── 命名注册表 API ───

    @classmethod
    def register(cls, name: str, config: FeishuConfig) -> Feishu:
        """创建客户端实例并注册到全局注册表。

        如果同名实例已存在，会抛出错误（防止意外覆盖）。
        若需覆盖，请先 remove() 再 register()。

        Args:
            name: 实例名称（如 "default", "hr", "bot"）
            config: 飞书配置

        Returns:
            创建的 Feishu 实例

        Raises:
            FeishuConfigError: 同名实例已注册
        """
        with cls._registry_lock:
            if name in cls._registry:
                existing = cls._registry[name]
                raise FeishuConfigError(
                    f'名为 "{name}" 的实例已注册 '
                    f"(app_id={existing._config.app_id})。"
                    f'若需覆盖，请先调用 Feishu.remove("{name}")。'
                )
            instance = cls(config=config)
            cls._registry[name] = instance
            return instance

    @classmethod
    def get(cls, name: str = "default") -> Feishu:
        """从注册表获取已注册的命名实例。

        Args:
            name: 实例名称，默认 "default"

        Returns:
            已注册的 Feishu 实例

        Raises:
            FeishuConfigError: 实例不存在
        """
        with cls._registry_lock:
            if name not in cls._registry:
                available = list(cls._registry.keys()) or ["(无)"]
                raise FeishuConfigError(
                    f'未找到名为 "{name}" 的实例。'
                    f"已注册的实例: {', '.join(available)}。"
                    f'请先调用 Feishu.register("{name}", config) 注册。'
                )
            return cls._registry[name]

    @classmethod
    def remove(cls, name: str) -> None:
        """从注册表移除命名实例。

        Args:
            name: 实例名称

        Raises:
            FeishuConfigError: 实例不存在
        """
        with cls._registry_lock:
            if name not in cls._registry:
                raise FeishuConfigError(f'未找到名为 "{name}" 的实例，无法移除。')
            del cls._registry[name]

    @classmethod
    def clear_registry(cls) -> None:
        """清空注册表。仅用于测试。"""
        with cls._registry_lock:
            cls._registry.clear()

    @classmethod
    def registered_names(cls) -> list[str]:
        """返回已注册的所有实例名称。"""
        with cls._registry_lock:
            return list(cls._registry.keys())

    # ─── 底层访问 ───

    @property
    def config(self) -> FeishuConfig:
        """获取当前实例的配置（只读）。"""
        return self._config

    @property
    def lark_client(self) -> lark.Client:
        """获取底层 lark-oapi 客户端（用于访问 SDK 未封装的接口）。"""
        return self._lark_client

    def __repr__(self) -> str:
        return f"Feishu(app_id={self._config.app_id!r})"
