"""假勤审批查询服务。

提供飞书假勤系统相关接口:
  - query_user_approvals: 查询员工假勤审批记录（请假/出差/外出/加班）

飞书 API 映射:
  query_user_approvals → POST /attendance/v1/user_approvals/query
                          client.attendance.v1.user_approval.query(req)

参考文档:
  - 查询审批信息: https://open.feishu.cn/document/server-docs/attendance-v1/user_approval/query

设计决策:
  - 内部按 50 个用户分批，对调用方透明
  - 批次级重试（不使用 @with_retry 装饰器，因为装饰器是方法级粒度）
  - 任意批次重试后仍失败 → 抛出 FeishuServerError，不返回部分结果
  - status 参数不做范围校验，直接透传（避免飞书新增状态码导致 SDK 不兼容）
  - 响应展平：每个 user_approval 下的 leaves / trips / out / overtime_works
    均展平为独立的 UserApproval 记录
"""

from __future__ import annotations

import datetime
import logging
import time
from typing import Any

from lark_oapi.api.attendance.v1 import (
    QueryUserApprovalRequest,
    QueryUserApprovalRequestBody,
)

from ylhp_common_feishu_sdk.exceptions import (
    FeishuRateLimitError,
    FeishuServerError,
    FeishuValidationError,
)
from ylhp_common_feishu_sdk.models import UserApproval
from ylhp_common_feishu_sdk.services._base import BaseService

logger = logging.getLogger("ylhp_common_feishu_sdk")

_BATCH_SIZE = 50
_MAX_USER_IDS = 500
# 飞书考勤 API employee_type 合法值：employee_id / employee_no / open_id
# union_id 仅通讯录等其他模块支持，考勤 API 不支持
# 需求文档 Section 3 将第三个值写为 "user_id"，属于笔误，以飞书官方 API 文档为准
_VALID_USER_ID_TYPES = frozenset({"open_id", "employee_id", "employee_no"})

# 飞书考勤 API unit 字段（int 枚举）→ SDK 语义字符串
_UNIT_MAP: dict[int, str] = {
    1: "day",
    2: "hour",
    3: "half_day",
    4: "half_hour",
}


