import json

import lark_oapi as lark

from ..schemas.department import Department
from .base import LarkBase


class LarkDepartment(LarkBase):
    async def get_departments_by_parent_department_id(
        self, department_id: str
    ) -> list[Department]:
        """根据父部门ID获取子部门列表"""
        try:
            # 构建请求体
            body = {
                "filter": {
                    "conditions": [
                        {
                            "field": "parent_department_id",
                            "operator": "eq",
                            "value": department_id,
                        }
                    ]
                },
                "required_fields": ["name"],
                "page_request": {"page_size": 100},
            }

            # 构建请求
            request: lark.BaseRequest = (
                lark.BaseRequest.builder()
                .http_method(lark.HttpMethod.POST)
                .uri(
                    "/open-apis/directory/v1/departments/filter?department_id_type=open_department_id&employee_id_type=open_id"
                )
                .token_types({lark.AccessTokenType.TENANT})
                .body(body)
                .build()
            )

            # 发送请求
            response: lark.BaseResponse = self.client.request(request)

            # 检查响应是否成功
            if not response.success():
                raise Exception(f"API请求失败: {response.msg}")

            # 检查响应内容
            if not response.raw or not response.raw.content:
                raise Exception("API响应内容为空")

            # 解析响应
            resp = json.loads(response.raw.content)

            # 检查数据格式
            if not resp.get("data") or not resp["data"].get("departments"):
                return []

            # 转换数据模型
            departments = []
            for item in resp["data"]["departments"]:
                try:
                    department = Department(**item)
                    departments.append(department)
                except Exception as e:
                    # 记录转换失败的数据，但继续处理其他数据
                    print(f"部门数据转换失败: {e}, 数据: {item}")
                    continue

            return departments

        except json.JSONDecodeError as e:
            raise Exception(f"JSON解析失败: {e}")
        except Exception as e:
            raise Exception(f"获取部门列表失败: {e}")
