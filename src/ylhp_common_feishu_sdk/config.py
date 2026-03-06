"""SDK 配置管理。

设计决策:
  - 使用 @dataclass(frozen=True) 保证实例创建后不可变
  - 优先使用显式参数，其次从环境变量加载
  - 校验在 __post_init__ 中完成，失败时抛 FeishuConfigError
  - 不使用 Pydantic（config 是内部基础设施）
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from ylhp_common_feishu_sdk.exceptions import FeishuConfigError


@dataclass(frozen=True)
class FeishuConfig:
    """飞书 SDK 配置。

    三种使用方式（优先级从高到低）：
    1. 直接传参: FeishuConfig(app_id="xxx", app_secret="yyy")
    2. 环境变量: FeishuConfig()  # 自动读取 FEISHU_APP_ID 等
    3. 混合: FeishuConfig(app_id="xxx")  # app_secret 从环境变量读取

    Attributes:
        app_id: 飞书应用的 App ID
        app_secret: 飞书应用的 App Secret
        domain: 飞书 API 域名，默认 https://open.feishu.cn（私有化部署时修改）
        log_level: SDK 内部日志级别
        timeout: HTTP 请求超时时间（秒）
        max_retries: 最大重试次数
        retry_wait_seconds: 重试基础等待时间（秒），实际等待 = base * 2^attempt
    """

    app_id: str = ""
    app_secret: str = ""
    domain: str = ""
    log_level: str = ""
    timeout: int | None = None
    max_retries: int | None = None
    retry_wait_seconds: float | None = None

    def __post_init__(self) -> None:
        """初始化后处理：加载环境变量并校验。"""
        # frozen=True 下修改字段需要用 object.__setattr__
        _set = object.__setattr__

        # 加载环境变量（显式参数优先）
        _set(self, "app_id", self.app_id or os.getenv("FEISHU_APP_ID", ""))
        _set(
            self,
            "app_secret",
            self.app_secret or os.getenv("FEISHU_APP_SECRET", ""),
        )
        _set(
            self,
            "domain",
            self.domain or os.getenv("FEISHU_DOMAIN", "https://open.feishu.cn"),
        )
        _set(
            self,
            "log_level",
            (self.log_level or os.getenv("FEISHU_LOG_LEVEL", "INFO")).upper(),
        )
        _set(
            self,
            "timeout",
            self.timeout if self.timeout is not None else int(os.getenv("FEISHU_TIMEOUT", "10")),
        )
        _set(
            self,
            "max_retries",
            self.max_retries
            if self.max_retries is not None
            else int(os.getenv("FEISHU_MAX_RETRIES", "3")),
        )
        _set(
            self,
            "retry_wait_seconds",
            self.retry_wait_seconds
            if self.retry_wait_seconds is not None
            else float(os.getenv("FEISHU_RETRY_WAIT_SECONDS", "1.0")),
        )

        # 校验必填字段
        if not self.app_id:
            raise FeishuConfigError("app_id 未配置。请传入参数或设置环境变量 FEISHU_APP_ID。")
        if not self.app_secret:
            raise FeishuConfigError(
                "app_secret 未配置。请传入参数或设置环境变量 FEISHU_APP_SECRET。"
            )

        # 校验 log_level
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR"}
        if self.log_level not in valid_levels:
            raise FeishuConfigError(f"无效的 log_level: {self.log_level!r}。有效值: {valid_levels}")
