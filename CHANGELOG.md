# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- refactor(log): use NullHandler + propagate=True for SDK logger
- refactor(models): convert output models from dataclass to Pydantic BaseModel

### Added
- 初始项目结构

### Changed
- refactor(log): SDK logger now uses NullHandler + propagate=True, logs bubble to host root logger
- refactor(models): output models converted from dataclass to Pydantic BaseModel with from_attributes=True

## [0.1.1] - 2025-02-28

### Added
- 项目初始化

## [0.2.0] - 2025-03-05

### Added
- feat(client): implement Feishu main class with thread-safe named registry
- feat(config): implement FeishuConfig with environment variable loading
- feat(exceptions): implement exception hierarchy with translate_error()
- feat(log): implement SDK logger with SensitiveFilter for log sanitization
- feat(models): implement PageResult generic dataclass
- feat(retry): implement with_retry decorator with exponential backoff
- feat(services): implement BaseService with _check_response and _log_call
