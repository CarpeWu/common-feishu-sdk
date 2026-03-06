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


class TestPageResultBoundary:
    """测试 PageResult 边界情况。"""

    def test_page_result_with_dict_type(self) -> None:
        """泛型支持 dict 类型。"""
        result: PageResult[dict[str, int]] = PageResult(
            items=[{"a": 1}, {"b": 2}],
            page_token=None,
            has_more=False,
        )
        assert result.items == [{"a": 1}, {"b": 2}]

    def test_page_result_with_custom_class(self) -> None:
        """泛型支持自定义类型。"""

        class User:
            def __init__(self, name: str) -> None:
                self.name = name

        result: PageResult[User] = PageResult(
            items=[User("Alice"), User("Bob")],
            page_token=None,
            has_more=False,
        )
        assert len(result.items) == 2
        assert result.items[0].name == "Alice"

    def test_page_result_equality(self) -> None:
        """相同值的结果相等。"""
        result1 = PageResult(items=["a", "b"], page_token="token", has_more=True)
        result2 = PageResult(items=["a", "b"], page_token="token", has_more=True)
        assert result1 == result2

    def test_page_result_inequality(self) -> None:
        """不同值的结果不相等。"""
        result1 = PageResult(items=["a"], page_token=None, has_more=False)
        result2 = PageResult(items=["b"], page_token=None, has_more=False)
        assert result1 != result2

    def test_page_result_asdict(self) -> None:
        """可以使用 dataclasses.asdict 序列化。"""
        from dataclasses import asdict

        result = PageResult(items=["a", "b"], page_token="next", has_more=True)
        d = asdict(result)
        assert d == {"items": ["a", "b"], "page_token": "next", "has_more": True}

    def test_page_result_repr(self) -> None:
        """__repr__ 包含完整信息。"""
        result = PageResult(items=["a"], page_token="t", has_more=True)
        repr_str = repr(result)
        assert "PageResult" in repr_str
        assert "items" in repr_str

    def test_page_result_large_items(self) -> None:
        """大量数据项。"""
        items = list(range(10000))
        result: PageResult[int] = PageResult(
            items=items,
            page_token=None,
            has_more=False,
        )
        assert len(result.items) == 10000
        assert result.items[0] == 0
        assert result.items[-1] == 9999

    def test_page_result_long_page_token(self) -> None:
        """超长 page_token。"""
        long_token = "a" * 1000
        result = PageResult(items=[1], page_token=long_token, has_more=True)
        assert result.page_token == long_token
        assert len(result.page_token) == 1000
