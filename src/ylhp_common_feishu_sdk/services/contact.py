"""组织架构服务。

提供飞书通讯录 / 组织架构相关接口:
  - list_departments: 获取子部门列表（单页）
  - iter_departments: 部门自动翻页迭代器
  - list_department_users: 获取部门直属员工列表（单页）
  - iter_department_users: 员工自动翻页迭代器
  - get_user: 获取用户详细信息

飞书 API 映射:
  list_departments     → GET /contact/v3/departments/:id/children
                         client.contact.v3.department.children(req)
  list_department_users → GET /contact/v3/users/find_by_department
                          client.contact.v3.user.find_by_department(req)
  get_user             → GET /contact/v3/users/:user_id
                         client.contact.v3.user.get(req)

参考文档:
  - 获取子部门列表: https://open.feishu.cn/document/server-docs/contact-v3/department/children
  - 获取部门直属用户列表: https://open.feishu.cn/document/server-docs/contact-v3/user/find_by_department
  - 获取单个用户信息: https://open.feishu.cn/document/server-docs/contact-v3/user/get
"""

from __future__ import annotations

from collections.abc import Iterator

from lark_oapi.api.contact.v3 import (
    ChildrenDepartmentRequest,
    FindByDepartmentUserRequest,
    GetUserRequest,
)

from ylhp_common_feishu_sdk._retry import with_retry
from ylhp_common_feishu_sdk.exceptions import FeishuValidationError
from ylhp_common_feishu_sdk.models import Department, PageResult, UserDetail, UserInfo
from ylhp_common_feishu_sdk.services._base import BaseService

# ─── ContactService ───


