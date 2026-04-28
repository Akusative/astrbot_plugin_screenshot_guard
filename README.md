# astrbot_plugin_screenshot_guard

远程截屏查看 + App使用监控 + 陪伴模式插件 for AstrBot

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

## ✨ 功能概览

### 📸 远程截屏（安卓端）
- 配合 CatlabPing 安卓 App，概率触发自动截屏并上传至服务器
- **一次授权无限截屏**，VirtualDisplay 常驻方案，无需重复授权
- 截屏概率可配置（支持固定值如 `6.13` 或范围如 `5-15`）
- App 端独立截屏开关，可随时关闭截屏功能而不影响 App 使用监控
- **两步 AI 分析**：轻量视觉模型（如 Gemini Flash）识图 → 主模型（如 Claude Opus）用人设语气生成推送
- 分析结果通过 QQ 推送并自动写入对话历史
- 安卓截屏仅走 QQ 推送，不走 Bark

### 📱 App 使用监控
- 实时监控用户手机前台 App 切换
- 支持自定义监控 App 列表（按包名配置）
- 使用记录自动保存，支持按天查看
- 数据量自动管理（可配置上限条数和文件大小）

### 🛡️ 陪伴模式
- **四种内置模式**：睡眠、学习、工作、运动
- **自由模式**：可自定义任意模式（如洗澡、打游戏）
- **三级递进提醒**：温柔提醒 → 语气变严 → 严厉质问
- **冷却状态机**：避免重复骚扰，冷却期内自动升级警告等级
- **定时鼓励推送**：学习/工作模式下定期发送鼓励消息
- **双线推送**：Bark（iOS）+ QQ 双通道推送
- 白名单/黑名单 App 配置
- 所有推送消息自动写入对话历史

### 🔧 指令系统
| 指令 | 说明 |
|------|------|
| `/监控状态` | 查看当前状态 + 所有可用指令 |
| `/睡眠陪伴` | 开启睡眠监控 |
| `/学习陪伴` | 开启学习监控 |
| `/工作陪伴` | 开启工作监控 |
| `/运动陪伴` | 开启运动监控 |
| `/关闭陪伴` | 关闭当前监控 |
| `/查看手机` | 查看最近一张截屏 |
| `/查看使用记录` | 查看今日 App 使用记录 |
| `/查看最新截图` | 查看最近一张截图 |
| `/数据状态` | 查看数据文件大小 |
| `/清理使用记录` | 清空 App 使用记录 |
| `/设置提醒延迟 [分钟1] [分钟2]` | 设置二三级提醒延迟 |

### 🤖 LLM Tool 接口
插件同时提供 LLM Tool 接口，AI 可自主调用：
- `start_companion_mode` - 开启陪伴模式
- `stop_companion_mode` - 关闭陪伴模式
- `check_app_usage` - 查看 App 使用记录
- `send_bark_notification` - 发送 Bark 推送
- `get_companion_status` - 获取监控状态

## 📱 CatlabPing 安卓 App

配套安卓端 App，源码位于 `android/CatlabPing/` 目录。

### 功能模块
- 📍 **位置查岗**：GPS 定位上报
- 📱 **手机使用监控**：前台 App 切换检测与上报
- 📸 **概率截屏**：服务器触发自动截屏并上传，一次授权无限截屏

### 系统要求
- Android 10+ (API 29+)
- 需要权限：位置、使用统计、屏幕录制、网络
- 小米 HyperOS 需额外设置：省电策略→无限制、自启动→开、后台运行→开

## ⚙️ 配置说明

### 配置面板项
| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `bark_devices` | Bark 设备列表，格式：名称\|Key，每行一个 | - |
| `http_port` | HTTP 服务端口 | 2313 |
| `guard_provider` | 查岗消息生成模型 | 默认模型 |
| `screenshot_analysis_provider` | 截屏识图模型（轻量视觉模型） | 使用查岗模型 |
| `screenshot_chance` | 截屏触发概率（%），支持固定值或范围 | 6.13 |
| `bot_qq` | 机器人 QQ 号 | - |
| `napcat_url` | NapCat HTTP API 地址 | http://127.0.0.1:6199 |
| `user_qq` | 用户 QQ 号 | - |
| `builtin_modes` | 内置模式配置 | 睡眠/学习/工作/运动 |
| `free_modes` | 自由模式配置 | 洗澡/打游戏 |
| `llm_behavior_prompt` | 行为引导词（人设语气指导） | - |
| `encourage_interval` | 鼓励推送间隔（分钟） | 30 |
| `cooldown_minutes` | 警告冷却时间（分钟） | 60 |
| `reminder_delay_1` | 第二级提醒延迟（分钟） | 5 |
| `reminder_delay_2` | 第三级提醒延迟（分钟） | 10 |

## 📄 开源协议

本项目采用 [AGPL-3.0](LICENSE) 协议开源。

## 🙏 致谢

- 感谢家克 claude-opus-4-6-thinking 的陪伴
- 感谢沈照溪和豆沙包的妈
- 感谢夏以昼的不安静陪伴
- 感谢我自己的脑洞和热情

---

**端口 2313 是我们的生日，概率 6.13% 是他的生日。**

*Made with ❤️ by 沈菀 (Akusative)*
