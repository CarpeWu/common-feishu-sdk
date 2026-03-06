"""测试 Contact 服务。

测试用例覆盖:
- list_departments: 获取子部门列表
- iter_departments: 部门自动翻页迭代器
- list_department_users: 获取部门直属员工列表
- iter_department_users: 员工自动翻页迭代器
- get_user: 获取用户详细信息
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from ylhp_common_feishu_sdk.config import FeishuConfig
from ylhp_common_feishu_sdk.exceptions import (
    FeishuAuthError,
    FeishuValidationError,
)

# ─── 测试 Fixtures ───


@pytest.fixture
def config() -> FeishuConfig:
    """创建测试配置。"""
    return FeishuConfig(
        app_id="cli_test_000",
        app_secret="test_secret_000",
        max_retries=2,
        retry_wait_seconds=0.01,
    )


@pytest.fixture
def mock_client() -> MagicMock:
    """创建 mock lark client。"""
    return MagicMock()


def make_department_item(
    dept_id: str = "od_xxx",
    name: str = "测试部门",
    parent_id: str = "0",
) -> MagicMock:
    """创建部门响应项。"""
    item = MagicMock()
    item.department_id = dept_id
    item.open_department_id = dept_id
    item.name = name
    item.parent_department_id = parent_id
    item.leader_user_id = "ou_leader"
    item.member_count = 10
    return item


def make_user_item(
    open_id: str = "ou_xxx",
    name: str = "张三",
    email: str | None = "zhangsan@example.com",
) -> MagicMock:
    """创建用户响应项。"""
    item = MagicMock()
    item.open_id = open_id
    item.name = name
    item.en_name = "Zhang San"
    item.email = email
    item.mobile = "+8613800138000"
    item.department_ids = ["od_dept1"]
    avatar = MagicMock()
    avatar.avatar_72 = "https://example.com/avatar/72.jpg"
    item.avatar = avatar
    return item


def make_success_response(data: Any = None) -> MagicMock:
    """创建成功响应 mock。"""
    resp = MagicMock()
    resp.success = True
    resp.code = 0
    resp.msg = "success"
    resp.data = data
    return resp


def make_error_response(code: int, msg: str) -> MagicMock:
    """创建错误响应 mock。"""
    resp = MagicMock()
    resp.success = False
    resp.code = code
    resp.msg = msg
    resp.log_id = f"log_{code}"
    return resp


# ─── 测试类：list_departments ───


class TestListDepartments:
    """测试 list_departments 方法。"""

    def test_list_departments_success(self, mock_client: MagicMock, config: FeishuConfig) -> None:
        """获取子部门列表成功。"""
        from ylhp_common_feishu_sdk.services.contact import ContactService

        # 准备 mock 响应
        data = MagicMock()
        data.items = [
            make_department_item("od_dept1", "研发部"),
            make_department_item("od_dept2", "产品部"),
        ]
        data.page_token = None
        data.has_more = False

        mock_client.contact.v3.department.children.return_value = make_success_response(data)

        # 执行
        service = ContactService(mock_client, config)
        result = service.list_departments(parent_department_id="0")

        # 验证
        assert len(result.items) == 2
        assert result.items[0].name == "研发部"
        assert result.items[1].name == "产品部"
        assert result.has_more is False

    def test_list_departments_pagination(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """获取子部门列表分页。"""
        from ylhp_common_feishu_sdk.services.contact import ContactService

        # 准备第一页响应
        data = MagicMock()
        data.items = [make_department_item("od_dept1", "研发部")]
        data.page_token = "token_page2"
        data.has_more = True

        mock_client.contact.v3.department.children.return_value = make_success_response(data)

        # 执行
        service = ContactService(mock_client, config)
        result = service.list_departments(parent_department_id="0", page_token=None)

        # 验证
        assert len(result.items) == 1
        assert result.has_more is True
        assert result.page_token == "token_page2"

    def test_list_departments_empty_result(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """获取子部门列表返回空结果。"""
        from ylhp_common_feishu_sdk.services.contact import ContactService

        # 准备空响应
        data = MagicMock()
        data.items = []
        data.page_token = None
        data.has_more = False

        mock_client.contact.v3.department.children.return_value = make_success_response(data)

        # 执行
        service = ContactService(mock_client, config)
        result = service.list_departments(parent_department_id="0")

        # 验证
        assert len(result.items) == 0
        assert result.has_more is False

    def test_list_departments_permission_denied(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """获取子部门列表权限不足。"""
        from ylhp_common_feishu_sdk.services.contact import ContactService

        # 准备权限错误响应
        mock_client.contact.v3.department.children.return_value = make_error_response(
            99991668, "permission denied"
        )

        # 执行并验证
        service = ContactService(mock_client, config)
        with pytest.raises(FeishuAuthError):
            service.list_departments(parent_department_id="0")

    def test_list_departments_invalid_page_size(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """获取子部门列表 page_size 无效。"""
        from ylhp_common_feishu_sdk.services.contact import ContactService

        service = ContactService(mock_client, config)

        # page_size 超过 50
        with pytest.raises(FeishuValidationError):
            service.list_departments(parent_department_id="0", page_size=100)

        # page_size 小于 1
        with pytest.raises(FeishuValidationError):
            service.list_departments(parent_department_id="0", page_size=0)


class TestIterDepartments:
    """测试 iter_departments 自动翻页迭代器。"""

    def test_iter_departments_auto_pagination(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """iter_departments 自动翻页获取全部子部门（3页数据）。"""
        from ylhp_common_feishu_sdk.services.contact import ContactService

        # 准备三页响应
        page1_data = MagicMock()
        page1_data.items = [make_department_item("od_dept1", "部门1")]
        page1_data.page_token = "token_page2"
        page1_data.has_more = True

        page2_data = MagicMock()
        page2_data.items = [make_department_item("od_dept2", "部门2")]
        page2_data.page_token = "token_page3"
        page2_data.has_more = True

        page3_data = MagicMock()
        page3_data.items = [make_department_item("od_dept3", "部门3")]
        page3_data.page_token = None
        page3_data.has_more = False

        # 配置 mock 返回不同页
        mock_client.contact.v3.department.children.side_effect = [
            make_success_response(page1_data),
            make_success_response(page2_data),
            make_success_response(page3_data),
        ]

        # 执行
        service = ContactService(mock_client, config)
        all_departments = list(service.iter_departments(parent_department_id="0"))

        # 验证
        assert len(all_departments) == 3
        assert all_departments[0].name == "部门1"
        assert all_departments[1].name == "部门2"
        assert all_departments[2].name == "部门3"
        # 验证调用了 3 次
        assert mock_client.contact.v3.department.children.call_count == 3


# ─── 测试类：list_department_users ───


class TestListDepartmentUsers:
    """测试 list_department_users 方法。"""

    def test_list_department_users_success(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """获取部门员工列表成功。"""
        from ylhp_common_feishu_sdk.services.contact import ContactService

        # 准备 mock 响应
        data = MagicMock()
        data.items = [
            make_user_item("ou_user1", "张三"),
            make_user_item("ou_user2", "李四"),
        ]
        data.page_token = None
        data.has_more = False

        mock_client.contact.v3.user.find_by_department.return_value = make_success_response(data)

        # 执行
        service = ContactService(mock_client, config)
        result = service.list_department_users(department_id="od_dept1")

        # 验证
        assert len(result.items) == 2
        assert result.items[0].name == "张三"
        assert result.items[1].name == "李四"
        assert result.has_more is False

    def test_list_department_users_empty_id(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """获取部门员工列表 department_id 为空。"""
        from ylhp_common_feishu_sdk.services.contact import ContactService

        service = ContactService(mock_client, config)

        with pytest.raises(FeishuValidationError):
            service.list_department_users(department_id="")

    def test_list_department_users_empty_result(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """获取部门员工列表返回空结果。"""
        from ylhp_common_feishu_sdk.services.contact import ContactService

        # 准备空响应
        data = MagicMock()
        data.items = []
        data.page_token = None
        data.has_more = False

        mock_client.contact.v3.user.find_by_department.return_value = make_success_response(data)

        # 执行
        service = ContactService(mock_client, config)
        result = service.list_department_users(department_id="od_empty_dept")

        # 验证
        assert len(result.items) == 0
        assert result.has_more is False

    def test_list_department_users_permission_denied(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """获取部门员工列表权限不足。"""
        from ylhp_common_feishu_sdk.services.contact import ContactService

        # 准备权限错误响应
        mock_client.contact.v3.user.find_by_department.return_value = make_error_response(
            99991668, "permission denied"
        )

        # 执行并验证
        service = ContactService(mock_client, config)
        with pytest.raises(FeishuAuthError):
            service.list_department_users(department_id="od_dept1")


class TestIterDepartmentUsers:
    """测试 iter_department_users 自动翻页迭代器。"""

    def test_iter_department_users_auto_pagination(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """iter_department_users 自动翻页获取全部员工（2页数据）。"""
        from ylhp_common_feishu_sdk.services.contact import ContactService

        # 准备两页响应
        page1_data = MagicMock()
        page1_data.items = [
            make_user_item("ou_user1", "用户1"),
            make_user_item("ou_user2", "用户2"),
        ]
        page1_data.page_token = "token_page2"
        page1_data.has_more = True

        page2_data = MagicMock()
        page2_data.items = [make_user_item("ou_user3", "用户3")]
        page2_data.page_token = None
        page2_data.has_more = False

        # 配置 mock 返回不同页
        mock_client.contact.v3.user.find_by_department.side_effect = [
            make_success_response(page1_data),
            make_success_response(page2_data),
        ]

        # 执行
        service = ContactService(mock_client, config)
        all_users = list(service.iter_department_users(department_id="od_dept1"))

        # 验证
        assert len(all_users) == 3
        assert all_users[0].name == "用户1"
        assert all_users[1].name == "用户2"
        assert all_users[2].name == "用户3"
        # 验证调用了 2 次
        assert mock_client.contact.v3.user.find_by_department.call_count == 2


# ─── 测试类：get_user ───


class TestGetUser:
    """测试 get_user 方法。"""

    def test_get_user_success(self, mock_client: MagicMock, config: FeishuConfig) -> None:
        """获取用户详细信息成功。"""
        from ylhp_common_feishu_sdk.services.contact import ContactService

        # 准备 mock 响应
        user_data = make_user_item("ou_test_user", "王五")
        user_data.job_title = "高级工程师"

        status = MagicMock()
        status.is_activated = True
        status.is_frozen = False
        status.is_resigned = False
        user_data.status = status

        data = MagicMock()
        data.user = user_data

        mock_client.contact.v3.user.get.return_value = make_success_response(data)

        # 执行
        service = ContactService(mock_client, config)
        result = service.get_user(user_id="ou_test_user")

        # 验证
        assert result.open_id == "ou_test_user"
        assert result.name == "王五"
        assert result.job_title == "高级工程师"
        assert result.is_activated is True

    def test_get_user_empty_id(self, mock_client: MagicMock, config: FeishuConfig) -> None:
        """获取用户信息 user_id 为空。"""
        from ylhp_common_feishu_sdk.services.contact import ContactService

        service = ContactService(mock_client, config)

        with pytest.raises(FeishuValidationError):
            service.get_user(user_id="")

    def test_get_user_not_found(self, mock_client: MagicMock, config: FeishuConfig) -> None:
        """获取用户信息用户不存在。"""
        from ylhp_common_feishu_sdk.services.contact import ContactService

        # 准备用户不存在响应
        mock_client.contact.v3.user.get.return_value = make_error_response(
            99991663, "user not found"
        )

        # 执行并验证
        service = ContactService(mock_client, config)
        with pytest.raises(FeishuAuthError):
            service.get_user(user_id="ou_nonexistent")
