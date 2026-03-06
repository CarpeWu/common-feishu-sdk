"""选择性重试装饰器。

设计决策:
  - 从 self._config 动态读取重试参数（max_retries, retry_wait_seconds）
  - 仅对 retryable=True 的 FeishuError 子类重试
  - FeishuRateLimitError 优先使用 retry_after 作为等待时间
  - 其他可重试异常使用指数退避: wait = base * 2^attempt
  - 最终失败时记录重试次数和总耗时
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

from ylhp_common_feishu_sdk.exceptions import FeishuError, FeishuRateLimitError

logger = logging.getLogger("ylhp_common_feishu_sdk")


def with_retry[R](func: Callable[..., R]) -> Callable[..., R]:
    """选择性重试装饰器。

    从被装饰方法所在 Service 实例的 self._config 动态读取
    max_retries 和 retry_wait_seconds。

    仅对 retryable=True 的 FeishuError 子类进行重试。
    其他异常（包括 FeishuAuthError、FeishuValidationError、
    FeishuAPIError、Pydantic ValidationError）立即抛出。

    要求:
        被装饰方法的 self 必须拥有 _config 属性（FeishuConfig 类型）。
        所有继承 BaseService 的类均满足此条件。

    Args:
        func: 被装饰的方法

    Returns:
        装饰后的方法

    Example:
        class MessagingService(BaseService):
            @with_retry
            def send_text(self, open_id: str, text: str) -> str:
                ...
    """

    @wraps(func)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> R:
        # 从实例动态读取重试配置
        max_retries: int = self._config.max_retries
        base_wait: float = self._config.retry_wait_seconds

        last_exception: FeishuError | None = None
        start_time = time.monotonic()

        for attempt in range(max_retries + 1):
            try:
                return func(self, *args, **kwargs)
            except FeishuError as e:
                if not e.retryable:
                    raise

                last_exception = e

                if attempt >= max_retries:
                    break

                # 计算等待时间
                if isinstance(e, FeishuRateLimitError) and e.retry_after:
                    wait_time = e.retry_after
                else:
                    wait_time = base_wait * (2**attempt)

                logger.debug(
                    f"API 调用失败 (attempt {attempt + 1}/{max_retries + 1}), "
                    f"{wait_time:.2f}s 后重试: {e}"
                )
                time.sleep(wait_time)

        # 所有重试都失败
        total_time = time.monotonic() - start_time
        logger.warning(
            f"API 调用最终失败: 共重试 {max_retries} 次, "
            f"总耗时 {total_time:.2f}s, 错误: {last_exception}"
        )
        raise last_exception

    return wrapper