class ContactService(BaseService):
    """组织架构服务。

    提供子部门列表、部门直属员工列表、用户详情三个核心接口。
    每个列表接口均有两个版本:
    - list_xxx: 单页查询，返回 PageResult，适合需要精确控制分页的场景
    - iter_xxx: 自动翻页迭代器，逐条产出，适合全量拉取

    Example:
        >>> from ylhp_common_feishu_sdk import Feishu
        >>> feishu = Feishu(app_id="xxx", app_secret="yyy")
        >>>
        >>> # 方式1: 自动翻页（推荐）
        >>> for dept in feishu.contacts.iter_departments():
        ...     print(dept.name, dept.open_department_id)
        >>>
        >>> # 方式2: 手动翻页
        >>> result = feishu.contacts.list_departments()
        >>> while result.has_more:
        ...     result = feishu.contacts.list_departments(
        ...         page_token=result.page_token
        ...     )
    """

    @with_retry
    def list_departments(
        self,
        parent_department_id: str = "0",
        page_size: int = 50,
        page_token: str | None = None,
        fetch_child: bool = False,
    ) -> PageResult[Department]:
        """获取子部门列表（单页）。

        使用飞书 API: GET /contact/v3/departments/:department_id/children
        lark-oapi 方法: client.contact.v3.department.children()

        Args:
            parent_department_id: 父部门 ID，默认 "0" 表示根部门
            page_size: 每页数量，1-50
            page_token: 分页标记
            fetch_child: 是否递归获取子部门

        Returns:
            PageResult[Department]，含 items、page_token、has_more

        Raises:
            FeishuValidationError: page_size 超出范围
            FeishuAuthError: 权限不足（不重试）
            FeishuServerError: 服务端错误（自动重试）

        Example:
            >>> result = feishu.contacts.list_departments()
            >>> for dept in result.items:
            ...     print(dept.name, dept.open_department_id)
        """
        if page_size < 1 or page_size > 50:
            raise FeishuValidationError("page_size", "page_size 须在 1-50 之间")

        self._log_call(
            "list_departments",
            parent_department_id=parent_department_id,
            page_size=page_size,
        )

        builder = (
            ChildrenDepartmentRequest.builder()
            .department_id(parent_department_id)
            .page_size(page_size)
            .department_id_type("open_department_id")
            .fetch_child(fetch_child)
        )
        if page_token:
            builder = builder.page_token(page_token)

        req = builder.build()
        resp = self._client.contact.v3.department.children(req)
        self._check_response(resp, "list_departments")

        items: list[Department] = []
        if resp.data and resp.data.items:
            for dept in resp.data.items:
                items.append(
                    Department(
                        department_id=dept.department_id,
                        open_department_id=dept.open_department_id,
                        name=dept.name,
                        parent_department_id=getattr(dept, "parent_department_id", None),
                        leader_user_id=getattr(dept, "leader_user_id", None),
                        member_count=getattr(dept, "member_count", None),
                    )
                )

        return PageResult(
            items=items,
            page_token=getattr(resp.data, "page_token", None),
            has_more=getattr(resp.data, "has_more", False),
        )

    def iter_departments(
        self,
        parent_department_id: str = "0",
        page_size: int = 50,
        fetch_child: bool = False,
    ) -> Iterator[Department]:
        """自动翻页获取全部子部门（生成器）。

        内部自动处理分页，调用者无需关心 page_token。
        每页请求均由 list_departments 发出（含重试逻辑）。

        Args:
            parent_department_id: 父部门 ID，默认 "0" 表示根部门
            page_size: 每页数量
            fetch_child: 是否递归获取子部门

        Yields:
            Department 对象

        Example:
            >>> for dept in feishu.contacts.iter_departments():
            ...     print(dept.name, dept.open_department_id)
        """
        page_token: str | None = None
        while True:
            result = self.list_departments(
                parent_department_id=parent_department_id,
                page_size=page_size,
                page_token=page_token,
                fetch_child=fetch_child,
            )
            yield from result.items
            if not result.has_more:
                break
            page_token = result.page_token

    @with_retry
    def list_department_users(
        self,
        department_id: str,
        page_size: int = 50,
        page_token: str | None = None,
    ) -> PageResult[UserInfo]:
        """获取部门直属员工列表（单页）。

        使用飞书 API: GET /contact/v3/users/find_by_department
        lark-oapi 方法: client.contact.v3.user.find_by_department()

        Args:
            department_id: 部门的 open_department_id
            page_size: 每页数量，1-50
            page_token: 分页标记

        Returns:
            PageResult[UserInfo]

        Raises:
            FeishuValidationError: department_id 为空或 page_size 超出范围

        Example:
            >>> result = feishu.contacts.list_department_users("od_xxx")
            >>> for user in result.items:
            ...     print(user.name, user.open_id)
        """
        if not department_id or not department_id.strip():
            raise FeishuValidationError("department_id", "department_id 不能为空")
        if page_size < 1 or page_size > 50:
            raise FeishuValidationError("page_size", "page_size 须在 1-50 之间")

        self._log_call("list_department_users", department_id=department_id)

        builder = (
            FindByDepartmentUserRequest.builder()
            .department_id(department_id)
            .page_size(page_size)
            .department_id_type("open_department_id")
            .user_id_type("open_id")
        )
        if page_token:
            builder = builder.page_token(page_token)

        req = builder.build()
        resp = self._client.contact.v3.user.find_by_department(req)
        self._check_response(resp, "list_department_users")

        items: list[UserInfo] = []
        if resp.data and resp.data.items:
            for user in resp.data.items:
                avatar = getattr(user, "avatar", None)
                items.append(
                    UserInfo(
                        open_id=user.open_id,
                        name=user.name,
                        en_name=getattr(user, "en_name", None),
                        avatar_url=getattr(avatar, "avatar_72", None) if avatar else None,
                        email=getattr(user, "email", None),
                        mobile=getattr(user, "mobile", None),
                        tenant_key=getattr(user, "tenant_key", None),
                        department_ids=getattr(user, "department_ids", []),
                    )
                )

        return PageResult(
            items=items,
            page_token=getattr(resp.data, "page_token", None),
            has_more=getattr(resp.data, "has_more", False),
        )

    def iter_department_users(
        self,
        department_id: str,
        page_size: int = 50,
    ) -> Iterator[UserInfo]:
        """自动翻页获取部门全部直属员工（生成器）。

        Args:
            department_id: 部门的 open_department_id
            page_size: 每页数量

        Yields:
            UserInfo 对象

        Example:
            >>> for user in feishu.contacts.iter_department_users("od_xxx"):
            ...     print(user.name, user.open_id)
        """
        page_token: str | None = None
        while True:
            result = self.list_department_users(
                department_id=department_id,
                page_size=page_size,
                page_token=page_token,
            )
            yield from result.items
            if not result.has_more:
                break
            page_token = result.page_token

    @with_retry
    def get_user(
        self,
        user_id: str,
        user_id_type: str = "open_id",
    ) -> UserDetail:
        """获取用户详细信息。

        使用飞书 API: GET /contact/v3/users/:user_id
        lark-oapi 方法: client.contact.v3.user.get()

        Args:
            user_id: 用户 ID
            user_id_type: ID 类型，默认 "open_id"

        Returns:
            UserDetail 对象

        Raises:
            FeishuValidationError: user_id 为空

        Example:
            >>> user = feishu.contacts.get_user("ou_xxx")
            >>> print(user.name, user.is_activated)
        """
        if not user_id or not user_id.strip():
            raise FeishuValidationError("user_id", "user_id 不能为空")

        self._log_call("get_user", user_id=user_id)

        req = (
            GetUserRequest.builder()
            .user_id(user_id)
            .user_id_type(user_id_type)
            .department_id_type("open_department_id")
            .build()
        )

        resp = self._client.contact.v3.user.get(req)
        self._check_response(resp, "get_user")

        user = resp.data.user
        avatar = getattr(user, "avatar", None)
        status = getattr(user, "status", None)

        return UserDetail(
            open_id=user.open_id,
            name=user.name,
            en_name=getattr(user, "en_name", None),
            avatar_url=getattr(avatar, "avatar_72", None) if avatar else None,
            email=getattr(user, "email", None),
            mobile=getattr(user, "mobile", None),
            department_ids=getattr(user, "department_ids", []),
            job_title=getattr(user, "job_title", None),
            is_activated=getattr(status, "is_activated", None) if status else None,
            is_frozen=getattr(status, "is_frozen", None) if status else None,
            is_resigned=getattr(status, "is_resigned", None) if status else None,
        )
