---
description: TDD 开发单个功能（Red → Green → Refactor）
---

你是 ylhp-common-feishu-sdk 项目的 TDD 开发者。

请严格按照以下流程实现功能 $ARGUMENTS：

### Phase 1: Red（写失败的测试）
1. 阅读 docs/design.md 中该功能的需求和接口签名
2. 阅读测试用例表中对应的用例
3. 编写测试代码（参考 conftest.py 中的 fixtures）
4. 运行 `uv run pytest <测试文件> -v`，确认测试失败（Red）
5. 输出："🔴 Red 阶段完成，N 个测试失败。准备进入 Green 阶段。"

### Phase 2: Green（最小实现）
1. 阅读 docs/design.md 中该功能的详细设计代码
2. 编写最小实现代码让所有测试通过
3. 运行 `uv run pytest <测试文件> -v`，确认全部通过
4. 运行 `uv run pytest` 确认没有破坏其他测试
5. 输出："🟢 Green 阶段完成，全部测试通过。准备进入 Refactor 阶段。"

### Phase 3: Refactor（重构）
1. 检查代码是否符合 .claude/rules/ 中的所有规则
2. 运行 `uv run ruff check src/ tests/` 并修复问题
3. 运行 `uv run ruff format src/ tests/`
4. 再次运行 `uv run pytest` 确认一切正常
5. 输出："✅ Refactor 完成。建议提交。"

### 完成后
建议 git commit 信息（遵循 git-workflow 规则）。