class AttendanceService(BaseService):
    """假勤审批查询服务。

    提供查询员工假勤审批记录的接口，内部自动处理批次拆分和合并。

    Example:
        >>> from ylhp_common_feishu_sdk import Feishu
        >>> from datetime import date
        >>> feishu = Feishu(app_id="xxx", app_secret="yyy")
        >>>
        >>> # 查询明日请假员工（用于排班计算）
        >>> approvals = feishu.attendance.query_user_approvals(
        ...     user_ids=["ou_xxx", "ou_yyy"],
        ...     check_date_from=date.today(),
        ...     check_date_to=date.today(),
        ... )
        >>> exempt = {a.user_id for a in approvals if a.approval_status == 1}
    """

    def query_user_approvals(
        self,
        user_ids: list[str],
        check_date_from: datetime.date | str,
        check_date_to: datetime.date | str,
        status: int | None = None,
        user_id_type: str = "open_id",
    ) -> list[UserApproval]:
        """查询员工假勤审批记录。

        内部自动将 user_ids 按 50 个分批查询，合并结果后返回。
        任意批次重试后仍失败时，整个调用失败（不返回部分结果）。

        Args:
            user_ids: 员工 ID 列表，非空，最多 500 个。
                SDK 内部自动分批，调用方无需关心批次大小。
            check_date_from: 查询起始日期（含），支持 datetime.date 对象
                或 "YYYYMMDD" 格式字符串（如 "20260314"）。
            check_date_to: 查询结束日期（含），须 >= check_date_from。
                支持 datetime.date 对象或 "YYYYMMDD" 格式字符串。
            status: 按审批状态过滤。None 返回全部状态。
                已知值：0=待审批, 1=未通过, 2=已通过, 3=已撤回, 4=已撤销。
                不校验具体值，直接透传给飞书 API。
            user_id_type: 用户 ID 类型，默认 "open_id"。
                可选值："open_id" / "employee_id" / "employee_no"。

        Returns:
            UserApproval 列表，按 (user_id, approval_date, approval_type) 去重。
            无审批记录时返回空列表 []（不报错）。

        Raises:
            FeishuValidationError: 参数校验失败时抛出：
                - user_ids 为空
                - user_ids 超过 500 个
                - check_date_to < check_date_from
                - user_id_type 不合法
                - 日期字符串格式不符合 YYYYMMDD
            FeishuServerError: 任意批次重试后仍失败（不返回部分结果）
            FeishuRateLimitError: 超出飞书限流且重试次数耗尽
            FeishuAuthError: 权限不足（不重试）
            FeishuAPIError: 其他飞书业务错误（不重试）

        Example:
            >>> # 查询昨日漏写检测（三向比对中的豁免判断）
            >>> from datetime import date, timedelta
            >>> yesterday = date.today() - timedelta(days=1)
            >>> approvals = feishu.attendance.query_user_approvals(
            ...     user_ids=scheduled_open_ids,
            ...     check_date_from=yesterday,
            ...     check_date_to=yesterday,
            ... )
            >>> late_exempt = {
            ...     a.user_id for a in approvals
            ...     if a.approval_status == 2  # 飞书官方 status 枚举：2=已通过
            ...     and a.approval_type in ("leave", "business_trip", "external_visit")
            ... }
        """
        # ── 1. 参数校验 ──────────────────────────────────────────────
        if not user_ids:
            raise FeishuValidationError("user_ids", "user_ids 不能为空")
        if len(user_ids) > _MAX_USER_IDS:
            raise FeishuValidationError(
                "user_ids", f"user_ids 最多 {_MAX_USER_IDS} 个，当前 {len(user_ids)} 个"
            )
        if user_id_type not in _VALID_USER_ID_TYPES:
            raise FeishuValidationError(
                "user_id_type",
                f"user_id_type 须为 {sorted(_VALID_USER_ID_TYPES)} 之一，当前值：{user_id_type!r}",
            )

        date_from_int = _normalize_date(check_date_from, "check_date_from")
        date_to_int = _normalize_date(check_date_to, "check_date_to")

        if date_to_int < date_from_int:
            raise FeishuValidationError(
                "check_date_to",
                f"check_date_to ({date_to_int}) 不能早于 check_date_from ({date_from_int})",
            )

        self._log_call(
            "query_user_approvals",
            user_id_count=len(user_ids),
            check_date_from=date_from_int,
            check_date_to=date_to_int,
            status=status,
            user_id_type=user_id_type,
        )

        # ── 2. 批次查询 ───────────────────────────────────────────────
        batches = [
            user_ids[i : i + _BATCH_SIZE]
            for i in range(0, len(user_ids), _BATCH_SIZE)
        ]
        total_batches = len(batches)

        all_approvals: list[UserApproval] = []
        for batch_idx, batch in enumerate(batches):
            batch_result = self._query_batch_with_retry(
                batch_user_ids=batch,
                date_from=date_from_int,
                date_to=date_to_int,
                status=status,
                user_id_type=user_id_type,
                batch_idx=batch_idx,
                total_batches=total_batches,
            )
            all_approvals.extend(batch_result)

        # ── 3. 去重后返回 ─────────────────────────────────────────────
        return _deduplicate(all_approvals)

    # ─── 内部方法 ────────────────────────────────────────────────────

    def _query_batch_with_retry(
        self,
        batch_user_ids: list[str],
        date_from: int,
        date_to: int,
        status: int | None,
        user_id_type: str,
        batch_idx: int,
        total_batches: int,
    ) -> list[UserApproval]:
        """单批次查询，含批次级重试逻辑。

        重试策略与 @with_retry 装饰器一致：
        - FeishuRateLimitError: 优先使用 retry_after，否则指数退避
        - FeishuServerError: 指数退避
        - 其他异常（FeishuAuthError 等）: 立即抛出，不重试

        任意批次最终失败后，抛出 FeishuServerError（不返回部分结果）。
        """
        max_retries: int = self._config.max_retries
        base_wait: float = self._config.retry_wait_seconds
        last_exc: FeishuServerError | FeishuRateLimitError | None = None

        for attempt in range(max_retries + 1):
            try:
                return self._query_single_batch(
                    batch_user_ids, date_from, date_to, status, user_id_type
                )
            except (FeishuServerError, FeishuRateLimitError) as e:
                last_exc = e
                if attempt >= max_retries:
                    break
                if isinstance(e, FeishuRateLimitError) and e.retry_after:
                    wait_secs = e.retry_after
                else:
                    wait_secs = base_wait * (2**attempt)
                logger.debug(
                    "批次 %d/%d 第 %d 次重试，等待 %.2fs: %s",
                    batch_idx + 1,
                    total_batches,
                    attempt + 1,
                    wait_secs,
                    e,
                )
                time.sleep(wait_secs)

        logger.warning(
            "批次 %d/%d 重试 %d 次后仍失败，整个调用终止",
            batch_idx + 1,
            total_batches,
            max_retries,
        )
        # 保留原始异常类型：429 耗尽时抛 FeishuRateLimitError，5xx 耗尽时抛 FeishuServerError
        # 调用方可通过异常类型区分"被限流"和"服务端崩溃"
        if isinstance(last_exc, FeishuRateLimitError):
            raise last_exc
        raise FeishuServerError(
            code=getattr(last_exc, "code", -1),
            msg=f"批次 {batch_idx + 1}/{total_batches} 重试 {max_retries} 次后仍失败: {last_exc}",
        )

    def _query_single_batch(
        self,
        user_ids: list[str],
        date_from: int,
        date_to: int,
        status: int | None,
        user_id_type: str,
    ) -> list[UserApproval]:
        """单次 API 调用（无重试），返回展平后的 UserApproval 列表。"""
        body_builder = (
            QueryUserApprovalRequestBody.builder()
            .user_ids(user_ids)
            .check_date_from(date_from)
            .check_date_to(date_to)
        )
        if status is not None:
            body_builder = body_builder.status(status)

        req = (
            QueryUserApprovalRequest.builder()
            .employee_type(user_id_type)
            .request_body(body_builder.build())
            .build()
        )

        resp = self._client.attendance.v1.user_approval.query(req)
        self._check_response(resp, "query_user_approvals")

        raw_list = getattr(resp.data, "user_approvals", None) or []
        return _parse_user_approvals(raw_list)


