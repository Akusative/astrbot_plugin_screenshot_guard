# Changelog

All notable changes to this project will be documented in this file.

## [3.2.4] - 2026-05-13

### Added
- 新增 `bark_sounds` 配置项，支持配置多个 Bark 推送铃声名称，每次推送时会从配置列表中随机抽取一个铃声作为参数附带。如果没有填写的话则会默认使用 `minuet` 铃声。

## [3.2.3] - 2026-05-09

### Fixed
- 修复截屏分析模型报错 `FileNotFoundError: No such file or directory: 'data:image...'` 的问题：修改截屏发送方式，直接向模型提供本地文件路径而不是进行 Base64 转码，以兼容部分处理文件路径的 LLM 适配器。
- 修复在非 multipart 数据上传方式（简单二进制上传）下的潜在 `UnboundLocalError: local variable 'device_name' referenced before assignment` 问题，将默认值提取到提前进行初始化。
