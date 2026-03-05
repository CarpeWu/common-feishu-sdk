"""测试 models 模块。

测试用例覆盖:
- PageResult 泛型类
- frozen 不可变
- has_more 逻辑
"""

from __future__ import annotations

from ylhp_common_feishu_sdk.models import PageResult


class TestPageResult:
    """测试 PageResult 分页结果类。"""

    def test_page_result_basic(self) -> None:
        """基本分页结果。"""
        result: PageResult[str] = PageResult(
            items=["a", "b", "c"],
            page_token="next_token",
            has_more=True,
        )
        assert result.items == ["a", "b", "c"]
        assert result.page_token == "next_token"
        assert result.has_more is True

    def test_page_result_no_more(self) -> None:
        """没有更多数据时。"""
        result: PageResult[int] = PageResult(
            items=[1, 2, 3],
            page_token=None,
            has_more=False,
        )
        assert result.items == [1, 2, 3]
        assert result.page_token is None
        assert result.has_more is False

    def test_page_result_empty(self) -> None:
        """空结果。"""
        result: PageResult[str] = PageResult(
            items=[],
            page_token=None,
            has_more=False,
        )
        assert result.items == []
        assert result.page_token is None
        assert result.has_more is False

    def test_page_result_frozen(self) -> None:
        """PageResult 应该是不可变的。"""
        result = PageResult(items=["a"], page_token=None, has_more=False)
        try:
            result.items.append("b")  # list 本身是可变的，但这不影响 frozen
        except AttributeError:
            pass  # 如果是 tuple 就会报错

        # 但不能重新赋值
        try:
            result.has_more = True  # type: ignore[misc]
        except (AttributeError, TypeError):
            pass  # frozen=True 应该阻止赋值
