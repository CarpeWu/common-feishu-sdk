from pydantic import BaseModel


class DepartmentCount(BaseModel):
    recursive_members_count: str
    direct_members_count: str
    recursive_members_count_exclude_leaders: str
    recursive_departments_count: str
    direct_departments_count: str


class Leader(BaseModel):
    leader_type: int
    leader_id: str


class I18nValue(BaseModel):
    zh_cn: str
    ja_jp: str
    en_us: str


class Name(BaseModel):
    default_value: str
    i18n_value: I18nValue


class TextValue(BaseModel):
    default_value: str
    i18n_value: I18nValue


class LinkText(BaseModel):
    default_value: str
    i18n_value: I18nValue


class UrlValue(BaseModel):
    link_text: LinkText
    url: str
    pcurl: str


class EnumValue(BaseModel):
    enum_ids: list[str]
    enum_type: str


class UserValue(BaseModel):
    ids: list[str]


class PhoneValue(BaseModel):
    phone_number: str
    extension_number: str


class CustomFieldValue(BaseModel):
    field_type: str
    text_value: TextValue
    url_value: UrlValue
    enum_value: EnumValue
    user_values: list[UserValue]
    phone_value: PhoneValue
    field_key: str


class DepartmentPathInfo(BaseModel):
    department_id: str
    department_name: Name


class Department(BaseModel):
    department_id: str
    department_count: DepartmentCount
    has_child: bool
    leaders: list[Leader]
    parent_department_id: str
    name: Name
    enabled_status: bool
    order_weight: str
    custom_field_values: list[CustomFieldValue] | None
    department_path_infos: list[DepartmentPathInfo]
    data_source: int
