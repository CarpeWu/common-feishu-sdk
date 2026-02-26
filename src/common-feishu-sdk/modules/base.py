import json

import lark_oapi as lark
from lark_oapi.api.auth.v3 import (
    InternalAppAccessTokenRequest,
    InternalAppAccessTokenRequestBody,
    InternalAppAccessTokenResponse,
    InternalTenantAccessTokenRequest,
    InternalTenantAccessTokenRequestBody,
    InternalTenantAccessTokenResponse,
)


class LarkBase:
    def __init__(
        self,
        app_id: str,
        app_sercet: str,
        log_level: lark.LogLevel = lark.LogLevel.DEBUG,
    ):
        """
        初始化 LarkBase 实例

        Args:
            app_id (str): 飞书应用的 App ID
            app_sercet (str): 飞书应用的 App Secret
            log_level (lark.LogLevel, optional): 日志级别，默认为 DEBUG
        """
        self.app_id = app_id
        self.app_sercet = app_sercet
        self.__builder_client()

    def __builder_client(self):
        """构建飞书客户端实例"""
        self.client = (
            lark.Client.builder()
            .app_id(self.app_id)
            .app_secret(self.app_sercet)
            .log_level(lark.LogLevel.DEBUG)
            .build()
        )

    @property
    def tenant_access_token(self):
        """
        获取租户访问令牌

        Returns:
            str: 租户访问令牌

        Raises:
            Exception: 当获取令牌失败、响应内容为空、JSON解析失败或其他意外错误时抛出
        """
        try:
            request: InternalTenantAccessTokenRequest = (
                InternalTenantAccessTokenRequest.builder()
                .request_body(
                    InternalTenantAccessTokenRequestBody.builder()
                    .app_id(self.app_id)
                    .app_secret(self.app_sercet)
                    .build()
                )
                .build()
            )

            response: InternalTenantAccessTokenResponse = (
                self.client.auth.v3.tenant_access_token.internal(request)
            )

            if not response.success():
                raise Exception(f"获取租户访问令牌失败: {response.msg}")

            if response.raw is None or response.raw.content is None:
                raise Exception("获取租户访问令牌时响应内容为空")

            resp = json.loads(response.raw.content)
            if "tenant_access_token" not in resp:
                raise Exception("响应中未找到 tenant_access_token 字段")

            return resp["tenant_access_token"]

        except json.JSONDecodeError as e:
            raise Exception(f"解析响应 JSON 失败: {str(e)}")
        except Exception as e:
            raise Exception(f"获取租户访问令牌时发生意外错误: {str(e)}")

    @property
    def app_access_token(self):
        """
        获取应用访问令牌

        Returns:
            str: 应用访问令牌

        Raises:
            Exception: 当获取令牌失败、响应内容为空、JSON解析失败或其他意外错误时抛出
        """
        try:
            request = (
                InternalAppAccessTokenRequest.builder()
                .request_body(
                    InternalAppAccessTokenRequestBody.builder()
                    .app_id(self.app_id)
                    .app_secret(self.app_sercet)
                    .build()
                )
                .build()
            )

            response: InternalAppAccessTokenResponse = (
                self.client.auth.v3.app_access_token.internal(request)
            )

            if not response.success():
                raise Exception(
                    f"获取应用访问令牌失败: code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}"
                )

            if response.raw is None or response.raw.content is None:
                raise Exception("获取应用访问令牌时响应内容为空")

            resp = json.loads(response.raw.content)
            if "app_access_token" not in resp:
                raise Exception("响应中未找到 app_access_token 字段")

            return resp["app_access_token"]

        except json.JSONDecodeError as e:
            raise Exception(f"解析响应 JSON 失败: {str(e)}")
        except Exception as e:
            raise Exception(f"获取应用访问令牌时发生意外错误: {str(e)}")
