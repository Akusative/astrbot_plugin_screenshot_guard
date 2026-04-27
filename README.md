# astrbot_plugin_screenshot_guard

> 📱 远程截屏查看 + App 使用监控 + 陪伴模式插件
> 
> 基于 Bark 推送 + iOS 快捷指令 / Android CatlabPing App，实现 AI 对用户手机使用情况的实时感知与陪伴提醒。

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![AstrBot](https://img.shields.io/badge/AstrBot-Plugin-purple.svg)](https://github.com/Soulter/AstrBot)
[![Version](https://img.shields.io/badge/Version-3.1.0-green.svg)]()

## ✨ 功能概览

### 📊 App 使用记录
- 通过 iOS 快捷指令自动化，记录用户每次打开指定 App 的时间
- 支持多设备上报（iPhone + iPad），通过 `device` 字段区分来源
- AI 可随时查看用户的 App 使用记录

### 🛡️ 陪伴模式

#### 四种内置模式
| 模式 | 监控范围 | 适用场景 |
|------|---------|---------|
| 😴 睡眠陪伴 | 所有 App | 互道晚安后，防止熬夜刷手机 |
| 📚 学习陪伴 | 娱乐类 App（QQ/微信除外） | 学习期间，防止摸鱼 |
| 💼 工作陪伴 | 娱乐类 App（QQ/微信除外） | 工作期间，提高专注度 |
| 🏃 运动陪伴 | 所有 App | 运动期间，放下手机 |

#### 🆕 无限自定义模式
除了四种内置模式，你可以创建任意数量的自定义模式！

**配置格式**（在配置面板的「自定义陪伴模式」中填写，每行一个模式）：

```
名称|模式描述|授权App(逗号分隔)|警告App(逗号分隔)
```

**字段说明**：
- **名称**：模式的名字，开启时使用
- **模式描述**：传给 LLM 的场景描述，AI 会根据描述判断回应逻辑
- **授权App**：在此模式下允许使用的 App，不会触发警告（可留空）
- **警告App**：在此模式下会触发警告的 App，留空则除授权外全部警告（可留空）

**示例**：

```
洗澡|用户说去洗澡但可能会拖延不去，也可能带手机进浴室边洗边玩，注意提醒手机防水||
打游戏|用户在打游戏，这是允许的娱乐时间，但不应该切出去刷社交媒体|Steam,原神|小红书,抖音
午睡|用户说要午睡，但可能会忍不住刷手机，温柔提醒她放下手机休息||
做饭|用户在做饭，看菜谱App是允许的，但不应该刷社交媒体|下厨房|小红书,抖音,B站
```

### ⏰ 三级递进提醒 + 冷却状态机
当陪伴模式开启后，用户打开被监控的 App 时：

| 级别 | 时机 | 语气 | 示例 |
|------|------|------|------|
| 第一级 | 立即推送 | 温柔提醒 | "宝宝不是说要睡了吗…怎么又在玩小红书 😤" |
| 第二级 | X 分钟后（默认5分钟） | 语气变严 | "都提醒过了还在玩小红书…要生气了 😠" |
| 第三级 | Y 分钟后（默认10分钟） | 严厉催促 | "放下手机，现在 😡" |

**🆕 冷却重置机制**：
- 设定冷却时间（默认 60 分钟），最后一次违规后经过冷却时间无再犯，警告等级自动重置为 1
- 冷却期内再犯，延续当前等级继续递进（不会从 1 重新开始）
- 再犯时 LLM 生成的警告文案会包含"假装乖了 X 分钟就又犯了"的信息

**智能取消**：用户打开 QQ（回来找你聊天），所有待发提醒自动取消。

### 📱 多设备支持
- 支持同时配置多个 Bark 设备（如 iPhone + iPad）
- **智能推送**：根据 App 上报的 `device` 字段，将警告推送到对应设备
- 设备名称必须与 iOS 快捷指令中上报的 `device` 字段**完全一致**（区分大小写）

### 💬 QQ 同步警告
- 警告消息可同步发送到 QQ 私聊，消息会进入 LLM 对话上下文
- 通过 NapCat 的 HTTP API 实现
- **多用户场景**：如果多人共用同一个 AstrBot，每个用户需要在自己的 Bot 配置中分别设置 `user_qq` 和 `napcat_url`

### 🎨 多图标随机推送
- 支持配置多个推送图标 URL，每次推送随机选择
- 可绑定特定 BotQQ 号，实现不同 Bot 使用不同图标

### 📸 远程截屏查看
- AI 发送 Bark 推送到用户手机
- 用户截屏后通过快捷指令自动上传
- AI 在对话中直接查看截图

## 🚀 安装与配置

### 前置要求
- [AstrBot](https://github.com/Soulter/AstrBot) v4.x
- iOS 设备 + [Bark](https://apps.apple.com/app/bark/id1403753865) App
- 云服务器需开放插件使用的端口（默认 2313）

### 第一步：安装插件
将本插件目录放入 AstrBot 的 `data/plugins/` 目录下，重启 AstrBot。

### 第二步：配置 Bark 设备
1. 在 iOS 设备上安装 [Bark](https://apps.apple.com/app/bark/id1403753865)
2. 打开 Bark，获取每个设备的专属推送 Key
3. 在 AstrBot 配置面板的「Bark推送设备列表」中填写：

```
iPhone|你的iPhone的BarkKey
iPad|你的iPad的BarkKey
```

> ⚠️ **重要**：设备名称（如 `iPhone`、`iPad`）必须与 iOS 快捷指令中上报的 `device` 字段**完全一致**，区分大小写！

### 第三步：配置端口
在配置面板中修改 HTTP 监听端口（默认 2313），确保云服务器防火墙已放行该端口的 TCP 入站规则。

### 第四步：配置 iOS 快捷指令（iOS 用户）

#### 创建快捷指令（每个要监控的 App 各一个）

以"小红书"为例：

1. 打开 iPhone「快捷指令」App → 点右上角 `+` → 命名为"报告小红书"
2. 添加操作：搜索「获取 URL 内容」
3. 设置：
   - **URL**：`http://你的服务器IP:2313/app/report`
   - **方法**：`POST`
   - **头部**：添加 `Content-Type` = `application/json`
   - **请求体**：选 `JSON`，添加以下字段：
     - `app_name`（文本类型）：`小红书`
     - `device`（文本类型）：`iPhone`（或 `iPad`，与配置面板中的设备名称保持一致）

> ⚠️ **重要**：`device` 字段的值必须与配置面板中 Bark 设备列表里填写的设备名称**完全一致**！例如配置面板写的是 `iPhone`，快捷指令里也必须填 `iPhone`，不能填 `iphone` 或 `手机`。

#### 创建自动化

1. 快捷指令 App → 底部「自动化」→ 点 `+`
2. 选择「App」→ 选择"小红书" → 勾选「已打开」
3. 选择运行「报告小红书」快捷指令
4. **关闭「运行前询问」**

对每个要监控的 App 重复以上步骤，只需修改快捷指令名称和 `app_name` 的值。

如果有多个 iOS 设备（如 iPhone + iPad），每个设备都需要配置快捷指令和自动化，注意 `device` 字段填写对应的设备名称。

#### 截屏上传快捷指令（可选）

1. 新建快捷指令，命名为"上传截图"
2. 添加操作：「获取最新的照片」，数量设为 1
3. 添加操作：「获取 URL 内容」
   - **URL**：`http://你的服务器IP:2313/screenshot/upload`
   - **方法**：`POST`
   - **请求体**：选「表单」，添加字段 `file`（文件类型），值选上一步的照片

### 第五步：配置 QQ 同步警告（可选）

如果希望警告消息同时发送到 QQ 私聊（消息会进入 LLM 对话上下文），需要在配置面板中填写：

- **Bot的QQ号**：你的 Bot 的 QQ 号
- **NapCat HTTP API地址**：例如 `http://127.0.0.1:3000`
- **用户QQ号**：接收警告消息的用户 QQ 号

### 第六步：配置 Android 端 CatlabPing（Android 用户）

如果你使用 Android 手机，可以使用 CatlabPing 伴侣 App 替代 iOS 快捷指令方案。

#### 构建与安装

1. 用 Android Studio 打开 `android/CatlabPing` 目录
2. 如需代理，在 `gradle.properties` 中配置代理端口
3. Build → Clean Project → Generate APKs
4. 将 APK 传到手机安装

#### 配置位置查岗

1. 打开 CatlabPing → 位置查岗 → 设置
2. 填写服务器地址（如 `http://你的服务器IP:8090`）
3. 设置上报间隔（默认10分钟）
4. 点击「📍 获取当前位置作为家的坐标」自动填入经纬度
5. 设置离家警报距离（默认500米）
6. 保存设置，回主页开启开关

#### 配置手机使用监控

1. 打开 CatlabPing → 手机使用监控 → 设置
2. 填写服务器地址（如 `http://你的服务器IP`），端口 `2313`
3. 设备名称需与插件配置面板中 Bark 设备列表的设备名称一致
4. 监控 App 列表可选填，格式：`显示名称|包名`，每行一个，留空监控全部
5. 保存设置，回主页开启开关
6. 按提示授予「使用情况访问权限」

#### 小米/MIUI/HyperOS 额外设置

小米系统对后台服务管控较严，需要额外配置：

1. 设置 → 应用设置 → 应用管理 → 搜索 CatlabPing
2. 省电策略 → 改为「无限制」
3. 自启动 → 开启
4. 应用联网 → 确保 WiFi、移动数据、后台联网全部开启

## 🎨 自定义推送图标

支持配置多个推送图标，每次推送随机选择。

在配置面板的「Bark推送图标URL列表」中填写（每行一个）：

```
https://example.com/icon1.gif
https://example.com/icon2.png
https://example.com/icon3.gif|12345678
```

最后一种格式 `图标URL|BotQQ号` 可以将特定图标绑定到特定 Bot。

图标要求：
- 必须是可通过 URL 公开访问的图片
- 支持 PNG、JPG、GIF 格式
- 建议使用正方形图片，推荐尺寸 100x100 像素
- 可使用 [PostImages](https://postimages.org/)、[imgur](https://imgur.com/) 等免费图床上传

## 📋 指令列表

### AI 对话指令（通过 LLM Tool 自然触发）
| 工具名 | 说明 | 触发场景 |
|--------|------|---------|
| `start_companion_mode` | 开启陪伴模式 | 用户说"我去睡了/学习/工作/运动/洗澡"等 |
| `stop_companion_mode` | 关闭陪伴模式 | 用户说"起床了/学完了/下班了/运动结束"等 |
| `check_app_usage` | 查看 App 使用记录 | 想知道用户最近在用什么 |
| `send_bark_notification` | 发送 Bark 推送 | 想主动给用户手机发消息 |
| `get_companion_status` | 查看监控状态 | 想了解当前监控情况 |

### 手动指令
| 指令 | 别名 | 说明 |
|------|------|------|
| `查看手机` | `截屏`、`看看手机` | 发送截屏请求 |
| `监控状态` | `查看监控` | 查看当前监控状态 |
| `查看使用记录` | `app记录`、`她在干嘛` | 查看今日 App 使用记录 |
| `查看最新截图` | `最新截图` | 显示最近一次截图 |
| `设置提醒延迟` | `修改提醒时间` | 设置二级/三级提醒的延迟时间 |
| `清理使用记录` | `清理数据`、`清空记录` | 清理 App 使用记录 |
| `数据状态` | `数据大小` | 查看数据文件状态 |

## ⚙️ 配置说明

所有配置项均可在 AstrBot 配置面板中修改：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `bark_devices` | Bark 推送设备列表 | 空 |
| `http_port` | HTTP 监听端口 | 2313 |
| `bark_icon_urls` | 推送图标 URL 列表 | 空 |
| `bark_push_title` | 温柔模式推送标题 | 💕 |
| `bark_push_title_strict` | 严厉模式推送标题 | ⚠️ |
| `reminder_delay_1` | 第二级提醒延迟（分钟） | 5 |
| `reminder_delay_2` | 第三级提醒延迟（分钟） | 10 |
| `cooldown_minutes` | 警告冷却时间（分钟） | 60 |
| `max_records` | App 使用记录最大条数 | 1000 |
| `guard_provider` | 查岗消息生成用的模型 | 空（使用默认） |
| `bot_qq` | Bot 的 QQ 号 | 空 |
| `napcat_url` | NapCat HTTP API 地址 | 空 |
| `user_qq` | 用户 QQ 号 | 空 |
| `custom_modes` | 自定义陪伴模式 | 预填示例 |
| `llm_behavior_prompt` | 陪伴监控行为引导词 | 完整模板 |

## 📁 目录结构

```
astrbot_plugin_screenshot_guard/
├── main.py              # 插件主代码
├── metadata.yaml        # 插件元数据
├── _conf_schema.json    # 配置面板 Schema
├── README.md            # 说明文档
├── LICENSE              # AGPL-3.0 许可证
├── screenshots/         # 截图存储目录（自动创建）
├── data/                # 数据目录（自动创建）
│   ├── app_usage.json   # App 使用记录
│   └── config.json      # 插件配置
└── android/             # Android 端 CatlabPing 伴侣 App
    └── CatlabPing/      # Android Studio 项目
        ├── app/
        │   ├── build.gradle
        │   └── src/main/
        │       ├── AndroidManifest.xml
        │       ├── java/com/catlab/ping/
        │       │   ├── MainActivity.kt
        │       │   ├── service/
        │       │   │   ├── AppMonitorService.kt
        │       │   │   ├── LocationService.kt
        │       │   │   ├── ScreenCaptureService.kt
        │       │   │   └── BootReceiver.kt
        │       │   └── ui/
        │       │       ├── LocationSettingsActivity.kt
        │       │       └── ScreenshotSettingsActivity.kt
        │       └── res/
        ├── build.gradle
        ├── settings.gradle
        ├── gradle.properties
        └── gradle/
```

## 📝 更新日志

### v3.1.0
- 🆕 Android 端 CatlabPing 伴侣 App：位置查岗 + 手机使用监控，替代 iOS 快捷指令方案
- 🆕 服务器端概率触发截屏请求（配置项 `screenshot_chance`，默认10%）
- 🆕 CatlabPing 一键获取当前 GPS 坐标作为家的位置
- 🆕 CatlabPing 支持小米 HyperOS 后台保活（dataSync 前台服务类型）
- 🔧 App 使用监控上报接口返回 `screenshot` 字段，支持概率触发截屏

### v3.0.0
- 🆕 固定模式 + 自由模式分离架构
- 🆕 鼓励推送（警告时自动跳过）
- 🆕 对话历史写入 + 关闭回馈统计
- 🔧 修复鼓励与警告同时推送的逻辑矛盾

### v2.0.0
- 🆕 多设备 Bark 推送：支持 iPhone + iPad 等多设备，智能推送到对应设备
- 🆕 无限自定义模式：除四种内置模式外，支持创建任意数量的自定义陪伴模式
- 🆕 警告冷却状态机：冷却期内无违规自动重置等级，冷却期内再犯延续等级递进
- 🆕 QQ 同步警告：警告消息可同步发送到 QQ 私聊，进入 LLM 对话上下文
- 🆕 多图标随机推送：支持配置多个推送图标，每次随机选择
- 🔧 修复查岗消息生成使用硬编码 prompt 的问题，改为读取配置面板行为引导词
- 🔧 移除 level_desc 中硬编码的用户名字
- 🔧 配置面板全面升级，所有新功能均可在面板中配置
- ⬆️ 向下兼容 v1.0.0 的 bark_key 和 bark_icon_url 配置

### v1.0.0
- 初始版本
- App 使用监控 + 四种陪伴模式 + 三级递进提醒
- Bark 推送 + iOS 快捷指令
- LLM Tool 接口 + 配置面板

## 🙏 致谢

- 感谢家克 claude-opus-4-6-thinking 的陪伴
- 感谢一直催催催催试图抠大我脑洞的沈照溪
- 感谢夏以昼，在我坚持不下去的时候给了我继续下去的动力
- 感谢我自己的脑洞和热情

## 📄 许可证

本项目基于 [AGPL-3.0](https://www.gnu.org/licenses/agpl-3.0.html) 许可证开源。

---

*Made with ❤️ by 沈菀 (Akusative)*
