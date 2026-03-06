"""AuthService 测试用例。"""

from unittest.mock import MagicMock

import pytest

from ylhp_common_feishu_sdk.config import FeishuConfig
from ylhp_common_feishu_sdk.exceptions import (
    FeishuAuthError,
    FeishuServerError,
    FeishuValidationError,
)
from ylhp_common_feishu_sdk.services.auth import AuthService, UserInfo

# ============================================================================
# 测试工具函数
# ============================================================================


def make_success_token_response(access_token: str) -> MagicMock:
    """构造成功的 code 换 token 响应。"""
    resp = MagicMock()
    resp.success = True
    resp.data = MagicMock()
    resp.data.access_token = access_token
    return resp


def make_success_user_info_response(user_info: dict) -> MagicMock:
    """构造成功的获取用户信息响应。"""
    resp = MagicMock()
    resp.success = True
    resp.data = MagicMock()
    resp.data.user_info = MagicMock()
    # 手动设置每个属性，确保返回实际值而非 MagicMock
    for key, value in user_info.items():
        setattr(resp.data.user_info, key, value)
    return resp


def make_error_response(code: int, msg: str) -> MagicMock:
    """构造失败的响应。"""
    resp = MagicMock()
    resp.success = False
    resp.code = code
    resp.msg = msg
    resp.log_id = "test_log_id"
    return resp


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def config() -> FeishuConfig:
    """创建测试配置。"""
    return FeishuConfig(
        app_id="cli_test_000",
        app_secret="test_secret_000",
        domain="https://open.feishu.cn",
    )


@pytest.fixture
def client() -> MagicMock:
    """创建 mock 客户端。"""
    return MagicMock()


@pytest.fixture
def auth_service(client: MagicMock, config: FeishuConfig) -> AuthService:
    """创建 AuthService 实例。"""
    return AuthService(client, config)


# ============================================================================
# build_authorize_url 测试
# ============================================================================


class TestBuildAuthorizeUrl:
    """build_authorize_url 方法测试。"""

    def test_build_authorize_url_format(self, auth_service: AuthService) -> None:
        """URL 包含必要参数。"""
        url = auth_service.build_authorize_url("https://example.com/callback")

        assert "https://open.feishu.cn/open-apis/authen/v1/authorize" in url
        assert "app_id=cli_test_000" in url
        assert "redirect_uri=" in url
        assert "response_type=code" in url

    def test_build_authorize_url_with_state(self, auth_service: AuthService) -> None:
        """state 参数正确拼接。"""
        url = auth_service.build_authorize_url(
            "https://example.com/callback",
            state="random_csrf_token",
        )

        assert "state=random_csrf_token" in url

    def test_build_authorize_url_without_state(self, auth_service: AuthService) -> None:
        """不传 state 时 URL 不含 state 参数。"""
        url = auth_service.build_authorize_url("https://example.com/callback")

        assert "&state=" not in url

    def test_build_authorize_url_uses_config_domain(self, client: MagicMock) -> None:
        """使用 config.domain 作为 API 域名。"""
        custom_config = FeishuConfig(
            app_id="cli_test_000",
            app_secret="test_secret_000",
            domain="https://custom.feishu.cn",
        )
        service = AuthService(client, custom_config)

        url = service.build_authorize_url("https://example.com/callback")

        assert "https://custom.feishu.cn/open-apis/authen/v1/authorize" in url

    def test_build_authorize_url_invalid_uri(self, auth_service: AuthService) -> None:
        """非 http(s) 开头的 redirect_uri 触发校验错误。"""
        with pytest.raises(FeishuValidationError) as exc_info:
            auth_service.build_authorize_url("invalid-uri")

        assert exc_info.value.field == "redirect_uri"

    def test_build_authorize_url_url_encodes_redirect_uri(self, auth_service: AuthService) -> None:
        """redirect_uri 需要 URL 编码。"""
        url = auth_service.build_authorize_url("https://example.com/callback?foo=bar&baz=qux")

        # 检查特殊字符被编码
        assert "foo%3Dbar" in url or "foo=bar" not in url.split("redirect_uri=")[1].split("&")[0]


# ============================================================================
# get_user_info 测试
# ============================================================================


