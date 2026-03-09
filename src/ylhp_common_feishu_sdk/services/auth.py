"""H5 网页授权登录服务。"""

from __future__ import annotations

import logging
from urllib.parse import quote_plus

import lark_oapi as lark
from lark_oapi.api.authen.v1 import (
    CreateOidcAccessTokenRequest,
    CreateOidcAccessTokenRequestBody,
    GetUserInfoRequest,
)

from ylhp_common_feishu_sdk._retry import with_retry
from ylhp_common_feishu_sdk.exceptions import FeishuValidationError
from ylhp_common_feishu_sdk.models import AuthCodeRequest, AuthorizeUrlParams, UserInfo
from ylhp_common_feishu_sdk.services._base import BaseService

logger = logging.getLogger("ylhp_common_feishu_sdk")


class AuthService(BaseService):
    """H5 网页授权登录服务。

    提供 H5 网页授权登录功能，支持：
    - 构建飞书 OAuth 授权 URL
    - 通过授权 code 获取用户身份信息

    注意：
    - H5 授权的 code 是一次性的，步骤1失败不重试
    - get_user_info 内部分两步：步骤1不重试，步骤2可重试
    """

    def build_authorize_url(self, redirect_uri: str, state: str = "") -> str:
        """构建飞书 H5 网页授权跳转 URL。

        Args:
            redirect_uri: 授权完成后的回调地址，须与飞书后台配置一致。
            state: 自定义状态参数（可选），建议传入随机值用于防 CSRF 攻击。

        Returns:
            完整的飞书 OAuth 授权 URL。

        Raises:
            FeishuValidationError: redirect_uri 格式不正确。

        Example:
            >>> service = AuthService(client, config)
            >>> url = service.build_authorize_url(
            ...     "https://myapp.com/callback",
            ...     state="random_token"
            ... )
        """
        # 1. 参数校验（通过 Pydantic）
        try:
            params = AuthorizeUrlParams(redirect_uri=redirect_uri, state=state)
        except Exception as e:
            raise FeishuValidationError("redirect_uri", str(e)) from e

        # 2. URL 编码
        encoded_uri = quote_plus(params.redirect_uri)

        # 3. 构造 URL
        url = (
            f"{self._config.domain}/open-apis/authen/v1/authorize"
            f"?app_id={self._config.app_id}"
            f"&redirect_uri={encoded_uri}"
            f"&response_type=code"
        )
        if params.state:
            url += f"&state={quote_plus(params.state)}"

        self._log_call("build_authorize_url", redirect_uri=params.redirect_uri)
        return url

    def get_user_info(self, code: str) -> UserInfo:
        """通过授权 code 获取用户身份信息。

        Args:
            code: 飞书回调返回的临时授权码（一次性）。

        Returns:
            UserInfo 实例，包含用户基本信息。

        Raises:
            FeishuValidationError: code 为空或仅空白字符。
            FeishuAuthError: code 无效或已过期。
            FeishuServerError: 服务端错误（步骤2可重试）。

        Example:
            >>> service = AuthService(client, config)
            >>> user = service.get_user_info("auth_code_from_callback")
            >>> print(user.open_id, user.name)
        """
        # 1. 参数校验
        try:
            req = AuthCodeRequest(code=code)
        except Exception as e:
            raise FeishuValidationError("code", str(e)) from e

        # 2. 步骤1: code 换 token（不重试）
        user_access_token = self._exchange_code_for_token(req.code)

        # 3. 步骤2: token 换用户信息（可重试）
        return self._fetch_user_info(user_access_token)

    def _exchange_code_for_token(self, code: str) -> str:
        """步骤1: code 换 user_access_token（不重试，code 一次性）。

        此方法不加 @with_retry 装饰器，因为 code 是一次性的，
        重试会导致 "code reused" 错误。
        """
        self._log_call("exchange_code_for_token", code_length=len(code))

        body = (
            CreateOidcAccessTokenRequestBody.builder()
            .grant_type("authorization_code")
            .code(code)
            .build()
        )
        request = CreateOidcAccessTokenRequest.builder().request_body(body).build()
        resp = self._client.authen.v1.oidc_access_token.create(request)

        self._check_response(resp, "code换token")
        return resp.data.access_token

    @with_retry
    def _fetch_user_info(self, user_access_token: str) -> UserInfo:
        """步骤2: 用 user_access_token 获取用户信息（可重试）。

        此方法加 @with_retry 装饰器，因为 user_access_token
        在有效期内可以多次使用。
        """
        self._log_call("fetch_user_info")

        option = lark.RequestOption.builder().user_access_token(user_access_token).build()
        request = GetUserInfoRequest.builder().build()
        resp = self._client.authen.v1.user_info.get(request, option)

        self._check_response(resp, "获取用户信息")

        # OIDC 接口直接返回 avatar_url 字符串（非嵌套对象）
        # from_attributes=True 自动读取，raw_avatar_url 字段捕获
        return UserInfo.model_validate(resp.data.user_info)
