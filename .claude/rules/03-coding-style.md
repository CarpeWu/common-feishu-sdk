# 编码风格规则（必须遵守）

## 不可变优先
- dataclass 使用 frozen=True
- FeishuConfig 创建后禁止修改
- 函数内不要修改传入的 dict/list，用展开或 copy

## 文件与函数
- 单文件不超过 400 行（超过则拆分）
- 单函数不超过 50 行（超过则提取子函数）
- 每个公共方法必须有 Google 风格 docstring（Args/Returns/Raises/Example）

## 类型提示
- 所有公共方法必须有完整类型注解
- 使用 Python 3.12 语法：`X | Y` 联合类型
- 禁止使用 `Any` 作为返回类型（入参的 **kwargs 除外）

## JSON 安全
- 绝对禁止用 f-string 拼接 JSON
- 必须使用 json.dumps(dict, ensure_ascii=False)

## 导入顺序
- 标准库 → 第三方库 → 本项目模块
- 使用 ruff 的 isort 规则自动排序