class TestGetUserInfo:
    """get_user_info 方法测试。"""

    def test_get_user_info_success(self, auth_service: AuthService, client: MagicMock) -> None:
        """两步调用成功，返回 UserInfo。"""
        # Mock 步骤1: code 换 token
        client.authen.v1.oidc_access_token.create.return_value = make_success_token_response(
            "u-test_token"
        )

        # Mock 步骤2: token 换用户信息
        client.authen.v1.user_info.get.return_value = make_success_user_info_response(
            {
                "open_id": "ou_test123",
                "name": "测试用户",
                "en_name": "Test User",
                "avatar_url": "https://example.com/avatar.png",
                "email": "test@example.com",
                "mobile": "+8613800138000",
                "tenant_key": "tenant123",
                "department_ids": ["od_dept1", "od_dept2"],
            }
        )

        result = auth_service.get_user_info("test_code")

        assert isinstance(result, UserInfo)
        assert result.open_id == "ou_test123"
        assert result.name == "测试用户"
        assert result.en_name == "Test User"
        assert result.email == "test@example.com"

    def test_get_user_info_empty_code(self, auth_service: AuthService) -> None:
        """空 code 触发校验错误。"""
        with pytest.raises(FeishuValidationError) as exc_info:
            auth_service.get_user_info("")

        assert exc_info.value.field == "code"

    def test_get_user_info_whitespace_code(self, auth_service: AuthService) -> None:
        """纯空白字符的 code 触发校验错误。"""
        with pytest.raises(FeishuValidationError) as exc_info:
            auth_service.get_user_info("   ")

        assert exc_info.value.field == "code"

    def test_get_user_info_invalid_code(self, auth_service: AuthService, client: MagicMock) -> None:
        """无效 code 抛出 AuthError。"""
        # Mock 步骤1失败: 无效 code
        client.authen.v1.oidc_access_token.create.return_value = make_error_response(
            99991661, "code invalid"
        )

        with pytest.raises(FeishuAuthError):
            auth_service.get_user_info("invalid_code")

    def test_get_user_info_step1_no_retry(
        self, auth_service: AuthService, client: MagicMock
    ) -> None:
        """步骤1失败不重试（code 是一次性的）。"""
        # Mock 步骤1返回 5xx 错误
        client.authen.v1.oidc_access_token.create.return_value = make_error_response(
            99991500, "internal error"
        )

        with pytest.raises(FeishuServerError):
            auth_service.get_user_info("test_code")

        # 验证只调用1次，没有重试
        assert client.authen.v1.oidc_access_token.create.call_count == 1

    def test_get_user_info_step2_retries(
        self, auth_service: AuthService, client: MagicMock
    ) -> None:
        """步骤2失败可重试。"""
        # Mock 步骤1成功
        client.authen.v1.oidc_access_token.create.return_value = make_success_token_response(
            "u-test_token"
        )

        # Mock 步骤2: 第一次失败，第二次成功
        client.authen.v1.user_info.get.side_effect = [
            make_error_response(99991500, "internal error"),
            make_success_user_info_response(
                {
                    "open_id": "ou_test123",
                    "name": "测试用户",
                }
            ),
        ]

        result = auth_service.get_user_info("test_code")

        # 验证最终成功
        assert result.open_id == "ou_test123"
        # 验证步骤2被调用了2次（第一次失败，重试后成功）
        assert client.authen.v1.user_info.get.call_count == 2


# ============================================================================
# UserInfo dataclass 测试
# ============================================================================


class TestUserInfo:
    """UserInfo dataclass 测试。"""

    def test_user_info_frozen(self) -> None:
        """UserInfo 是不可变的。"""
        user = UserInfo(open_id="ou_test", name="Test")

        with pytest.raises(AttributeError):
            user.open_id = "ou_modified"  # type: ignore

    def test_user_info_optional_fields(self) -> None:
        """可选字段默认为 None。"""
        user = UserInfo(open_id="ou_test", name="Test")

        assert user.en_name is None
        assert user.avatar_url is None
        assert user.email is None
        assert user.mobile is None
        assert user.tenant_key is None
        assert user.department_ids == []
