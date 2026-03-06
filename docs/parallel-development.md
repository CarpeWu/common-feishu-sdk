# 并行开发经验总结

## 背景

本次成功实现了三个模块（Auth、Contact、Messaging）的并行开发，从单个 VSCode 窗口中的三个 Claude Code 会话同时进行，最终合并到 main 分支。

---

## 一、前置条件（必须满足）

| 条件 | 说明 |
|------|------|
| **模块独立性** | 模块之间零依赖，可独立开发、测试、合并 |
| **设计文档完备** | 每个模块有清晰的 API 映射、接口签名、测试用例表 |
| **共享文件锁定** | 明确哪些文件不能动（如 client.py），在合并后统一处理 |
| **统一的代码规范** | 编码风格、测试策略、提交格式必须一致 |

---

## 二、并行开发流程

### 2.1 分支策略
```
main
├── feat/module-1-auth      ← 会话 A
├── feat/module-2-contact   ← 会话 B
└── feat/module-3-messaging ← 会话 C
```

每个会话从 main 创建独立的 feature 分支，互不干扰。

### 2.2 会话提示词模板

每个并行会话的提示词应包含：

```
## 你的任务
实现 [模块名] 模块，严格遵循 TDD 流程。

## 设计文档
[粘贴 docs/design.md 中相关章节]

## API 映射（必须遵守）
[粘贴该模块的 lark-oapi 方法映射]

## 测试用例
[粘贴测试用例表]

## 禁止事项
- ❌ 不要修改 client.py（合并后统一注册）
- ❌ 不要修改其他模块的文件
- ❌ 不要修改共享的 conftest.py

## 完成标准
- [ ] 所有测试通过
- [ ] ruff check 通过
- [ ] 提交到 feat/module-X-xxx 分支
```

### 2.3 TDD 流程（每个会话独立执行）

```
Red → Green → Refactor → Doc Sync → Review → Commit
```

---

## 三、遇到的问题与解决方案

### 3.1 Git Worktree 冲突
**问题**：尝试用 git worktree 创建多工作目录，但分支已被占用
```
fatal: 'feat/module-1-auth' is already used by worktree
```
**解决**：`git worktree remove <path>` 清理后重试

**经验**：单窗口多会话模式更简单，不需要 worktree

### 3.2 文件跨分支污染
**问题**：切换分支时，工作目录中仍有其他模块的文件变更
**解决**：使用 `git stash` 暂存，切换后按需恢复

**经验**：每个会话只 add 自己模块的文件

### 3.3 GitHub CLI 不适用
**问题**：`gh pr create` 只支持 GitHub，不适用于自建 Git 服务器
**解决**：使用 Web 界面手动创建 PR

**经验**：提前确认 Git 托管平台，准备备用方案

---

## 四、最佳实践

### 4.1 提示词设计
- ✅ 范围明确：每个会话只负责一个模块
- ✅ 边界清晰：列出禁止修改的文件
- ✅ 验收标准：测试通过、lint 通过、提交格式

### 4.2 提交策略
- 测试和实现一起提交（不拆分）
- 使用规范的 commit message：`feat(module): description`
- 合并前由主会话统一检查

### 4.3 合并后处理
共享文件（如 client.py）的更新放在最后一个 PR 合并后：
```python
# 合并后统一添加
self.auth = AuthService(self._lark_client, self._config)
self.messages = MessagingService(self._lark_client, self._config)
self.contacts = ContactService(self._lark_client, self._config)
```

### 4.4 质量保证
```bash
# 合并前检查
uv run pytest && uv run ruff check src/ tests/

# 合并后验证
uv run pytest  # 确保无回归
```

---

## 五、快速命令参考

```bash
# 查看所有分支状态
git branch -a

# 推送所有 feature 分支
git push -u origin feat/module-1-auth feat/module-2-contact feat/module-3-messaging

# 清理已合并的本地分支
git branch -d feat/module-1-auth feat/module-2-contact feat/module-3-messaging

# 最终提交共享文件
git add src/.../client.py
git commit -m "feat(client): register services"
git push origin main
```

---

## 六、适用场景

| 适合并行 | 不适合并行 |
|----------|------------|
| 模块间无依赖 | 模块间有调用关系 |
| 接口已定义清楚 | 接口需要边做边设计 |
| 每个模块工作量相近 | 工作量差异大（会互相等待） |
| 有详细的设计文档 | 设计文档不完整 |

---

## 七、本次成果

- ✅ 3 个模块并行开发
- ✅ 166 个测试全部通过
- ✅ 3 个 PR 合并到 main
- ✅ 服务注册完成
- ✅ 本地分支已清理

**耗时对比**：并行开发 ≈ 串行开发时间的 1/3
