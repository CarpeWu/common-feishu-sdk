# 飞书 API 映射规则（必须遵守）

实现飞书 API 调用时，必须严格按以下映射使用 lark-oapi 方法。
禁止使用 .list() 替代 .children() 或 .find_by_department()。

| SDK 方法 | lark-oapi 调用 | Request 类 |
|----------|---------------|------------|
| list_departments | client.contact.v3.department.children(req) | ChildrenDepartmentRequest |
| list_department_users | client.contact.v3.user.find_by_department(req) | FindByDepartmentUserRequest |
| get_user | client.contact.v3.user.get(req) | GetUserRequest |
| send_text / send_card | client.im.v1.message.create(req) | CreateMessageRequest |
| reply_text | client.im.v1.message.reply(req) | ReplyMessageRequest |
| code→token | client.authen.v1.oidc_access_token.create(req) | CreateOidcAccessTokenRequest |
| token→user_info | client.authen.v1.user_info.get(req) | GetUserInfoRequest |

如果需要调用不在此表中的飞书 API，必须先向我确认映射关系后再实现。