# ─── 模块级工具函数 ───────────────────────────────────────────────────


def _normalize_date(date_input: datetime.date | str, field_name: str) -> int:
    """将日期输入统一转换为飞书 API 要求的 int 格式（yyyyMMdd）。

    Args:
        date_input: datetime.date 对象，或 "YYYYMMDD" 格式字符串
        field_name: 字段名（用于错误消息）

    Returns:
        int 类型日期，如 20260314

    Raises:
        FeishuValidationError: 输入类型不支持或格式/值不合法
    """
    if isinstance(date_input, datetime.date):
        return int(date_input.strftime("%Y%m%d"))

    if isinstance(date_input, str):
        if len(date_input) != 8 or not date_input.isdigit():
            raise FeishuValidationError(
                field_name, f"日期字符串格式须为 YYYYMMDD（8位纯数字），当前值：{date_input!r}"
            )
        try:
            datetime.date(
                int(date_input[:4]),
                int(date_input[4:6]),
                int(date_input[6:8]),
            )
        except ValueError as e:
            raise FeishuValidationError(
                field_name, f"无效日期：{date_input!r}"
            ) from e
        return int(date_input)

    raise FeishuValidationError(
        field_name, f"日期类型须为 datetime.date 或 YYYYMMDD 字符串，当前类型：{type(date_input).__name__}"
    )


def _parse_date_str(date_str: str) -> datetime.date:
    """将飞书返回的 yyyyMMdd 字符串解析为 datetime.date。"""
    return datetime.date(
        int(date_str[:4]),
        int(date_str[4:6]),
        int(date_str[6:8]),
    )


def _infer_approval_status(item: Any) -> int | None:
    """从 approve_pass_time 推断审批状态。

    飞书考勤 API 响应体不含 approval_status 字段。
    approve_pass_time 非空字符串 → 2（已通过，对齐飞书官方 status 枚举）。
    为空或不存在 → None（状态未知，常见于 outs/trips 的待审批记录）。
    overtime_works 无 approve_pass_time 字段，始终返回 None。
    """
    pass_time = getattr(item, "approve_pass_time", None)
    if pass_time and isinstance(pass_time, str) and pass_time.strip():
        return 2
    return None


def _parse_user_approvals(raw_list: list[Any]) -> list[UserApproval]:
    """将飞书 API 响应的 user_approvals 展平为 UserApproval 列表。

    飞书响应结构：每个 user_approval 包含 user_id、date 以及四种审批类型的子列表：
      - leaves          → approval_type = "leave"
      - trips           → approval_type = "business_trip"
      - outs            → approval_type = "external_visit"
      - overtime_works  → approval_type = "overtime"

    每个子项独立展平为一条 UserApproval 记录。
    approval_status 从 approve_pass_time 推断（飞书响应体不含该字段）。
    """
    result: list[UserApproval] = []

    _TYPE_ATTR_MAP = (
        ("leaves", "leave"),
        ("trips", "business_trip"),
        ("outs", "external_visit"),
        ("overtime_works", "overtime"),
    )

    for ua in raw_list:
        user_id: str = ua.user_id
        # 飞书返回 yyyyMMdd 字符串
        approval_date: datetime.date = _parse_date_str(ua.date)

        for attr_name, approval_type in _TYPE_ATTR_MAP:
            items = getattr(ua, attr_name, None) or []
            for item in items:
                result.append(
                    UserApproval(
                        user_id=user_id,
                        approval_date=approval_date,
                        approval_type=approval_type,
                        approval_status=_infer_approval_status(item),
                        start_time=getattr(item, "start_time", ""),
                        end_time=getattr(item, "end_time", ""),
                        reason=getattr(item, "reason", None) or None,
                        leave_type=getattr(item, "leave_type", None) or None,
                        time_unit=_UNIT_MAP.get(getattr(item, "unit", None)),
                        duration=getattr(item, "duration", None),
                        # leaves/outs 无 duration 字段（interval 单位为秒，语义不同，不映射）
                    )
                )

    return result


def _deduplicate(approvals: list[UserApproval]) -> list[UserApproval]:
    """按 (user_id, approval_date, approval_type) 去重，保留首次出现的记录。"""
    seen: set[tuple[str, datetime.date, str]] = set()
    result: list[UserApproval] = []
    for approval in approvals:
        key = (approval.user_id, approval.approval_date, approval.approval_type)
        if key not in seen:
            seen.add(key)
            result.append(approval)
    return result
