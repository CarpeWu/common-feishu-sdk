---
description: 提交前最终检查清单
---

请在提交代码前执行完整的预检清单：

```bash
# 1. 测试
uv run pytest -v

# 2. 代码检查
uv run ruff check src/ tests/

# 3. 格式化
uv run ruff format src/ tests/

# 4. 类型检查（如果安装了 mypy/pyright）
# uv run mypy src/
```

然后执行 /sync-docs 检查文档一致性。

全部通过后输出：
```
✅ 预检通过，可以提交。
建议提交信息：<type>(<scope>): <description>
```
