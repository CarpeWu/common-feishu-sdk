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
from collections.abc import Callable
from typing import Any


class SensitiveFilter(logging.Filter):
    """日志脱敏过滤器。

    匹配并掩码以下敏感信息：
    - JWT token: "eyJ..." → "eyJ***"
    - tenant_access_token: "t-xxx" → "t-***"
    - app_access_token: "a-xxx" → "a-***"
    - App Secret: "app_secret": "xxx" → "app_secret": "***"
    - App ID: "cli_xxx" → "cli_xxx***"（保留前8位）
    - URL code: "?code=xxx" → "?code=***"
    - JSON code: "code": "xxx" → "code": "***"
    - Bearer token: "Bearer xxx" → "Bearer ***"
    """

    # 脱敏规则: (正则模式, 替换字符串或 callable)
    _PATTERNS: list[tuple[re.Pattern[str], str | Callable[[re.Match[str]], str]]] = [
        # 1. JWT 格式 token (user_access_token, refresh_token)
        (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"), "eyJ***"),

        # 2. tenant_access_token (t-前缀 + 至少20字符)
        (re.compile(r"\bt-[A-Za-z0-9_-]{20,}\b"), "t-***"),

        # 3. app_access_token (a-前缀 + 至少20字符)
        (re.compile(r"\ba-[A-Za-z0-9_-]{20,}\b"), "a-***"),

        # 4. App Secret (限定 JSON key 上下文)
        # 匹配: "app_secret": / "client_secret": / "secret": / "app_Secret":
        (
            re.compile(
                r'("(?:app_?secret|client_secret|secret)"\s*:\s*")([A-Za-z0-9_]{8,})(")',
                re.IGNORECASE,
            ),
            r"\1***\3",
        ),

        # 5. App ID (cli_前缀 + 至少16位)
        # 保留前8位用于调试: cli_a879***
        (
            re.compile(r"\bcli_[a-z0-9]{16,}\b"),
            lambda m: f"{m.group()[:8]}***",
        ),

        # 6. URL 中的授权码 code 参数
        (re.compile(r"([?&]code=)[A-Za-z0-9_-]{16,}"), r"\1***"),

        # 7. JSON code 字段 (字符串值，数字 code 不匹配)
        (re.compile(r'("code"\s*:\s*")([A-Za-z0-9_-]{16,})(")'), r"\1***\3"),

        # 8. Bearer Authorization Header (兜底)
        (re.compile(r"(Bearer\s+)\S{20,}", re.IGNORECASE), r"\1***"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """过滤并脱敏日志记录。

        Args:
            record: 日志记录对象

        Returns:
            总是返回 True（允许记录通过），但会修改 record.msg 和 record.args
        """
        # 脱敏 msg
        if isinstance(record.msg, str):
            record.msg = self._mask(record.msg)

        # 脱敏 args (格式化参数)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._mask_value(v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self._mask_value(a) for a in record.args)

        return True

    def _mask(self, text: str) -> str:
        """对字符串应用所有脱敏规则。"""
        for pattern, repl in self._PATTERNS:
            text = pattern.sub(repl, text)
        return text

    def _mask_value(self, value: Any) -> Any:
        """递归脱敏任意值（处理嵌套 dict/list）。"""
        if isinstance(value, str):
            return self._mask(value)
        elif isinstance(value, dict):
            return {k: self._mask_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._mask_value(item) for item in value]
        return value


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
