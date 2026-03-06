"""SDK 数据模型。

设计决策 — "进严出宽":
  - 入参（Pydantic BaseModel）: 调用 API 前严格校验
  - 出参（dataclass）: 从 API 响应构造，使用 getattr 兜底
  - dataclass 比 Pydantic 轻量，且可以用 frozen=True 保证不可变
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, field_validator

# === 出参 dataclass（从 API 响应构造）===


@dataclass(frozen=True)
class PageResult[T]:
    """分页查询结果。

    Attributes:
        items: 当前页的数据列表
        page_token: 下一页的分页标记（无下一页时为 None）
        has_more: 是否还有更多数据
    """

    items: list[T]
    page_token: str | None = None
    has_more: bool = False


@dataclass(frozen=True)
class UserInfo:
    """用户基本信息（Auth 和 Contact 共用）。

    Attributes:
        open_id: 用户的 open_id
        name: 用户姓名
        en_name: 英文名
        avatar_url: 头像 URL
        email: 邮箱
        mobile: 手机号
        tenant_key: 租户 key
        department_ids: 所属部门 ID 列表
    """

    open_id: str
    name: str
    en_name: str | None = None
    avatar_url: str | None = None
    email: str | None = None
    mobile: str | None = None
    tenant_key: str | None = None
    department_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Department:
    """部门信息。

    Attributes:
        department_id: 部门 ID
        open_department_id: 部门的 open_department_id
        name: 部门名称
        parent_department_id: 父部门 ID
        leader_user_id: 部门主管的用户 ID
        member_count: 部门成员数量
    """

    department_id: str
    open_department_id: str
    name: str
    parent_department_id: str | None = None
    leader_user_id: str | None = None
    member_count: int | None = None


@dataclass(frozen=True)
class UserDetail:
    """用户详细信息（get_user 返回）。

    Attributes:
        open_id: 用户的 open_id
        name: 用户姓名
        en_name: 英文名
        avatar_url: 头像 URL
        email: 邮箱
        mobile: 手机号
        department_ids: 所属部门 ID 列表
        job_title: 职位
        is_activated: 是否已激活
        is_frozen: 是否已冻结
        is_resigned: 是否已离职
    """

    open_id: str
    name: str
    en_name: str | None = None
    avatar_url: str | None = None
    email: str | None = None
    mobile: str | None = None
    department_ids: list[str] = field(default_factory=list)
    job_title: str | None = None
    is_activated: bool | None = None
    is_frozen: bool | None = None
    is_resigned: bool | None = None


# === 入参 Pydantic（调用前严格校验）===


class AuthorizeUrlParams(BaseModel):
    """构建授权 URL 的参数。

    Attributes:
        redirect_uri: 回调地址（必须以 http:// 或 https:// 开头）
        state: 状态参数（可选）
    """

    redirect_uri: str
    state: str = ""

    @field_validator("redirect_uri")
    @classmethod
    def validate_redirect_uri(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("必须以 http:// 或 https:// 开头")
        return v


class AuthCodeRequest(BaseModel):
    """授权码请求参数。

    Attributes:
        code: 授权码（不能为空）
    """

    code: str

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("授权码不能为空")
        return v.strip()


# === Messaging 入参模型 ===


class TextContent(BaseModel):
    """文本消息内容。

    Attributes:
        text: 文本内容（不能为空）
    """

    text: str

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("消息文本不能为空")
        return v.strip()

    def to_json(self) -> str:
        """转换为 JSON 字符串。"""
        import json

        return json.dumps({"text": self.text}, ensure_ascii=False)


class CardContent(BaseModel):
    """卡片消息内容。

    Attributes:
        card: 卡片内容字典（不能为空）
    """

    card: dict[str, Any]

    @field_validator("card")
    @classmethod
    def validate_card(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not v:
            raise ValueError("卡片内容不能为空")
        return v

    def to_json(self) -> str:
        """转换为 JSON 字符串。"""
        import json

        return json.dumps(self.card, ensure_ascii=False)


class SendMessageRequest(BaseModel):
    """发送消息的统一入参。

    Attributes:
        receive_id: 接收者 ID
        receive_id_type: 接收者 ID 类型，默认 "open_id"
        msg_type: 消息类型
        content: 消息内容（JSON 字符串）
    """

    receive_id: str
    receive_id_type: str = "open_id"
    msg_type: str
    content: str

    @field_validator("receive_id")
    @classmethod
    def validate_receive_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("接收者 ID 不能为空")
        return v.strip()


class ReplyTextRequest(BaseModel):
    """回复消息的入参。

    Attributes:
        message_id: 被回复消息的 ID
        text: 回复的文本内容
    """

    message_id: str
    text: str

    @field_validator("message_id")
    @classmethod
    def validate_message_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("消息 ID 不能为空")
        return v.strip()

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("回复文本不能为空")
        return v.strip()

    def to_content_json(self) -> str:
        """转换文本内容为 JSON 字符串。"""
        import json

        return json.dumps({"text": self.text}, ensure_ascii=False)
