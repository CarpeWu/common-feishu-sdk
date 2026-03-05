"""SDK 数据模型。

设计决策 — "进严出宽":
  - 入参（Pydantic BaseModel）: 调用 API 前严格校验，  - 出参（dataclass）: 从 API 响应构造，使用 getattr 兜底
  - dataclass 比 Pydantic 轻量，且可以用 frozen=True 保证不可变
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class PageResult(Generic[T]):
    """分页查询结果。

    Attributes:
        items: 当前页的数据列表
        page_token: 下一页的分页标记（无下一页时为 None）
        has_more: 是否还有更多数据
    """

    items: list[T]
    page_token: str | None = None
    has_more: bool = False
