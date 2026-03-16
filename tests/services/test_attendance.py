"""测试 Attendance 服务。

测试用例覆盖:
- query_user_approvals: 假勤审批查询
  - 单批次（≤50 用户）
  - 多批次（120 用户 → 3 次请求）
  - user_ids 为空 → FeishuValidationError
  - user_ids 超过 500 → FeishuValidationError
  - check_date_to < check_date_from → FeishuValidationError
  - user_id_type 不合法 → FeishuValidationError
  - 日期字符串格式错误 → FeishuValidationError
  - 返回空列表（无审批记录，不报错）
  - 5xx 触发重试并最终成功
  - 429 触发重试并最终成功
  - 批次重试后仍失败 → FeishuServerError（全部回滚，不返回部分结果）
  - datetime.date 对象输入
  - YYYYMMDD 字符串输入
  - status 参数透传
  - 多类型审批展平（leave / business_trip / external_visit / overtime）
  - 去重逻辑
"""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

from ylhp_common_feishu_sdk.config import FeishuConfig
from ylhp_common_feishu_sdk.exceptions import (
    FeishuRateLimitError,
    FeishuServerError,
    FeishuValidationError,
)

# ─── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def config() -> FeishuConfig:
    """测试配置：重试次数少，等待时间极短（加速测试）。"""
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


# ─── 响应构建 Helper ─────────────────────────────────────────────────


def make_leave_item(
    approval_status: int = 1,
    start_time: str = "2026-03-14 09:00:00",
    end_time: str = "2026-03-14 18:00:00",
    leave_type: str | None = "annual_leave",
    reason: str | None = "年假",
    duration: float | None = 1.0,
    duration_unit: str | None = "day",
) -> MagicMock:
    """创建请假子项 mock。"""
    item = MagicMock()
    item.approval_status = approval_status
    item.start_time = start_time
    item.end_time = end_time
    item.leave_type = leave_type
    item.reason = reason
    item.duration = duration
    item.duration_unit = duration_unit
    item.approve_pass_time = "2026-03-14 12:00:00" if approval_status == 1 else ""
    return item


def make_trip_item(
    approval_status: int = 1,
    start_time: str = "2026-03-15 09:00:00",
    end_time: str = "2026-03-15 18:00:00",
) -> MagicMock:
    """创建出差子项 mock。"""
    item = MagicMock()
    item.approval_status = approval_status
    item.start_time = start_time
    item.end_time = end_time
    item.reason = None
    item.leave_type = None
    item.duration = None
    item.duration_unit = None
    item.approve_pass_time = "2026-03-15 12:00:00" if approval_status == 1 else ""
    return item


def make_user_approval_item(
    user_id: str = "ou_user1",
    date: str = "20260314",
    leaves: list[Any] | None = None,
    trips: list[Any] | None = None,
    outs: list[Any] | None = None,
    overtime_works: list[Any] | None = None,
) -> MagicMock:
    """创建 user_approval 响应项 mock。"""
    item = MagicMock()
    item.user_id = user_id
    item.date = date
    item.leaves = leaves or []
    item.trips = trips or []
    item.outs = outs or []
    item.overtime_works = overtime_works or []
    return item


def make_success_response(user_approvals: list[Any] | None = None) -> MagicMock:
    """创建成功响应 mock。"""
    resp = MagicMock()
    resp.success = True
    resp.code = 0
    resp.msg = "success"
    resp.data = MagicMock()
    resp.data.user_approvals = user_approvals or []
    return resp


def make_error_response(code: int, msg: str) -> MagicMock:
    """创建错误响应 mock。"""
    resp = MagicMock()
    resp.success = False
    resp.code = code
    resp.msg = msg
    resp.log_id = f"log_{code}"
    return resp


# ─── 测试类：参数校验 ─────────────────────────────────────────────────


