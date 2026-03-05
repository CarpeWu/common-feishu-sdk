"""SDK 专用 logger（不污染宿主应用）和日志脱敏 Filter。

设计决策:
  - 使用标准库 logging 的 named logger ("ylhp_common_feishu_sdk")
  - propagate=False，不影响宿主应用的 root logger
  - 脱敏 Filter 通过正则匹配，将敏感信息替换为掩码
  - 幂等: 多次调用不会重复添加 handler
"""

from __future__ import annotations

import logging
import re


class SensitiveFilter(logging.Filter):
    """日志脱敏过滤器。

    匹配并掩码以下敏感信息：
    - Bearer token: "Bearer xxx" → "Bearer ***"
    - 飞书 token: "t-xxx" → "t-****"
    - app_secret 值: app_secret='xxx' → app_secret='****'
    """

    # 脱敏规则: (正则模式, 替换字符串)
    _PATTERNS: list[tuple[re.Pattern[str], str]] = [
        # Bearer token
        (re.compile(r"Bearer\s+\S+", re.IGNORECASE), "Bearer ***"),
        # 飞书 token (t-xxx 格式)
        (re.compile(r"\bt-[a-zA-Z0-9]{8,}\b"), "t-****"),
        # app_secret='xxx' 或 app_secret="xxx"
        (
            re.compile(r"(app_secret[\"':\s=]+)['\"]?[a-zA-Z0-9_]{8,}['\"]?", re.IGNORECASE),
            r"\1'****'",
        ),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """过滤并脱敏日志记录。

        Args:
            record: 日志记录对象

        Returns:
            总是返回 True（允许记录通过），但会修改 record.msg
        """
        msg = record.msg
        for pattern, replacement in self._PATTERNS:
            msg = pattern.sub(replacement, msg)
        record.msg = msg
        # 清空 args 避免 % 格式化时还原原文
        record.args = ()  # type: ignore[assignment]
        return True


def setup_sdk_logger(level: str = "INFO") -> logging.Logger:
    """配置 SDK 专用 logger。

    - logger name: "ylhp_common_feishu_sdk"
    - propagate: False（不传播到 root logger）
    - 添加 SensitiveFilter 脱敏
    - 幂等: 多次调用不会重复添加 handler

    Args:
        level: 日志级别（DEBUG / INFO / WARNING / ERROR）

    Returns:
        配置好的 logger 实例
    """
    logger = logging.getLogger("ylhp_common_feishu_sdk")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s [%(name)s] %(levelname)s %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        handler.addFilter(SensitiveFilter())
        logger.addHandler(handler)

    return logger
