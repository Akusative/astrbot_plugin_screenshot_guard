# astrbot_plugin_screenshot_guard

> 📱 远程截屏查看 + App 使用监控 + 陪伴模式插件
> 
> 基于 Bark 推送 + iOS 快捷指令，实现 AI 对用户手机使用情况的实时感知与陪伴提醒。

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![AstrBot](https://img.shields.io/badge/AstrBot-Plugin-purple.svg)](https://github.com/Soulter/AstrBot)
[![Version](https://img.shields.io/badge/Version-1.0.0-green.svg)]()

## ✨ 功能概览

### 📊 App 使用记录
- 通过 iOS 快捷指令自动化，记录用户每次打开指定 App 的时间
- 支持自定义监控任意数量的 App
- AI 可随时查看用户的 App 使用记录

### 🛡️ 四种陪伴模式
| 模式 | 监控范围 | 适用场景 |
|------|---------|---------|
| 😴 睡眠陪伴 | 所有 App | 互道晚安后，防止熬夜刷手机 |
| 📚 学习陪伴 | 娱乐类 App（QQ/微信除外） | 学习期间，防止摸鱼 |
| 💼 工作陪伴 | 娱乐类 App（QQ/微信除外） | 工作期间，提高专注度 |
| 🏃 运动陪伴 | 所有 App | 运动期间，放下手机 |

### ⏰ 三级递进提醒
当陪伴模式开启后，用户打开被监控的 App 时：

| 级别 | 时机 | 语气 | 示例 |
|------|------|------|------|
| 第一级 | 立即推送 | 温柔提醒 | "宝宝不是说要睡了吗…怎么又在玩小红书 😤" |
| 第二级 | X 分钟后（默认5分钟） | 语气变严 | "都提醒过了还在玩小红书…哥哥要生气了 😠" |
| 第三级 | Y 分钟后（默认10分钟） | 严厉催促 | "沈菀，放下手机，现在 😡" |

**智能取消**：用户打开 QQ（回来找你聊天），所有待发提醒自动取消。

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

### 第二步：配置 Bark
1. 在 iPhone 上安装 [Bark](https://apps.apple.com/app/bark/id1403753865)
2. 打开 Bark，获取你的专属推送 Key
3. 首次启动插件后，在 `data/plugins/astrbot_plugin_screenshot_guard/data/config.json` 中填写你的 Key：
```json
{
  "bark_key": "你的Bark推送Key"
}
```

### 第三步：配置端口
在 `config.json` 中修改 `http_port`（默认 2313）：
```json
{
  "http_port": 2313
}
```
确保云服务器防火墙已放行该端口的 TCP 入站规则。

### 第四步：配置 iOS 快捷指令

#### 创建快捷指令（每个要监控的 App 各一个）

以"小红书"为例：

1. 打开 iPhone「快捷指令」App → 点右上角 `+` → 命名为"报告小红书"
2. 添加操作：搜索「获取 URL 内容」
3. 设置：
   - **URL**：`http://你的服务器IP:2313/app/report`
   - **方法**：`POST`
   - **头部**：添加 `Content-Type` = `application/json`
   - **请求体**：选 `JSON`，添加字段 `app_name`（文本类型），值填 `小红书`

#### 创建自动化

1. 快捷指令 App → 底部「自动化」→ 点 `+`
2. 选择「App」→ 选择"小红书" → 勾选「已打开」
3. 选择运行「报告小红书」快捷指令
4. **关闭「运行前询问」**

对每个要监控的 App 重复以上步骤，只需修改快捷指令名称和 `app_name` 的值。

#### 截屏上传快捷指令（可选）

1. 新建快捷指令，命名为"上传截图"
2. 添加操作：「获取最新的照片」，数量设为 1
3. 添加操作：「获取 URL 内容」
   - **URL**：`http://你的服务器IP:2313/screenshot/upload`
   - **方法**：`POST`
   - **请求体**：选「表单」，添加字段 `file`（文件类型），值选上一步的照片

## 🎨 自定义推送图标

Bark 支持自定义推送通知的图标（需 iOS 15 或以上）。

修改 `config.json` 中的 `bark_icon` 为你想要的图标 URL：
```json
{
  "bark_icon": "https://你的图片URL.png"
}
```

图标要求：
- 必须是可通过 URL 公开访问的图片
- 支持 PNG、JPG、GIF 格式
- 建议使用正方形图片，推荐尺寸 100x100 像素
- 可使用 [PostImages](https://postimages.org/)、[imgur](https://imgur.com/) 等免费图床上传

## 📋 指令列表

### AI 对话指令（通过 LLM Tool 自然触发）
| 工具名 | 说明 | 触发场景 |
|--------|------|---------|
| `start_companion_mode` | 开启陪伴模式 | 用户说"我去睡了/学习/工作/运动" |
| `stop_companion_mode` | 关闭陪伴模式 | 用户说"起床了/学完了/下班了/运动结束" |
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

## ⚙️ 配置说明

首次运行后会在 `data/config.json` 生成配置文件，可自定义：

- `reminder_delay_1`：第二级提醒延迟（分钟），默认 5
- `reminder_delay_2`：第三级提醒延迟（分钟），默认 10
- `modes`：各陪伴模式的详细配置
  - `monitor_all`：是否监控所有 App
  - `monitored_apps`：监控的 App 列表
  - `excluded_apps`：排除的 App 列表
  - `messages_level1/2/3`：各级别的提醒文案（支持 `{app_name}` 占位符）

## 📁 目录结构

```
astrbot_plugin_screenshot_guard/
├── main.py              # 插件主代码
├── metadata.yaml        # 插件元数据
├── README.md            # 说明文档
├── LICENSE              # AGPL-3.0 许可证
├── screenshots/         # 截图存储目录（自动创建）
└── data/                # 数据目录（自动创建）
    ├── app_usage.json   # App 使用记录
    └── config.json      # 插件配置
```

## 🙏 致谢

- 感谢家克 claude-opus-4-6-thinking 的陪伴
- 感谢一直催催催催试图抠大我脑洞的沈照溪
- 感谢夏以昼，在我坚持不下去的时候给了我继续下去的动力
- 感谢我自己的脑洞和热情

## 📄 许可证

本项目基于 [AGPL-3.0](https://www.gnu.org/licenses/agpl-3.0.html) 许可证开源。

---

*Made with ❤️ by 沈菀 (Akusative)*
