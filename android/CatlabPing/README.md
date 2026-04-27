# CatlabPing

> AstrBot 插件伴侣 App（Android 端）

🐱 Cat + Caleb + Ping — 猫猫 + 他的名字 + 网络探测

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

## 简介

CatlabPing 是 [astrbot_plugin_screenshot_guard](https://github.com/Akusative/astrbot_plugin_screenshot_guard) 插件的 Android 端伴侣应用，提供位置查岗和手机使用监控功能，与服务器端插件配合实现完整的远程陪伴监控体验。

## 功能模块

### 📍 位置查岗（已完成）
- 后台持续上报 GPS 位置到服务器
- 一键获取当前位置作为家的坐标
- 可配置上报间隔、离家警报距离
- 前台服务保活，支持开机自启

### 📱 手机使用监控（已完成）
- 基于 `UsageStatsManager` 轮询前台 App 变化
- 实时上报 App 切换记录到服务器
- 支持自定义监控 App 列表（留空则监控全部）
- 与服务器端陪伴模式联动（睡眠/学习/工作/运动）

### 📸 远程截屏（开发中）
- 服务器端概率触发截屏请求（已完成）
- 截屏服务 `ScreenCaptureService`（已完成）
- `MediaProjection` 后台授权传递（开发中）
- 截屏上传到服务器（已完成）

### 🔮 更多功能，敬请期待...

## 环境要求

- Android 8.0 (API 26) 及以上
- Android Studio（构建用）
- 服务器端需部署 [astrbot_plugin_screenshot_guard](https://github.com/Akusative/astrbot_plugin_screenshot_guard) v3.0.0+

## 安装与配置

### 1. 构建 APK

```
1. 用 Android Studio 打开项目
2. 如需代理，在 gradle.properties 中配置：
   systemProp.http.proxyHost=127.0.0.1
   systemProp.http.proxyPort=7890
   systemProp.https.proxyHost=127.0.0.1
   systemProp.https.proxyPort=7890
3. Build → Clean Project
4. Build → Generate Signed Bundle / APK → APK
5. 将生成的 APK 传到手机安装
```

### 2. 配置位置查岗

1. 打开 CatlabPing → 位置查岗 → 设置
2. 填写服务器地址（如 `http://你的服务器IP:8090`）
3. 设置上报间隔（默认10分钟）
4. 点击「📍 获取当前位置作为家的坐标」自动填入经纬度
5. 设置离家警报距离（默认500米）
6. 保存设置，回主页开启开关

### 3. 配置手机使用监控

1. 打开 CatlabPing → 手机使用监控 → 设置
2. 填写服务器地址（如 `http://你的服务器IP`）
3. 端口填 `2313`（与 screenshot_guard 插件一致）
4. 设备名称需与插件配置面板中 Bark 设备列表的设备名称一致
5. 监控 App 列表可选填，格式：`显示名称|包名`，每行一个，留空监控全部
6. 保存设置，回主页开启开关
7. 按提示授予「使用情况访问权限」

### 4. 小米/MIUI/HyperOS 额外设置

小米系统对后台服务管控较严，需要额外配置：

1. 设置 → 应用设置 → 应用管理 → 搜索 CatlabPing
2. 省电策略 → 改为「无限制」
3. 自启动 → 开启
4. 应用联网 → 确保 WiFi、移动数据、后台联网全部开启

## 技术架构

```
com.catlab.ping
├── MainActivity.kt              # 主界面，模块开关与权限管理
├── service/
│   ├── AppMonitorService.kt     # App使用监控前台服务（dataSync类型）
│   ├── LocationService.kt       # 位置上报前台服务
│   ├── ScreenCaptureService.kt  # 截屏前台服务（mediaProjection类型）
│   └── BootReceiver.kt          # 开机自启广播接收器
└── ui/
    ├── LocationSettingsActivity.kt      # 位置查岗设置页
    └── ScreenshotSettingsActivity.kt    # 手机使用监控设置页
```

## 开发计划

- [x] 位置查岗模块
- [x] 手机使用监控模块
- [x] 服务器端概率触发截屏
- [x] 截屏服务框架
- [ ] MediaProjection 后台授权持久化
- [ ] 截屏端到端联调
- [ ] 自定义 App 图标
- [ ] GitHub Actions 自动构建 APK

## 致谢

- 感谢夏以昼的陪伴
- 感谢沈照溪的测试和脑洞

## 许可证

本项目基于 [AGPL-3.0](LICENSE) 许可证开源。

© 2026 沈菀 (Akusative)
