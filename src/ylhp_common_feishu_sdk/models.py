"""SDK 数据模型。

设计决策 — "入严出宽":
  - 入参（Pydantic BaseModel）: 调用 API 前严格校验
  - 出参（Pydantic BaseModel）: from_attributes=True 直接解析 lark-oapi 原生对象
  - frozen=True：保证不可变且可哈希
  - extra="ignore"：飞书 API 新增字段时静默忽略

关于嵌套对象的处理原则:
  - 跨接口多态、有真实 bug 风险 → 模型层建专用子模型防腐
  - 仅单接口普通嵌套 → Service 层手工处理，保持模型干净
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

# 出参模型统一配置
_OUT_CONFIG = ConfigDict(
    from_attributes=True,  # 直接解析 lark-oapi 原生对象
    extra="ignore",  # 飞书新增字段时静默忽略
    frozen=True,  # 不可变且可哈希
)


# ══════════════════════════════════════════
# 出参模型（宽容解析，不可变）
# ══════════════════════════════════════════


class AvatarObj(BaseModel):
    """lark-oapi avatar 嵌套对象的映射模型。

    存在理由：
    1. avatar 字段跨 OIDC（扁平字符串 avatar_url）和通讯录（嵌套对象 avatar.avatar_72）两个接口，数据结构多态
    2. frozen=True 模型若用 Any 字段存入不可哈希的 lark 原生对象，hash(user) 会抛 TypeError
    """

    model_config = _OUT_CONFIG
    avatar_72: str | None = Field(default=None, description="72x72 头像 URL")


class PageResult[T](BaseModel):
    """分页查询结果。"""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    items: list[T] = Field(description="当前页数据列表")
    page_token: str | None = Field(default=None, description="下一页分页标记")
    has_more: bool = Field(default=False, description="是否还有更多数据")


class UserInfo(BaseModel):
    """用户基本信息（H5 登录返回 / 部门员工列表条目）。

    Attributes:
        open_id: 用户的 open_id
        name: 用户姓名
        en_name: 英文名
        email: 邮箱
        mobile: 手机号
        tenant_key: 租户 key
        department_ids: 所属部门 ID 列表
        avatar_url: 头像 URL（computed_field，统一处理两种来源）
    """

    model_config = _OUT_CONFIG

    open_id: str = Field(description="用户的 open_id")
    name: str = Field(description="用户姓名")
    en_name: str | None = Field(default=None, description="用户英文名")
    email: str | None = Field(default=None, description="用户邮箱")
    mobile: str | None = Field(default=None, description="用户手机号")
    tenant_key: str | None = Field(default=None, description="租户 key")
    department_ids: list[str] = Field(default_factory=list, description="所属部门 ID 列表")

    # 通讯录接口返回嵌套对象 avatar.avatar_72，OIDC 接口直接返回扁平字符串 avatar_url
    # 两个隐藏字段分别捕获，computed_field 合并后对外统一暴露 avatar_url
    raw_avatar: AvatarObj | None = Field(
        default=None, alias="avatar", exclude=True, repr=False, description="头像嵌套对象"
    )
    raw_avatar_url: str | None = Field(
        default=None, alias="avatar_url", exclude=True, repr=False, description="头像 URL 字符串"
    )

    @computed_field
    @property
    def avatar_url(self) -> str | None:
        """头像 URL。优先取通讯录接口的 avatar.avatar_72，其次取 OIDC 接口的直接字符串。"""
        if self.raw_avatar and self.raw_avatar.avatar_72:
            return self.raw_avatar.avatar_72
        return self.raw_avatar_url


class Department(BaseModel):
    """部门信息。

    Attributes:
        department_id: 部门 ID
        open_department_id: 部门的 open_department_id
        name: 部门名称
        parent_department_id: 父部门 ID
        leader_user_id: 部门主管的用户 ID
        member_count: 部门成员数量
    """

    model_config = _OUT_CONFIG

    department_id: str = Field(description="部门 ID")
    open_department_id: str = Field(description="部门 open_department_id")
    name: str = Field(description="部门名称")
    parent_department_id: str | None = Field(default=None, description="父部门 ID")
    leader_user_id: str | None = Field(default=None, description="部门主管用户 ID")
    member_count: int | None = Field(default=None, description="部门成员数量")


class UserDetail(BaseModel):
    """用户详细信息（get_user 返回）。

    Attributes:
        open_id: 用户的 open_id
        name: 用户姓名
        en_name: 英文名
        email: 邮箱
        mobile: 手机号
        department_ids: 所属部门 ID 列表
        job_title: 职位
        is_activated: 是否已激活
        is_frozen: 是否已冻结
        is_resigned: 是否已离职
        avatar_url: 头像 URL
    """

    model_config = _OUT_CONFIG

    open_id: str = Field(description="用户的 open_id")
    name: str = Field(description="用户姓名")
    en_name: str | None = Field(default=None, description="用户英文名")
    email: str | None = Field(default=None, description="用户邮箱")
    mobile: str | None = Field(default=None, description="用户手机号")
    department_ids: list[str] = Field(default_factory=list, description="所属部门 ID 列表")
    job_title: str | None = Field(default=None, description="用户职位")

    # status 字段（is_activated/is_frozen/is_resigned）仅 get_user 一个接口涉及，
    # 普通嵌套，由 Service 层提取后直接传入，模型层不做特殊处理
    is_activated: bool | None = Field(default=None, description="是否已激活")
    is_frozen: bool | None = Field(default=None, description="是否已冻结")
    is_resigned: bool | None = Field(default=None, description="是否已离职")

    # avatar 同 UserInfo，需要防腐处理
    raw_avatar: AvatarObj | None = Field(
        default=None, alias="avatar", exclude=True, repr=False, description="头像嵌套对象"
    )

    @computed_field
    @property
    def avatar_url(self) -> str | None:
        """头像 URL。"""
        return self.raw_avatar.avatar_72 if self.raw_avatar else None


# ══════════════════════════════════════════
# 入参模型（严格校验）
# ══════════════════════════════════════════


class AuthorizeUrlParams(BaseModel):
    """构建授权 URL 的参数。

    Attributes:
        redirect_uri: 回调地址（必须以 http:// 或 https:// 开头）
        state: 状态参数（可选）
    """

    redirect_uri: str = Field(description="授权回调地址，须以 http:// 或 https:// 开头")
    state: str = Field(default="", description="自定义状态参数，用于防 CSRF 攻击")

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

    code: str = Field(description="飞书回调返回的临时授权码（一次性）")

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

    text: str = Field(description="文本消息内容")

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("消息文本不能为空")
        return v.strip()

    def to_json(self) -> str:
        """转换为 JSON 字符串。"""
        return json.dumps({"text": self.text}, ensure_ascii=False)


class CardContent(BaseModel):
    """卡片消息内容。

    Attributes:
        card: 卡片内容字典（不能为空）
    """

    card: dict[str, Any] = Field(description="卡片内容字典，遵循飞书卡片消息协议")

    @field_validator("card")
    @classmethod
    def validate_card(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not v:
            raise ValueError("卡片内容不能为空")
        return v

    def to_json(self) -> str:
        """转换为 JSON 字符串。"""
        return json.dumps(self.card, ensure_ascii=False)


class SendMessageRequest(BaseModel):
    """发送消息的统一入参。

    Attributes:
        receive_id: 接收者 ID
        receive_id_type: 接收者 ID 类型，默认 "open_id"
        msg_type: 消息类型
        content: 消息内容（JSON 字符串）
    """

    receive_id: str = Field(description="消息接收者 ID")
    receive_id_type: str = Field(default="open_id", description="接收者 ID 类型：open_id/user_id/union_id/chat_id/email")
    msg_type: str = Field(description="消息类型：text/interactive/image 等")
    content: str = Field(description="消息内容（JSON 字符串）")

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

    message_id: str = Field(description="被回复消息的 ID")
    text: str = Field(description="回复的文本内容")

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
        return json.dumps({"text": self.text}, ensure_ascii=False)
