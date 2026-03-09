# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-03-09

### Added

- feat(client): implement Feishu main class with thread-safe named registry
- feat(config): implement FeishuConfig with environment variable loading
- feat(exceptions): implement exception hierarchy with `translate_error()`
- feat(log): implement SDK logger with SensitiveFilter for log sanitization
- feat(models): implement Pydantic models for input validation and output types
  - `UserInfo`, `UserDetail`, `Department`, `PageResult[T]` (frozen, from_attributes=True)
  - Input models: `AuthorizeUrlParams`, `AuthCodeRequest`, `TextContent`, `CardContent`, etc.
- feat(retry): implement `@with_retry` decorator with exponential backoff
  - Dynamic config reading from `self._config`
  - Only retries on `retryable=True` exceptions (5xx, 429)
- feat(services): implement BaseService with `_check_response` and `_log_call`
- feat(auth): H5 web authorization login
  - `build_authorize_url(redirect_uri, state?)` - Build OAuth URL
  - `get_user_info(code)` - Exchange code for user info (step1 no-retry, step2 retryable)
- feat(contact): Organization structure management
  - `list_departments()` / `iter_departments()` - Get child departments
  - `list_department_users()` / `iter_department_users()` - Get department users
  - `get_user(user_id)` - Get user details
- feat(messaging): Message sending service
  - `send_text(open_id, text)` - Send personal text message
  - `send_text_to_chat(chat_id, text)` - Send group text message
  - `send_card(receive_id, card, receive_id_type?)` - Send interactive card
  - `reply_text(message_id, text)` - Reply to message
- docs: Add 6 example scripts (send_text, send_card, h5_login, sync_org, daily_reminder, multi_app)
- test: 170+ test cases with 98% code coverage

### Changed

- refactor(log): SDK logger now uses NullHandler + propagate=True, logs bubble to host root logger
- refactor(models): output models converted from dataclass to Pydantic BaseModel with `from_attributes=True`
- docs: README.md updated with correct API names (`contacts`, `messages` plural form)
- docs: README.md added multi-app examples, error handling guide, config reference

## [0.1.1] - 2025-02-28

### Added

- Initial project structure
