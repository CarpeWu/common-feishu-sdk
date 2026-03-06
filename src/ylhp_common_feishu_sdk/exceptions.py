"""SDK 统一异常体系。

设计决策:
- 基类 FeishuError 包含 retryable 属性，供重试装饰器判断
- 按照语义分为: 配置错误、校验错误、认证错误、限流、服务端错误、通用API错误
- translate_error() 将飞书错误码映射为对应异常类
- 未知错误码降级为 FeishuAPIError (retryable=False)，并记录 warning 日志
"""

from __future__ import annotations

import logging

logger = logging.getLogger("ylhp_common_feishu_sdk")


class FeishuError(Exception):
    """飞书 SDK 基础异常。

    Attributes:
        retryable: 该异常是否可以通过重试恢复
        message: 错误消息
    """

    retryable: bool = False
    message: str

    def __init__(self, message: str = "") -> None:
        self.message = message
        super().__init__(message)


class FeishuConfigError(FeishuError):
    """配置错误（缺少必要配置、配置冲突等）。不可重试。"""

    retryable = False


class FeishuValidationError(FeishuError):
    """参数校验错误（Pydantic 校验失败等）。不可重试。

    Attributes:
        field: 校验失败的字段名
        detail: 详细错误信息
    """

    retryable = False

    def __init__(self, field: str, detail: str) -> None:
        self.field = field
        self.detail = detail
        super().__init__(f"参数校验失败: {field} - {detail}")


class FeishuAPIError(FeishuError):
    """飞书 API 通用业务错误。不可重试。

    Attributes:
        code: 飞书错误码
        msg: 飞书错误消息
        log_id: 飞书请求日志 ID（用于向飞书技术支持提交工单）
    """

    retryable = False

    def __init__(self, code: int, msg: str, log_id: str | None = None) -> None:
        self.code = code
        self.msg = msg
        self.log_id = log_id
        super().__init__(f"飞书 API 错误 [{code}]: {msg} (log_id={log_id})")


class FeishuAuthError(FeishuAPIError):
    """认证/授权错误（Token 无效、权限不足、OAuth code 过期等）。不可重试。"""

    retryable = False


class FeishuRateLimitError(FeishuAPIError):
    """请求频率限制（HTTP 429）。可重试。

    Attributes:
        retry_after: 建议等待秒数（从响应头解析，可能为 None）
    """

    retryable = True

    def __init__(
        self,
        code: int,
        msg: str,
        log_id: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(code, msg, log_id)
        self.retry_after = retry_after


class FeishuServerError(FeishuAPIError):
    """飞书服务端错误（5xx 类）。可重试。"""

    retryable = True


# ── 错误码分类集合 ──

_AUTH_CODES: frozenset[int] = frozenset(
    {
        99991660,  # access_token invalid
        99991661,  # access_token expired
        99991662,  # access_token reused
        99991663,  # tenant_access_token invalid
        99991664,  # tenant_access_token expired
        99991665,  # app_access_token invalid
        99991668,  # insufficient scope
        99991669,  # app not available
        10003,  # invalid app_id
        10014,  # app_secret error
    }
)

_RATE_LIMIT_CODES: frozenset[int] = frozenset(
    {
        99991400,  # rate limit
        99991429,  # too many requests
    }
)

_SERVER_ERROR_CODES: frozenset[int] = frozenset(
    {
        99991500,  # internal server error
        99991501,  # service unavailable
        99991502,  # bad gateway
        99991503,  # gateway timeout
        99991504,  # upstream timeout
    }
)


def translate_error(code: int, msg: str, log_id: str | None = None) -> FeishuAPIError:
    """将飞书错误码翻译为语义化异常。

    Args:
        code: 飞书 API 错误码
        msg: 飞书 API 错误消息
        log_id: 请求日志 ID

    Returns:
        对应的异常实例（FeishuAuthError / FeishuRateLimitError /
        FeishuServerError / FeishuAPIError）

    Example:
        >>> try:
        ...     resp = client.contact.v3.user.get(req)
        ...     if not resp.success():
        ...         raise translate_error(resp.code, resp.msg, resp.get_log_id())
        ... except FeishuAuthError:
        ...     print("认证失败，请检查 app_id 和 app_secret")
    """
    if code in _AUTH_CODES:
        return FeishuAuthError(code, msg, log_id)
    if code in _RATE_LIMIT_CODES:
        return FeishuRateLimitError(code, msg, log_id)
    if code in _SERVER_ERROR_CODES:
        return FeishuServerError(code, msg, log_id)

    # 兜底策略：检查 msg 关键词
    msg_lower = msg.lower() if msg else ""
    if any(kw in msg_lower for kw in ("token", "auth", "permission", "forbidden")):
        return FeishuAuthError(code, msg, log_id)
    if any(kw in msg_lower for kw in ("rate", "limit", "throttl")):
        return FeishuRateLimitError(code, msg, log_id)
    if any(kw in msg_lower for kw in ("internal", "server error", "unavailable")):
        return FeishuServerError(code, msg, log_id)

    # 未知错误码 — 记录 warning 便于后续补充
    logger.warning(
        "未知飞书错误码 %d，降级为 FeishuAPIError (msg=%s, log_id=%s)",
        code,
        msg,
        log_id,
    )
    return FeishuAPIError(code, msg, log_id)