class TestQueryUserApprovalsValidation:
    """测试 query_user_approvals 参数校验。"""

    def test_empty_user_ids_raises(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """user_ids 为空 → FeishuValidationError。"""
        from ylhp_common_feishu_sdk.services.attendance import AttendanceService

        service = AttendanceService(mock_client, config)
        with pytest.raises(FeishuValidationError) as exc_info:
            service.query_user_approvals(
                user_ids=[],
                check_date_from="20260314",
                check_date_to="20260314",
            )
        assert exc_info.value.field == "user_ids"

    def test_user_ids_exceeds_500_raises(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """user_ids 超过 500 → FeishuValidationError。"""
        from ylhp_common_feishu_sdk.services.attendance import AttendanceService

        service = AttendanceService(mock_client, config)
        with pytest.raises(FeishuValidationError) as exc_info:
            service.query_user_approvals(
                user_ids=[f"ou_{i}" for i in range(501)],
                check_date_from="20260314",
                check_date_to="20260314",
            )
        assert exc_info.value.field == "user_ids"

    def test_date_to_before_date_from_raises(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """check_date_to < check_date_from → FeishuValidationError。"""
        from ylhp_common_feishu_sdk.services.attendance import AttendanceService

        service = AttendanceService(mock_client, config)
        with pytest.raises(FeishuValidationError) as exc_info:
            service.query_user_approvals(
                user_ids=["ou_user1"],
                check_date_from="20260314",
                check_date_to="20260313",
            )
        assert exc_info.value.field == "check_date_to"

    def test_invalid_user_id_type_raises(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """user_id_type 不合法 → FeishuValidationError。"""
        from ylhp_common_feishu_sdk.services.attendance import AttendanceService

        service = AttendanceService(mock_client, config)
        with pytest.raises(FeishuValidationError) as exc_info:
            service.query_user_approvals(
                user_ids=["ou_user1"],
                check_date_from="20260314",
                check_date_to="20260314",
                user_id_type="invalid_type",
            )
        assert exc_info.value.field == "user_id_type"

    def test_invalid_date_string_format_raises(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """日期字符串不是 YYYYMMDD 格式 → FeishuValidationError。"""
        from ylhp_common_feishu_sdk.services.attendance import AttendanceService

        service = AttendanceService(mock_client, config)
        with pytest.raises(FeishuValidationError):
            service.query_user_approvals(
                user_ids=["ou_user1"],
                check_date_from="2026-03-14",  # 含连字符，不是 YYYYMMDD
                check_date_to="20260314",
            )

    def test_invalid_date_value_raises(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """日期字符串格式正确但值不合法 → FeishuValidationError。"""
        from ylhp_common_feishu_sdk.services.attendance import AttendanceService

        service = AttendanceService(mock_client, config)
        with pytest.raises(FeishuValidationError):
            service.query_user_approvals(
                user_ids=["ou_user1"],
                check_date_from="20261399",  # 13 月 99 日
                check_date_to="20261399",
            )


# ─── 测试类：日期格式转换 ─────────────────────────────────────────────


class TestDateNormalization:
    """测试日期输入格式转换。"""

    def test_date_object_input(self, mock_client: MagicMock, config: FeishuConfig) -> None:
        """datetime.date 对象输入 → 转换为 int 传给 API。"""
        from ylhp_common_feishu_sdk.services.attendance import AttendanceService

        mock_client.attendance.v1.user_approval.query.return_value = make_success_response()

        service = AttendanceService(mock_client, config)
        service.query_user_approvals(
            user_ids=["ou_user1"],
            check_date_from=datetime.date(2026, 3, 14),
            check_date_to=datetime.date(2026, 3, 14),
        )

        # 验证 API 被调用（日期转换后 int 传入）
        mock_client.attendance.v1.user_approval.query.assert_called_once()

    def test_yyyymmdd_string_input(self, mock_client: MagicMock, config: FeishuConfig) -> None:
        """YYYYMMDD 字符串输入 → 正常调用 API。"""
        from ylhp_common_feishu_sdk.services.attendance import AttendanceService

        mock_client.attendance.v1.user_approval.query.return_value = make_success_response()

        service = AttendanceService(mock_client, config)
        service.query_user_approvals(
            user_ids=["ou_user1"],
            check_date_from="20260314",
            check_date_to="20260314",
        )

        mock_client.attendance.v1.user_approval.query.assert_called_once()

    def test_date_same_from_and_to(self, mock_client: MagicMock, config: FeishuConfig) -> None:
        """check_date_from == check_date_to → 合法（同日查询）。"""
        from ylhp_common_feishu_sdk.services.attendance import AttendanceService

        mock_client.attendance.v1.user_approval.query.return_value = make_success_response()

        service = AttendanceService(mock_client, config)
        result = service.query_user_approvals(
            user_ids=["ou_user1"],
            check_date_from="20260314",
            check_date_to="20260314",
        )
        assert result == []


# ─── 测试类：单批次正常查询 ───────────────────────────────────────────


class TestQuerySingleBatch:
    """测试单批次查询（≤50 用户）。"""

    def test_single_batch_empty_result(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """有效参数但无审批记录 → 返回空列表（不报错）。"""
        from ylhp_common_feishu_sdk.services.attendance import AttendanceService

        mock_client.attendance.v1.user_approval.query.return_value = make_success_response(
            user_approvals=[]
        )

        service = AttendanceService(mock_client, config)
        result = service.query_user_approvals(
            user_ids=["ou_user1", "ou_user2"],
            check_date_from="20260314",
            check_date_to="20260314",
        )

        assert result == []
        mock_client.attendance.v1.user_approval.query.assert_called_once()

    def test_single_batch_with_leave(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """单批次，有请假记录 → 返回对应 UserApproval。"""
        from ylhp_common_feishu_sdk.services.attendance import AttendanceService

        leave = make_leave_item(approval_status=1, leave_type="annual_leave")
        ua = make_user_approval_item(user_id="ou_user1", date="20260314", leaves=[leave])
        mock_client.attendance.v1.user_approval.query.return_value = make_success_response(
            [ua]
        )

        service = AttendanceService(mock_client, config)
        result = service.query_user_approvals(
            user_ids=["ou_user1"],
            check_date_from="20260314",
            check_date_to="20260314",
        )

        assert len(result) == 1
        assert result[0].user_id == "ou_user1"
        assert result[0].approval_type == "leave"
        assert result[0].approval_status == 2  # approve_pass_time 非空 → 推断为 2（已通过）
        assert result[0].approval_date == datetime.date(2026, 3, 14)
        assert result[0].leave_type == "annual_leave"

    def test_single_batch_multiple_types(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """同一用户有多种审批类型 → 全部展平返回。"""
        from ylhp_common_feishu_sdk.services.attendance import AttendanceService

        leave = make_leave_item(approval_status=1)
        trip = make_trip_item(approval_status=1)
        ua = make_user_approval_item(
            user_id="ou_user1", date="20260314", leaves=[leave], trips=[trip]
        )
        mock_client.attendance.v1.user_approval.query.return_value = make_success_response(
            [ua]
        )

        service = AttendanceService(mock_client, config)
        result = service.query_user_approvals(
            user_ids=["ou_user1"],
            check_date_from="20260314",
            check_date_to="20260314",
        )

        assert len(result) == 2
        types = {r.approval_type for r in result}
        assert types == {"leave", "business_trip"}

    def test_status_parameter_passed_through(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """status 参数应透传给飞书 API（不做范围校验）。
        验证请求对象中 status 字段确实被写入，防止透传路径被破坏时测试仍通过。
        """
        from ylhp_common_feishu_sdk.services.attendance import AttendanceService

        mock_client.attendance.v1.user_approval.query.return_value = make_success_response()

        service = AttendanceService(mock_client, config)
        service.query_user_approvals(
            user_ids=["ou_user1"],
            check_date_from="20260314",
            check_date_to="20260314",
            status=1,
        )

        mock_client.attendance.v1.user_approval.query.assert_called_once()
        # 从 call_args 中取出实际传给 API 的 request 对象，验证 status 字段存在
        call_args = mock_client.attendance.v1.user_approval.query.call_args
        actual_request = call_args[0][0]  # 第一个位置参数即 QueryUserApprovalRequest
        # request_body 中的 status 字段应被设置（通过 builder 写入）
        body = actual_request.request_body
        assert getattr(body, "status", None) == 1

    def test_status_none_not_passed_to_api(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """status=None 时不向飞书 API 传 status 字段（返回全部状态）。"""
        from ylhp_common_feishu_sdk.services.attendance import AttendanceService

        mock_client.attendance.v1.user_approval.query.return_value = make_success_response()

        service = AttendanceService(mock_client, config)
        service.query_user_approvals(
            user_ids=["ou_user1"],
            check_date_from="20260314",
            check_date_to="20260314",
            status=None,
        )

        mock_client.attendance.v1.user_approval.query.assert_called_once()
        call_args = mock_client.attendance.v1.user_approval.query.call_args
        actual_request = call_args[0][0]
        body = actual_request.request_body
        # status=None 时 builder 不调用 .status()，字段应为 None 或不存在
        assert getattr(body, "status", None) is None


# ─── 测试类：多批次查询 ───────────────────────────────────────────────


class TestQueryMultiBatch:
    """测试多批次查询（>50 用户）。"""

    def test_120_users_makes_3_api_calls(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """120 个用户 → 3 次 API 调用（50+50+20），结果合并返回。"""
        from ylhp_common_feishu_sdk.services.attendance import AttendanceService

        # 3 次调用分别返回不同用户的审批记录
        leave_batch1 = make_leave_item()
        ua_batch1 = make_user_approval_item(user_id="ou_user1", date="20260314", leaves=[leave_batch1])

        leave_batch2 = make_leave_item()
        ua_batch2 = make_user_approval_item(user_id="ou_user51", date="20260314", leaves=[leave_batch2])

        leave_batch3 = make_leave_item()
        ua_batch3 = make_user_approval_item(user_id="ou_user101", date="20260314", leaves=[leave_batch3])

        mock_client.attendance.v1.user_approval.query.side_effect = [
            make_success_response([ua_batch1]),
            make_success_response([ua_batch2]),
            make_success_response([ua_batch3]),
        ]

        service = AttendanceService(mock_client, config)
        result = service.query_user_approvals(
            user_ids=[f"ou_user{i}" for i in range(1, 121)],
            check_date_from="20260314",
            check_date_to="20260314",
        )

        # 验证调用次数
        assert mock_client.attendance.v1.user_approval.query.call_count == 3
        # 验证结果合并
        assert len(result) == 3
        user_ids_returned = {r.user_id for r in result}
        assert "ou_user1" in user_ids_returned
        assert "ou_user51" in user_ids_returned
        assert "ou_user101" in user_ids_returned

    def test_exactly_50_users_makes_1_api_call(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """恰好 50 个用户 → 1 次 API 调用。"""
        from ylhp_common_feishu_sdk.services.attendance import AttendanceService

        mock_client.attendance.v1.user_approval.query.return_value = make_success_response()

        service = AttendanceService(mock_client, config)
        service.query_user_approvals(
            user_ids=[f"ou_user{i}" for i in range(50)],
            check_date_from="20260314",
            check_date_to="20260314",
        )

        assert mock_client.attendance.v1.user_approval.query.call_count == 1

    def test_51_users_makes_2_api_calls(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """51 个用户 → 2 次 API 调用（50+1）。"""
        from ylhp_common_feishu_sdk.services.attendance import AttendanceService

        mock_client.attendance.v1.user_approval.query.side_effect = [
            make_success_response(),
            make_success_response(),
        ]

        service = AttendanceService(mock_client, config)
        service.query_user_approvals(
            user_ids=[f"ou_user{i}" for i in range(51)],
            check_date_from="20260314",
            check_date_to="20260314",
        )

        assert mock_client.attendance.v1.user_approval.query.call_count == 2


# ─── 测试类：重试机制 ─────────────────────────────────────────────────


class TestRetryBehavior:
    """测试批次级重试机制。"""

    def test_5xx_retries_and_eventually_succeeds(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """5xx 错误触发重试，最终成功。"""
        from ylhp_common_feishu_sdk.services.attendance import AttendanceService

        leave = make_leave_item(approval_status=1)
        ua = make_user_approval_item(user_id="ou_user1", date="20260314", leaves=[leave])

        # 前两次 5xx，第三次成功（max_retries=2）
        mock_client.attendance.v1.user_approval.query.side_effect = [
            make_error_response(99991500, "internal server error"),
            make_error_response(99991500, "internal server error"),
            make_success_response([ua]),
        ]

        service = AttendanceService(mock_client, config)
        result = service.query_user_approvals(
            user_ids=["ou_user1"],
            check_date_from="20260314",
            check_date_to="20260314",
        )

        assert len(result) == 1
        assert mock_client.attendance.v1.user_approval.query.call_count == 3

    def test_429_retries_and_eventually_succeeds(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """429 限流触发重试，最终成功。"""
        from ylhp_common_feishu_sdk.services.attendance import AttendanceService

        leave = make_leave_item(approval_status=1)
        ua = make_user_approval_item(user_id="ou_user1", date="20260314", leaves=[leave])

        mock_client.attendance.v1.user_approval.query.side_effect = [
            make_error_response(99991400, "rate limit"),
            make_success_response([ua]),
        ]

        service = AttendanceService(mock_client, config)
        result = service.query_user_approvals(
            user_ids=["ou_user1"],
            check_date_from="20260314",
            check_date_to="20260314",
        )

        assert len(result) == 1
        assert mock_client.attendance.v1.user_approval.query.call_count == 2

    def test_batch_fails_after_retries_raises_server_error(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """批次重试耗尽后抛出 FeishuServerError，不返回部分结果。"""
        from ylhp_common_feishu_sdk.services.attendance import AttendanceService

        # max_retries=2，共 3 次调用全部失败
        mock_client.attendance.v1.user_approval.query.return_value = make_error_response(
            99991500, "internal server error"
        )

        service = AttendanceService(mock_client, config)
        with pytest.raises(FeishuServerError):
            service.query_user_approvals(
                user_ids=["ou_user1"],
                check_date_from="20260314",
                check_date_to="20260314",
            )

        # 验证重试了 max_retries+1 次
        assert mock_client.attendance.v1.user_approval.query.call_count == 3

    def test_batch2_fails_does_not_return_batch1_results(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """批次 2 失败 → 整个调用失败，不返回批次 1 的部分结果（方案A：全部回滚）。"""
        from ylhp_common_feishu_sdk.services.attendance import AttendanceService

        # 批次 1 成功，批次 2 持续失败
        leave = make_leave_item(approval_status=1)
        ua = make_user_approval_item(user_id="ou_user1", date="20260314", leaves=[leave])

        batch2_error = make_error_response(99991500, "server error")

        mock_client.attendance.v1.user_approval.query.side_effect = [
            make_success_response([ua]),  # 批次 1 成功
            batch2_error,  # 批次 2 失败
            batch2_error,  # 批次 2 重试 1
            batch2_error,  # 批次 2 重试 2（耗尽）
        ]

        service = AttendanceService(mock_client, config)
        with pytest.raises(FeishuServerError):
            service.query_user_approvals(
                user_ids=[f"ou_user{i}" for i in range(51)],  # 51 个 → 2 批次
                check_date_from="20260314",
                check_date_to="20260314",
            )
        # 关键断言：抛出异常而非返回批次 1 的部分结果，由 pytest.raises 保证


    def test_429_exhausted_raises_rate_limit_error(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """429 重试耗尽 → 抛出 FeishuRateLimitError（而非 FeishuServerError）。
        调用方可区分"被限流"与"服务端崩溃"。
        """
        from ylhp_common_feishu_sdk.services.attendance import AttendanceService

        # max_retries=2，3 次调用全部 429
        mock_client.attendance.v1.user_approval.query.return_value = make_error_response(
            99991400, "rate limit"
        )

        service = AttendanceService(mock_client, config)
        with pytest.raises(FeishuRateLimitError):
            service.query_user_approvals(
                user_ids=["ou_user1"],
                check_date_from="20260314",
                check_date_to="20260314",
            )

        assert mock_client.attendance.v1.user_approval.query.call_count == 3


# ─── 测试类：审批类型展平 ──────────────────────────────────────────────


class TestApprovalTypeFlattening:
    """测试四种审批类型（leaves / trips / out / overtime_works）的展平逻辑。
    确保 _TYPE_ATTR_MAP 所有四个条目均被覆盖。
    """

    def test_external_visit_flattened(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """outs 子列表 → approval_type = "external_visit"。"""
        from ylhp_common_feishu_sdk.services.attendance import AttendanceService

        out_item = MagicMock()
        out_item.approval_status = 1
        out_item.start_time = "2026-03-14 10:00:00"
        out_item.end_time = "2026-03-14 12:00:00"
        out_item.reason = "客户拜访"
        out_item.leave_type = None
        out_item.duration = None
        out_item.duration_unit = None
        out_item.approve_pass_time = "2026-03-14 11:00:00"

        ua = make_user_approval_item(user_id="ou_user1", date="20260314", outs=[out_item])
        mock_client.attendance.v1.user_approval.query.return_value = make_success_response([ua])

        service = AttendanceService(mock_client, config)
        result = service.query_user_approvals(
            user_ids=["ou_user1"],
            check_date_from="20260314",
            check_date_to="20260314",
        )

        assert len(result) == 1
        assert result[0].approval_type == "external_visit"
        assert result[0].approval_status == 2  # approve_pass_time 非空 → 推断为 2

    def test_overtime_flattened(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """overtime_works 子列表 → approval_type = "overtime"。"""
        from ylhp_common_feishu_sdk.services.attendance import AttendanceService

        overtime_item = MagicMock()
        overtime_item.approval_status = 1
        overtime_item.start_time = "2026-03-14 19:00:00"
        overtime_item.end_time = "2026-03-14 22:00:00"
        overtime_item.reason = None
        overtime_item.leave_type = None
        overtime_item.duration = 3.0
        overtime_item.unit = 2  # _UNIT_MAP: 2 → "hour"

        ua = make_user_approval_item(
            user_id="ou_user1", date="20260314", overtime_works=[overtime_item]
        )
        mock_client.attendance.v1.user_approval.query.return_value = make_success_response([ua])

        service = AttendanceService(mock_client, config)
        result = service.query_user_approvals(
            user_ids=["ou_user1"],
            check_date_from="20260314",
            check_date_to="20260314",
        )

        assert len(result) == 1
        assert result[0].approval_type == "overtime"
        assert result[0].duration == 3.0
        assert result[0].time_unit == "hour"

    def test_all_four_types_flattened(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """同一用户同时有四种审批 → 全部展平，共 4 条记录。"""
        from ylhp_common_feishu_sdk.services.attendance import AttendanceService

        leave = make_leave_item()
        trip = make_trip_item()

        out_item = MagicMock()
        out_item.approval_status = 1
        out_item.start_time = "2026-03-14 10:00:00"
        out_item.end_time = "2026-03-14 11:00:00"
        out_item.reason = None
        out_item.leave_type = None
        out_item.duration = None
        out_item.duration_unit = None
        out_item.approve_pass_time = "2026-03-14 10:30:00"

        overtime_item = MagicMock()
        overtime_item.approval_status = 1
        overtime_item.start_time = "2026-03-14 20:00:00"
        overtime_item.end_time = "2026-03-14 22:00:00"
        overtime_item.reason = None
        overtime_item.leave_type = None
        overtime_item.duration = 2.0
        overtime_item.unit = 2
        overtime_item.approve_pass_time = ""

        ua = make_user_approval_item(
            user_id="ou_user1",
            date="20260314",
            leaves=[leave],
            trips=[trip],
            outs=[out_item],
            overtime_works=[overtime_item],
        )
        mock_client.attendance.v1.user_approval.query.return_value = make_success_response([ua])

        service = AttendanceService(mock_client, config)
        result = service.query_user_approvals(
            user_ids=["ou_user1"],
            check_date_from="20260314",
            check_date_to="20260314",
        )

        assert len(result) == 4
        types = {r.approval_type for r in result}
        assert types == {"leave", "business_trip", "external_visit", "overtime"}


class TestDeduplication:
    """测试结果去重逻辑。"""

    def test_duplicate_records_are_deduplicated(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """相同 (user_id, approval_date, approval_type) 的记录去重，保留首次出现。"""
        from ylhp_common_feishu_sdk.services.attendance import AttendanceService

        # 两条完全相同的请假记录（模拟飞书 API 偶发重复）
        leave1 = make_leave_item(approval_status=1, start_time="2026-03-14 09:00:00")
        leave2 = make_leave_item(approval_status=1, start_time="2026-03-14 09:00:00")
        ua = make_user_approval_item(
            user_id="ou_user1", date="20260314", leaves=[leave1, leave2]
        )
        mock_client.attendance.v1.user_approval.query.return_value = make_success_response(
            [ua]
        )

        service = AttendanceService(mock_client, config)
        result = service.query_user_approvals(
            user_ids=["ou_user1"],
            check_date_from="20260314",
            check_date_to="20260314",
        )

        # 两条重复记录去重后只剩 1 条
        assert len(result) == 1

    def test_different_types_not_deduplicated(
        self, mock_client: MagicMock, config: FeishuConfig
    ) -> None:
        """不同 approval_type 的记录不去重。"""
        from ylhp_common_feishu_sdk.services.attendance import AttendanceService

        leave = make_leave_item()
        trip = make_trip_item()
        ua = make_user_approval_item(
            user_id="ou_user1", date="20260314", leaves=[leave], trips=[trip]
        )
        mock_client.attendance.v1.user_approval.query.return_value = make_success_response(
            [ua]
        )

        service = AttendanceService(mock_client, config)
        result = service.query_user_approvals(
            user_ids=["ou_user1"],
            check_date_from="20260314",
            check_date_to="20260314",
        )

        assert len(result) == 2
