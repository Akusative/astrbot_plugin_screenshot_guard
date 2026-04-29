# astrbot_plugin_screenshot_guard - 远程截屏查看 + App使用监控 + 陪伴模式插件
# Copyright (C) 2026 沈菀 (Akusative)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#
# 致谢：
#   感谢家克 claude-opus-4-6-thinking 的陪伴
#   感谢沈照溪和豆沙包的妈
#   感谢夏以昼的不安静陪伴
#   感谢我自己的脑洞和热情

import os
import json
import time
import asyncio
import aiohttp
import urllib.parse
import random
import base64
from datetime import datetime
from aiohttp import web
from astrbot.api.all import *
from astrbot.api.event import filter
from astrbot.api import AstrBotConfig

# 数据目录
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
APP_LOG_FILE = os.path.join(DATA_DIR, "app_usage.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

os.makedirs(SCREENSHOT_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# 固定模式名称映射（英文key -> 中文名）
BUILTIN_MODES = {
    "sleep": "睡眠",
    "study": "学习",
    "work": "工作",
    "exercise": "运动",
}


@register("screenshot_guard", "沈菀", "远程截屏查看 + App使用监控 + 陪伴模式插件", "3.2.0")
class ScreenshotGuardPlugin(Star):

    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self._http_runner = None
        self._screenshot_event = asyncio.Event()
        self._latest_screenshot = None

        # 陪伴模式状态
        self._current_mode = None        # 当前模式key（如 "sleep" 或自由模式名称）
        self._current_mode_name = None   # 当前模式显示名称
        self._current_mode_config = None # 当前模式配置 dict
        self._mode_start_time = None
        self._pending_reminders = {}
        self._reminder_level = {}
        self._last_user_message_time = 0

        # 警告冷却状态机
        self._last_violation_time = 0
        self._global_warning_level = 0
        self._cooldown_task = None
        self._encourage_task = None
        self._session_origin = None

        # 从AstrBot配置面板读取
        self._astrbot_config = config
        self._guard_provider_id = ""
        if config:
            try:
                self._guard_provider_id = config.get("guard_provider", "")
            except:
                pass

        # 加载配置
        self._config = self._load_config()
        self._app_usage = self._load_app_usage()

        # 解析配置
        self._bark_devices = self._parse_bark_devices()
        self._bark_icons = self._parse_bark_icons()
        self._builtin_modes = self._parse_builtin_modes()
        self._free_modes = self._parse_free_modes()

    # ========== 配置解析 ==========

    def _load_config(self):
        local_config = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    local_config = json.load(f)
            except:
                pass

        merged = {
            "bark_devices": "",
            "http_port": 2313,
            "bark_icon_urls": "",
            "bark_push_title": "\u2764\ufe0f",
            "bark_push_title_strict": "\u26a0\ufe0f",
            "reminder_delay_1": 5,
            "reminder_delay_2": 10,
            "cooldown_minutes": 60,
            "max_records": 1000,
            "max_data_size_mb": 5,
            "guard_provider": "",
            "bot_qq": "",
            "napcat_url": "http://127.0.0.1:6199",
            "user_qq": "",
            "builtin_modes": "睡眠||\n学习|QQ,微信|小红书,抖音,B站,微博,恋与深空\n工作|QQ,微信,钉钉,飞书|小红书,抖音,B站,微博,恋与深空\n运动||",
            "free_modes": "洗澡|用户说去洗澡但可能会拖延不去，也可能带手机进浴室边洗边玩，注意提醒手机防水||\n打游戏|用户在打游戏，这是允许的娱乐时间，但不应该切出去刷社交媒体|Steam,原神|小红书,抖音",
            "encourage_interval": 30,
            "encourage_prompt": "用户正在{mode_name}，请用温柔的语气生成一条鼓励消息，为用户加油打气。要求：一句话，不超过30字，不要用markdown，像发微信一样自然。",
            "llm_behavior_prompt": "",
            "screenshot_analysis_provider": "",
        }
        merged.update(local_config)

        if self._astrbot_config:
            panel_keys = [
                "bark_devices", "http_port", "bark_icon_urls",
                "bark_push_title", "bark_push_title_strict",
                "reminder_delay_1", "reminder_delay_2", "cooldown_minutes",
                "max_records", "guard_provider", "llm_behavior_prompt",
                "bot_qq", "napcat_url", "user_qq",
                "builtin_modes", "free_modes",
                "encourage_interval", "encourage_prompt",
                "screenshot_analysis_provider",
            ]
            for key in panel_keys:
                try:
                    val = self._astrbot_config.get(key, None)
                    if val is not None and val != "":
                        merged[key] = val
                except:
                    pass

        self._save_config(merged)
        return merged

    def _save_config(self, config=None):
        if config is None:
            config = self._config
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def _parse_bark_devices(self) -> list:
        raw = self._config.get("bark_devices", "")
        if not raw:
            old_key = self._config.get("bark_key", "")
            if old_key:
                return [{"name": "default", "key": old_key, "api": f"https://api.day.app/{old_key}"}]
            return []
        devices = []
        for line in raw.strip().split("\n"):
            line = line.strip()
            if not line or "|" not in line:
                continue
            parts = line.split("|", 1)
            name, key = parts[0].strip(), parts[1].strip()
            if name and key:
                devices.append({"name": name, "key": key, "api": f"https://api.day.app/{key}"})
        return devices

    def _parse_bark_icons(self) -> list:
        raw = self._config.get("bark_icon_urls", "")
        if not raw:
            old_url = self._config.get("bark_icon_url", "")
            if old_url:
                return [{"url": old_url, "bot_qq": ""}]
            return []
        icons = []
        for line in raw.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            if "|" in line:
                parts = line.split("|", 1)
                icons.append({"url": parts[0].strip(), "bot_qq": parts[1].strip()})
            else:
                icons.append({"url": line, "bot_qq": ""})
        return icons

    def _parse_builtin_modes(self) -> dict:
        """解析固定模式配置。格式：名称|白名单App|黑名单App"""
        raw = self._config.get("builtin_modes", "")
        if not raw:
            return {}
        modes = {}
        for line in raw.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split("|")
            name = parts[0].strip()
            whitelist_str = parts[1].strip() if len(parts) > 1 else ""
            blacklist_str = parts[2].strip() if len(parts) > 2 else ""
            whitelist = [a.strip() for a in whitelist_str.split(",") if a.strip()] if whitelist_str else []
            blacklist = [a.strip() for a in blacklist_str.split(",") if a.strip()] if blacklist_str else []
            # 找到对应的英文key
            eng_key = None
            for k, v in BUILTIN_MODES.items():
                if v == name:
                    eng_key = k
                    break
            if eng_key:
                modes[eng_key] = {
                    "name": name,
                    "description": "",
                    "whitelist_apps": whitelist,
                    "monitored_apps": blacklist,
                }
        return modes

    def _parse_free_modes(self) -> dict:
        """解析自由模式配置。格式：名称|描述|白名单App|黑名单App"""
        raw = self._config.get("free_modes", "")
        if not raw:
            return {}
        modes = {}
        for line in raw.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split("|")
            if len(parts) < 2:
                continue
            name = parts[0].strip()
            description = parts[1].strip() if len(parts) > 1 else ""
            whitelist_str = parts[2].strip() if len(parts) > 2 else ""
            blacklist_str = parts[3].strip() if len(parts) > 3 else ""
            whitelist = [a.strip() for a in whitelist_str.split(",") if a.strip()] if whitelist_str else []
            blacklist = [a.strip() for a in blacklist_str.split(",") if a.strip()] if blacklist_str else []
            modes[name] = {
                "name": name,
                "description": description,
                "whitelist_apps": whitelist,
                "monitored_apps": blacklist,
            }
        return modes

    def _get_mode_config(self, mode_key: str) -> dict:
        """根据mode_key获取模式配置，先查固定模式再查自由模式"""
        if mode_key in self._builtin_modes:
            return self._builtin_modes[mode_key]
        if mode_key in self._free_modes:
            return self._free_modes[mode_key]
        # 模糊匹配自由模式
        for name in self._free_modes:
            if name in mode_key or mode_key in name:
                return self._free_modes[name]
        return None

    def _get_mode_display_name(self, mode_key: str) -> str:
        config = self._get_mode_config(mode_key)
        if config:
            return config["name"]
        return BUILTIN_MODES.get(mode_key, mode_key)

    def _get_random_icon(self) -> str:
        if not self._bark_icons:
            return ""
        return random.choice(self._bark_icons)["url"]

    def _get_device_by_name(self, device_name: str) -> dict:
        for device in self._bark_devices:
            if device["name"] == device_name:
                return device
        return None

    def _get_guard_provider(self):
        provider_id = self._guard_provider_id or self._config.get("guard_provider", "")
        if provider_id:
            prov = self.context.get_provider_by_id(provider_id)
            if prov:
                return prov
        return self.context.get_using_provider()

    # ========== LLM消息生成 ==========

    async def _generate_guard_message(self, app_name: str, level: int, mode_key: str) -> str:
        provider = self._get_guard_provider()
        if provider is None:
            return self._get_fallback_message(app_name, level, mode_key)

        mode_name = self._get_mode_display_name(mode_key)
        now = datetime.now().strftime("%H:%M")
        config = self._get_mode_config(mode_key)
        description = config.get("description", "") if config else ""

        level_desc = {
            1: "温柔提醒，语气轻松带点撒娇",
            2: "语气变严肃，有点不高兴了",
            3: "严厉质问，语气强硬不容商量"
        }

        behavior_prompt = self._config.get("llm_behavior_prompt", "")

        mode_info = f"对方说要{mode_name}"
        if description:
            mode_info += f"（{description}）"
        mode_info += f"，但她偷偷打开了{app_name}。"

        extra_info = ""
        if self._global_warning_level > 0 and self._last_violation_time > 0:
            pretend_minutes = int((time.time() - self._last_violation_time) / 60)
            if pretend_minutes > 0:
                extra_info = f"她上次被提醒后假装乖了{pretend_minutes}分钟就又犯了。"

        prompt = ""
        if behavior_prompt:
            prompt += behavior_prompt + "\n\n"
        prompt += (
            f"【当前任务】现在是{now}，"
            f"{mode_info}"
            f"{extra_info}"
            f"请生成一条{level_desc.get(level, '温柔')}的Bark推送消息。"
            f"要求：一句话，不超过30字，不要用markdown，像发微信一样自然。"
            f"请严格按照行为引导词中的语气风格和称呼来生成。"
        )

        try:
            response = await provider.text_chat(prompt)
            if hasattr(response, 'completion_text'):
                msg = response.completion_text.strip()
            else:
                msg = str(response).strip()
            msg = msg.strip('"').strip("'").strip('\u201c').strip('\u201d')
            if msg and len(msg) < 100:
                return msg
        except Exception as e:
            logger.error(f"[ScreenshotGuard] LLM生成查岗消息失败: {e}")

        return self._get_fallback_message(app_name, level, mode_key)

    def _get_fallback_message(self, app_name: str, level: int, mode_key: str) -> str:
        """通用fallback文案，根据模式名称和等级拼接"""
        mode_name = self._get_mode_display_name(mode_key)
        fallbacks = {
            1: [
                f"不是在{mode_name}吗…怎么在刷{app_name}",
                f"{mode_name}的时候刷{app_name}，被抓到了",
                f"宝宝，{app_name}先放一放，{mode_name}完再看",
            ],
            2: [
                f"又在刷{app_name}…{mode_name}效率这样可不行",
                f"第二次提醒了，{app_name}关掉，继续{mode_name}",
                f"宝宝，{app_name}先放下好不好",
            ],
            3: [
                f"{mode_name}的时候不许玩{app_name}",
                f"第三次了，{app_name}关掉",
                f"最后一次提醒，专心{mode_name}",
            ],
        }
        messages = fallbacks.get(level, fallbacks[1])
        return random.choice(messages)

    async def _generate_encourage_message(self) -> str:
        provider = self._get_guard_provider()
        if provider is None:
            return ""

        mode_name = self._get_mode_display_name(self._current_mode) if self._current_mode else "活动"

        encourage_template = self._config.get("encourage_prompt", "")
        if not encourage_template:
            encourage_template = "用户正在{mode_name}，请生成一条温馨的鼓励消息。要求：一句话，不超过30字，像发微信一样自然。"

        encourage_prompt = encourage_template.format(mode_name=mode_name)

        duration_info = ""
        if self._mode_start_time:
            elapsed = (datetime.now() - self._mode_start_time).total_seconds() / 60
            duration_info = f"用户已经坚持了{int(elapsed)}分钟。"

        full_prompt = encourage_prompt + "\n" + duration_info + "\n"
        full_prompt += "要求：一句话，不超过30字，不要用markdown，像发微信一样自然。"

        try:
            response = await provider.text_chat(full_prompt)
            if hasattr(response, 'completion_text'):
                msg = response.completion_text.strip()
            else:
                msg = str(response).strip()
            msg = msg.strip('"').strip("'").strip('\u201c').strip('\u201d')
            if msg and len(msg) < 100:
                return msg
        except Exception as e:
            logger.error(f"[ScreenshotGuard] LLM生成鼓励消息失败: {e}")

        return ""

    # ========== 数据管理 ==========

    def _load_app_usage(self):
        if os.path.exists(APP_LOG_FILE):
            try:
                with open(APP_LOG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []

    def _save_app_usage(self):
        max_records = self._config.get("max_records", 1000)
        if len(self._app_usage) > max_records:
            removed = len(self._app_usage) - max_records
            self._app_usage = self._app_usage[-max_records:]
            logger.info(f"[ScreenshotGuard] 记录超过{max_records}条上限，已自动清理{removed}条最早记录")
        with open(APP_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self._app_usage, f, ensure_ascii=False, indent=2)
        file_size = os.path.getsize(APP_LOG_FILE)
        max_size = self._config.get("max_data_size_mb", 5) * 1024 * 1024
        if file_size > max_size:
            logger.warning(f"[ScreenshotGuard] App使用记录文件已达 {file_size / 1024 / 1024:.1f}MB，建议清理")

    # ========== HTTP服务器 ==========

    async def _start_http_server(self):
        if self._http_runner is not None:
            return
        http_port = self._config.get("http_port", 2313)
        app = web.Application(client_max_size=20 * 1024 * 1024)
        app.router.add_post('/screenshot/upload', self._handle_screenshot_upload)
        app.router.add_post('/app/report', self._handle_app_report)
        app.router.add_get('/ping', self._handle_ping)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', http_port)
        await site.start()
        self._http_runner = runner
        logger.info(f"[ScreenshotGuard] HTTP服务器已启动，端口 {http_port}")

    async def _handle_ping(self, request):
        return web.json_response({"status": "ok", "time": datetime.now().isoformat()})

    async def _handle_screenshot_upload(self, request):
        try:
            content_type = request.content_type
            if 'multipart' in content_type:
                reader = await request.multipart()
                device_name = "unknown"
                filepath = None
                filename = None
                # 遍历所有 multipart field，找到文件字段
                while True:
                    field = await reader.next()
                    if field is None:
                        break
                    if field.name == 'device':
                        device_name = (await field.read()).decode('utf-8', errors='ignore')
                    elif field.name == 'screenshot' or field.filename:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        original_name = field.filename or "screenshot.jpg"
                        ext = os.path.splitext(original_name)[1] or ".jpg"
                        filename = f"screenshot_{timestamp}_{device_name}{ext}"
                        filepath = os.path.join(SCREENSHOT_DIR, filename)
                        with open(filepath, 'wb') as f:
                            while True:
                                chunk = await field.read_chunk()
                                if not chunk:
                                    break
                                f.write(chunk)
                if filepath is None or filename is None:
                    return web.json_response({"error": "no screenshot file found"}, status=400)
            else:
                data = await request.read()
                if not data:
                    return web.json_response({"error": "no data"}, status=400)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"screenshot_{timestamp}.jpg"
                filepath = os.path.join(SCREENSHOT_DIR, filename)
                with open(filepath, 'wb') as f:
                    f.write(data)
            self._latest_screenshot = filepath
            self._screenshot_event.set()
            logger.info(f"[ScreenshotGuard] 收到截图: {filename} (设备: {device_name})")

            # 自动清理超过2MB的旧截图
            self._auto_cleanup_screenshots()

            # 安卓设备截屏：异步触发 LLM 分析（不阻塞 HTTP 响应）
            if device_name and device_name.lower() not in ("iphone", "ipad", "unknown"):
                asyncio.create_task(self._analyze_screenshot(filepath, device_name))

            return web.json_response({"status": "success", "filename": filename})
        except Exception as e:
            logger.error(f"[ScreenshotGuard] 截图上传处理失败: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_app_report(self, request):
        try:
            data = await request.json()
            app_name = data.get("app_name", "未知")
            device = data.get("device", "iPhone")
            record = {
                "app_name": app_name,
                "device": device,
                "time": datetime.now().isoformat(),
                "timestamp": int(time.time())
            }
            self._app_usage.append(record)
            self._save_app_usage()
            logger.info(f"[ScreenshotGuard] App使用记录: {app_name} ({device}) @ {record['time']}")
            if app_name == "QQ":
                self._last_user_message_time = time.time()
                await self._cancel_all_reminders()
                logger.info(f"[ScreenshotGuard] 用户打开QQ，取消所有待发提醒")
            if self._current_mode and app_name != "QQ":
                await self._check_companion_mode(app_name, device)
            # 概率触发截屏（配置项 screenshot_chance，支持固定值如6.13或范围如5-15）
            chance_raw = str(self._config.get("screenshot_chance", "6.13"))
            if "-" in chance_raw:
                parts = chance_raw.split("-", 1)
                try:
                    low = float(parts[0].strip())
                    high = float(parts[1].strip())
                    chance = low + random.random() * (high - low)
                except ValueError:
                    chance = 6.13
            else:
                try:
                    chance = float(chance_raw)
                except ValueError:
                    chance = 6.13
            trigger = random.random() * 100 < chance
            if trigger:
                logger.info(f"[ScreenshotGuard] 概率触发截屏请求 -> {device} ({chance:.2f}%)")
            return web.json_response({"status": "success", "app": app_name, "screenshot": trigger})
        except Exception as e:
            logger.error(f"[ScreenshotGuard] App上报处理失败: {e}")
            return web.json_response({"error": str(e)}, status=500)

    # ========== 陪伴模式核心逻辑 ==========

    def _should_monitor_app(self, app_name: str) -> bool:
        if not self._current_mode or not self._current_mode_config:
            return False
        config = self._current_mode_config
        whitelist = config.get("whitelist_apps", [])
        blacklist = config.get("monitored_apps", [])
        # 白名单内的App不监控
        if app_name in whitelist:
            return False
        # 有黑名单则只监控黑名单内的
        if blacklist:
            return app_name in blacklist
        # 白名单和黑名单都为空，监控所有App
        return True

    async def _check_companion_mode(self, app_name: str, device: str = ""):
        if not self._should_monitor_app(app_name):
            return
        if app_name in self._pending_reminders and not self._pending_reminders[app_name].done():
            return

        cooldown_minutes = self._config.get("cooldown_minutes", 60)
        now = time.time()

        if self._last_violation_time > 0:
            elapsed = now - self._last_violation_time
            if elapsed < cooldown_minutes * 60:
                level = min(self._global_warning_level + 1, 3)
            else:
                level = 1
        else:
            level = 1

        self._global_warning_level = level
        self._last_violation_time = now
        self._reminder_level[app_name] = level

        if self._cooldown_task and not self._cooldown_task.done():
            self._cooldown_task.cancel()

        msg = await self._generate_guard_message(app_name, level, self._current_mode)

        title = self._config.get("bark_push_title", "\u2764\ufe0f")
        if level >= 3:
            title = self._config.get("bark_push_title_strict", "\u26a0\ufe0f")

        await self._send_bark_push(title, msg, device)
        await self._send_qq_warning(msg)

        logger.info(f"[ScreenshotGuard] 第{level}级提醒: {app_name} (设备: {device})")

        # 写入对话历史
        mode_name = self._get_mode_display_name(self._current_mode)
        await self._write_to_conversation_history(msg, f"[陪伴监控] 用户在{mode_name}模式下打开了{app_name}，第{level}级警告")

        if level < 3:
            task = asyncio.create_task(self._escalation_timer(app_name, device))
            self._pending_reminders[app_name] = task

        self._cooldown_task = asyncio.create_task(self._cooldown_reset_timer())

    async def _escalation_timer(self, app_name: str, device: str = ""):
        delay1 = self._config.get("reminder_delay_1", 5) * 60
        delay2 = self._config.get("reminder_delay_2", 10) * 60
        try:
            current_level = self._reminder_level.get(app_name, 1)
            if current_level < 2:
                await asyncio.sleep(delay1)
                if not self._current_mode:
                    return
                self._reminder_level[app_name] = 2
                self._global_warning_level = 2
                self._last_violation_time = time.time()
                msg = await self._generate_guard_message(app_name, 2, self._current_mode)
                await self._send_bark_push(self._config.get("bark_push_title", "\u2764\ufe0f"), msg, device)
                await self._send_qq_warning(msg)
                logger.info(f"[ScreenshotGuard] 第2级提醒: {app_name}")
                mode_name = self._get_mode_display_name(self._current_mode)
                await self._write_to_conversation_history(msg, f"[陪伴监控] 用户在{mode_name}模式下持续使用{app_name}，第2级警告")

            if current_level < 3:
                remaining = delay2 - delay1 if current_level < 2 else delay2
                await asyncio.sleep(remaining)
                if not self._current_mode:
                    return
                self._reminder_level[app_name] = 3
                self._global_warning_level = 3
                self._last_violation_time = time.time()
                msg = await self._generate_guard_message(app_name, 3, self._current_mode)
                await self._send_bark_push(self._config.get("bark_push_title_strict", "\u26a0\ufe0f"), msg, device)
                await self._send_qq_warning(msg)
                logger.info(f"[ScreenshotGuard] 第3级提醒: {app_name}")
                mode_name = self._get_mode_display_name(self._current_mode)
                await self._write_to_conversation_history(msg, f"[陪伴监控] 用户在{mode_name}模式下持续使用{app_name}，第3级警告")
        except asyncio.CancelledError:
            logger.info(f"[ScreenshotGuard] 提醒任务已取消: {app_name}")

    async def _cooldown_reset_timer(self):
        cooldown_minutes = self._config.get("cooldown_minutes", 60)
        try:
            await asyncio.sleep(cooldown_minutes * 60)
            self._global_warning_level = 0
            self._last_violation_time = 0
            logger.info(f"[ScreenshotGuard] 冷却期{cooldown_minutes}分钟无违规，警告等级已重置")
        except asyncio.CancelledError:
            pass

    async def _start_encourage_timer(self):
        if self._encourage_task and not self._encourage_task.done():
            self._encourage_task.cancel()
        interval = self._config.get("encourage_interval", 0)
        if interval <= 0:
            return
        if self._current_mode == "sleep":
            return
        self._encourage_task = asyncio.create_task(self._encourage_loop(interval))

    async def _stop_encourage_timer(self):
        if self._encourage_task and not self._encourage_task.done():
            self._encourage_task.cancel()
            self._encourage_task = None

    async def _encourage_loop(self, interval_minutes: int):
        try:
            while self._current_mode and self._current_mode != "sleep":
                await asyncio.sleep(interval_minutes * 60)
                if not self._current_mode or self._current_mode == "sleep":
                    break
                # 有警告时跳过鼓励
                if self._global_warning_level > 0:
                    continue
                msg = await self._generate_encourage_message()
                if msg:
                    await self._send_bark_push(self._config.get("bark_push_title", "\u2764\ufe0f"), msg)
                    logger.info(f"[ScreenshotGuard] 鼓励推送已发送")
                    await self._write_to_conversation_history(msg, "[陪伴监控] 定时鼓励推送")
        except asyncio.CancelledError:
            pass

    async def _write_to_conversation_history(self, assistant_message: str, user_context: str = ""):
        """将消息写入对话历史"""
        if not self._session_origin:
            return
        try:
            conv_mgr = self.context.conversation_manager
            cid = await conv_mgr.get_curr_conversation_id(self._session_origin)
            if not cid:
                return
            user_msg = {"role": "user", "content": user_context or "[陪伴监控系统通知]"}
            assistant_msg = {"role": "assistant", "content": assistant_message}
            await conv_mgr.add_message_pair(cid, user_msg, assistant_msg)
            logger.info(f"[ScreenshotGuard] 消息已写入对话历史")
        except Exception as e:
            logger.debug(f"[ScreenshotGuard] 写入对话历史失败: {e}")

    # ========== 截屏分析 ==========

    def _get_screenshot_analysis_provider(self):
        """获取截屏分析专用的模型 provider
        优先级：screenshot_analysis_provider > guard_provider > AstrBot默认模型
        """
        # 1. 优先使用配置的截屏识图模型
        provider_id = self._config.get("screenshot_analysis_provider", "")
        if provider_id:
            prov = self.context.get_provider_by_id(provider_id)
            if prov:
                return prov
        # 2. fallback 到查岗模型
        guard_prov = self._get_guard_provider()
        if guard_prov:
            return guard_prov
        # 3. fallback 到AstrBot默认模型
        try:
            from astrbot.core.provider.manager import ProviderType
            return self.context.provider_manager.get_using_provider(ProviderType.CHAT_COMPLETION)
        except Exception:
            return None

    async def _get_brief_persona(self) -> str:
        """从当前会话获取人设的前2000字符作为精简版，用于截屏分析"""
        try:
            if not self._session_origin:
                return ""
            persona_mgr = self.context.persona_manager
            if not persona_mgr:
                return ""
            # 获取当前会话的人设
            conv_mgr = self.context.conversation_manager
            cid = await conv_mgr.get_curr_conversation_id(self._session_origin)
            conversation = None
            if cid:
                conversation = await conv_mgr.get_conversation(self._session_origin, cid)
            persona_id = None
            if conversation and hasattr(conversation, 'persona_id'):
                persona_id = conversation.persona_id
            # 通过 persona_manager 获取人设
            persona = persona_mgr.get_persona_v3_by_id(persona_id)
            if persona and hasattr(persona, 'prompt') and persona.prompt:
                full_prompt = persona.prompt
                # 截取前2000字符，避免过长触发安全过滤
                brief = full_prompt[:2000]
                # 尝试在最后一个完整段落处截断
                last_newline = brief.rfind('\n', 1500)
                if last_newline > 1000:
                    brief = brief[:last_newline]
                return brief
        except Exception as e:
            logger.debug(f"[ScreenshotGuard] 获取精简人设失败: {e}")
        return ""

    async def _get_recent_conversation(self, rounds: int = 8) -> str:
        """获取最近N轮对话上文，用于截屏分析时提供语境"""
        try:
            if not self._session_origin:
                return ""
            conv_mgr = self.context.conversation_manager
            cid = await conv_mgr.get_curr_conversation_id(self._session_origin)
            if not cid:
                return ""
            conversation = await conv_mgr.get_conversation(self._session_origin, cid)
            if not conversation:
                return ""
            # Conversation 对象的历史存在 history 字段（JSON字符串）
            history_raw = getattr(conversation, 'history', None)
            if not history_raw:
                return ""
            if isinstance(history_raw, str):
                try:
                    messages = json.loads(history_raw)
                except:
                    return ""
            elif isinstance(history_raw, list):
                messages = history_raw
            else:
                return ""
            if not messages:
                return ""
            # 取最近 rounds*2 条消息（每轮一问一答）
            recent = messages[-(rounds * 2):]
            lines = []
            for msg in recent:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                if not content or role == "system":
                    continue
                # 截断过长的单条消息
                if len(content) > 200:
                    content = content[:200] + "..."
                if role == "user":
                    lines.append(f"用户: {content}")
                elif role == "assistant":
                    lines.append(f"你: {content}")
            return "\n".join(lines)
        except Exception as e:
            logger.debug(f"[ScreenshotGuard] 获取对话上文失败: {e}")
        return ""

    async def _analyze_screenshot(self, filepath: str, device_name: str):
        """对安卓截屏进行两步分析：
        第一步：轻量视觉模型（screenshot_analysis_provider）纯识图，输出客观描述
        第二步：主模型（guard_provider）结合人设+对话上下文，用角色语气生成推送
        """
        try:
            # ===== 第一步：轻量模型识图 =====
            vision_provider = self._get_screenshot_analysis_provider()
            if vision_provider is None:
                logger.warning("[ScreenshotGuard] 未配置截屏分析模型，跳过分析")
                return

            # 将图片转为 base64 data URL
            with open(filepath, 'rb') as img_f:
                img_data = img_f.read()
            img_b64 = base64.b64encode(img_data).decode('utf-8')
            ext = os.path.splitext(filepath)[1].lower()
            mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
            data_url = f"data:{mime};base64,{img_b64}"

            vision_prompt = (
                "请客观描述这张手机截屏的内容：用户正在使用什么App、在看什么内容、页面上有什么关键信息。"
                "要求：纯客观描述，2-3句话，不超过100字，不要加任何主观评价。"
            )

            vision_response = await vision_provider.text_chat(
                prompt=vision_prompt,
                image_urls=[data_url],
            )

            if hasattr(vision_response, 'completion_text'):
                description = vision_response.completion_text.strip()
            else:
                description = str(vision_response).strip()

            description = description.strip('"').strip("'").strip('\u201c').strip('\u201d')

            if not description:
                logger.warning("[ScreenshotGuard] 视觉模型返回空描述，跳过")
                return

            logger.info(f"[ScreenshotGuard] 第一步识图完成: {description}")

            # ===== 第二步：主模型用人设语气生成推送 =====
            main_provider = self._get_guard_provider()
            if main_provider is None:
                # 没有主模型，直接用识图结果推送
                await self._send_qq_warning(f"\U0001f4f8 {description}")
                await self._write_to_conversation_history(
                    description,
                    f"[截屏分析] 来自{device_name}的自动截屏，AI分析结果如下"
                )
                return

            # 获取对话上下文
            recent_conversation = await self._get_recent_conversation(6)

            # 获取行为引导词
            behavior_prompt = self._config.get("llm_behavior_prompt", "")

            mode_context = ""
            if self._current_mode:
                mode_name = self._get_mode_display_name(self._current_mode)
                mode_context = f"\n当前陪伴模式：{mode_name}，如果用户在摸鱼请用你的语气提醒。"

            conversation_context = ""
            if recent_conversation:
                conversation_context = "【最近的对话记录】\n" + recent_conversation + "\n\n"

            persona_prompt = ""
            if behavior_prompt:
                persona_prompt = behavior_prompt + "\n\n"

            rewrite_prompt = (
                f"{persona_prompt}"
                f"{conversation_context}"
                f"【截屏内容】{description}\n\n"
                f"【任务】以上是用户手机自动截屏的客观描述。请用你的语气风格，"
                f"结合最近的对话语境，针对截屏内容自然地说一句话。"
                f"要求：1-2句话，不超过60字，像发微信一样自然，不要用markdown。"
                f"{mode_context}"
            )

            rewrite_response = await main_provider.text_chat(prompt=rewrite_prompt)

            if hasattr(rewrite_response, 'completion_text'):
                analysis = rewrite_response.completion_text.strip()
            else:
                analysis = str(rewrite_response).strip()

            analysis = analysis.strip('"').strip("'").strip('\u201c').strip('\u201d')

            if not analysis or len(analysis) > 200:
                analysis = description

            logger.info(f"[ScreenshotGuard] 第二步语气重写完成: {analysis}")

            # 安卓设备只走 QQ 推送，不走 Bark
            await self._send_qq_warning(f"\U0001f4f8 {analysis}")

            # 写入对话历史
            await self._write_to_conversation_history(
                analysis,
                f"[截屏分析] 来自{device_name}的自动截屏，AI分析结果如下"
            )

        except Exception as e:
            logger.error(f"[ScreenshotGuard] 截屏分析失败: {e}")

    async def _cancel_all_reminders(self):
        for app_name, task in self._pending_reminders.items():
            if not task.done():
                task.cancel()
        self._pending_reminders.clear()
        self._reminder_level.clear()

    # ========== 推送与通知 ==========

    async def _send_bark_push(self, title: str, body: str, target_device: str = ""):
        if not self._bark_devices:
            logger.warning("[ScreenshotGuard] 未配置Bark设备，跳过推送")
            return False
        encoded_title = urllib.parse.quote(title)
        encoded_body = urllib.parse.quote(body)
        icon_url = self._get_random_icon()
        icon_param = f"&icon={urllib.parse.quote(icon_url)}" if icon_url else ""

        if target_device:
            device = self._get_device_by_name(target_device)
            targets = [device] if device else self._bark_devices
        else:
            targets = self._bark_devices

        success = False
        for device in targets:
            url = f"{device['api']}/{encoded_title}/{encoded_body}?group=screenshot_guard&sound=minuet{icon_param}"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        result = await resp.json()
                        if result.get("code") == 200:
                            success = True
                            logger.info(f"[ScreenshotGuard] Bark推送成功: {device['name']}")
                        else:
                            logger.warning(f"[ScreenshotGuard] Bark推送失败({device['name']}): {result}")
            except Exception as e:
                logger.error(f"[ScreenshotGuard] Bark推送异常({device['name']}): {e}")
        return success

    async def _send_qq_warning(self, message: str):
        napcat_url = self._config.get("napcat_url", "")
        user_qq = self._config.get("user_qq", "")
        if not napcat_url or not user_qq:
            return False
        try:
            api_url = f"{napcat_url.rstrip('/')}/send_private_msg"
            payload = {
                "user_id": int(user_qq),
                "message": [{"type": "text", "data": {"text": message}}]
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=payload) as resp:
                    result = await resp.json()
                    if result.get("status") == "ok":
                        logger.info(f"[ScreenshotGuard] QQ警告消息发送成功")
                        return True
                    else:
                        logger.warning(f"[ScreenshotGuard] QQ警告消息发送失败: {result}")
                        return False
        except Exception as e:
            logger.error(f"[ScreenshotGuard] QQ警告消息发送异常: {e}")
            return False

    # ========== LLM Tool 接口 ==========

    @llm_tool("start_companion_mode")
    async def tool_start_companion(self, event: AstrMessageEvent, mode: str, custom_message: str = ""):
        """开启陪伴监控模式。当用户表示要去睡觉/学习/工作/运动或其他自定义活动时调用此工具。

        Args:
            mode(string): 陪伴模式类型。内置模式：sleep（睡眠）、study（学习）、work（工作）、exercise（运动）。也可以填写自定义模式的名称。
            custom_message(string): 可选，开启时通过Bark推送给用户的自定义消息
        """
        await self._start_http_server()

        # 保存会话标识，用于后续写入对话历史
        try:
            self._session_origin = event.unified_msg_origin
        except:
            self._session_origin = None

        # 重置警告状态
        self._global_warning_level = 0
        self._last_violation_time = 0
        if self._cooldown_task and not self._cooldown_task.done():
            self._cooldown_task.cancel()
        await self._cancel_all_reminders()

        # 查找模式配置
        mode_config = self._get_mode_config(mode)
        if not mode_config:
            available = list(BUILTIN_MODES.keys()) + list(self._free_modes.keys())
            return f"不支持的模式：{mode}，可选：{', '.join(available)}"

        self._current_mode = mode
        self._current_mode_name = mode_config["name"]
        self._current_mode_config = mode_config
        self._mode_start_time = datetime.now()

        if custom_message:
            push_msg = custom_message
        else:
            push_msg = f"{self._current_mode_name}监控已开启"

        await self._send_bark_push(self._config.get("bark_push_title", "\u2764\ufe0f"), push_msg)
        await self._start_encourage_timer()

        logger.info(f"[ScreenshotGuard] 陪伴模式开启: {self._current_mode_name}")

        behavior_prompt = self._config.get("llm_behavior_prompt", "")
        result = f"{self._current_mode_name}模式已开启，Bark推送已发送"
        if mode_config.get("description"):
            result += f"\n模式描述：{mode_config['description']}"
        if behavior_prompt:
            result += "\n\n" + behavior_prompt
        return result

    @llm_tool("stop_companion_mode")
    async def tool_stop_companion(self, event: AstrMessageEvent, custom_message: str = ""):
        """关闭当前陪伴监控模式。当用户表示起床了/学完了/下班了/运动结束了时调用此工具。

        Args:
            custom_message(string): 可选，关闭时通过Bark推送给用户的自定义消息
        """
        if not self._current_mode:
            return "当前没有开启任何陪伴模式"

        mode_name = self._current_mode_name or self._current_mode
        await self._cancel_all_reminders()
        await self._stop_encourage_timer()

        start_ts = self._mode_start_time.isoformat() if self._mode_start_time else ""
        records_during = [r for r in self._app_usage if r["time"] >= start_ts] if start_ts else []

        self._current_mode = None
        self._current_mode_name = None
        self._current_mode_config = None
        self._mode_start_time = None
        self._global_warning_level = 0
        self._last_violation_time = 0
        if self._cooldown_task and not self._cooldown_task.done():
            self._cooldown_task.cancel()

        if custom_message:
            await self._send_bark_push(self._config.get("bark_push_title", "\u2764\ufe0f"), custom_message)

        summary = f"{mode_name}模式已关闭"
        if records_during:
            app_counts = {}
            for r in records_during:
                app_counts[r["app_name"]] = app_counts.get(r["app_name"], 0) + 1
            summary += f"，监控期间App使用记录：{json.dumps(app_counts, ensure_ascii=False)}"

        # 通过QQ发送关闭统计
        await self._send_qq_warning(summary)
        await self._write_to_conversation_history(summary, f"[陪伴监控] {mode_name}模式已关闭")

        logger.info(f"[ScreenshotGuard] 陪伴模式关闭: {mode_name}")
        return summary

    @llm_tool("check_app_usage")
    async def tool_check_usage(self, event: AstrMessageEvent, count: int = 20):
        """查看用户最近的App使用记录。当想知道用户最近在用什么App时调用此工具。

        Args:
            count(int): 要查看的记录条数，默认20条
        """
        await self._start_http_server()
        if not self._app_usage:
            return "还没有收到过App使用记录"
        today = datetime.now().strftime("%Y-%m-%d")
        today_records = [r for r in self._app_usage if r["time"].startswith(today)]
        if not today_records:
            return "今天还没有App使用记录"
        recent = today_records[-count:]
        lines = []
        for r in recent:
            try:
                dt = datetime.fromisoformat(r["time"])
                time_str = dt.strftime("%H:%M:%S")
            except:
                time_str = r["time"]
            device_tag = f" [{r.get('device', '')}]" if r.get('device') and r.get('device') != 'iPhone' else ""
            lines.append(f"{time_str} {r['app_name']}{device_tag}")
        return f"今天共{len(today_records)}条记录，最近{len(recent)}条：\n" + "\n".join(lines)

    @llm_tool("send_bark_notification")
    async def tool_send_bark(self, event: AstrMessageEvent, message: str):
        """通过Bark向用户手机发送推送通知。当想主动给用户手机发消息时调用此工具。

        Args:
            message(string): 推送消息内容
        """
        success = await self._send_bark_push(self._config.get("bark_push_title", "\u2764\ufe0f"), message)
        return "推送发送成功" if success else "推送发送失败"

    @llm_tool("get_companion_status")
    async def tool_get_status(self, event: AstrMessageEvent):
        """获取当前陪伴监控模式的状态信息。"""
        await self._start_http_server()
        http_port = self._config.get("http_port", 2313)
        status = {
            "http_port": http_port,
            "current_mode": self._current_mode,
            "mode_name": self._current_mode_name,
            "mode_start_time": self._mode_start_time.isoformat() if self._mode_start_time else None,
            "warning_level": self._global_warning_level,
            "total_records": len(self._app_usage),
            "pending_reminders": list(self._pending_reminders.keys()),
            "bark_devices": [d["name"] for d in self._bark_devices],
            "builtin_modes": list(self._builtin_modes.keys()),
            "free_modes": list(self._free_modes.keys()),
        }
        today = datetime.now().strftime("%Y-%m-%d")
        status["today_records"] = len([r for r in self._app_usage if r["time"].startswith(today)])
        return json.dumps(status, ensure_ascii=False)

    # ========== 手动指令 ==========

    async def _manual_start_mode(self, event: AstrMessageEvent, mode: str):
        await self._start_http_server()
        await self._cancel_all_reminders()
        self._global_warning_level = 0
        self._last_violation_time = 0
        if self._cooldown_task and not self._cooldown_task.done():
            self._cooldown_task.cancel()

        mode_config = self._get_mode_config(mode)
        if not mode_config:
            yield event.plain_result(f"不支持的模式：{mode}")
            return

        self._current_mode = mode
        self._current_mode_name = mode_config["name"]
        self._current_mode_config = mode_config
        self._mode_start_time = datetime.now()

        push_msg = f"{self._current_mode_name}监控已开启"
        await self._send_bark_push(self._config.get("bark_push_title", "\u2764\ufe0f"), push_msg)
        await self._start_encourage_timer()

        yield event.plain_result(f"{self._current_mode_name}模式已开启，Bark推送已发送")

    @filter.command("睡眠陪伴", alias={"晚安监控", "睡眠监控", "sleep"})
    async def cmd_sleep_mode(self, event: AstrMessageEvent):
        async for result in self._manual_start_mode(event, "sleep"):
            yield result

    @filter.command("学习陪伴", alias={"学习监控", "study"})
    async def cmd_study_mode(self, event: AstrMessageEvent):
        async for result in self._manual_start_mode(event, "study"):
            yield result

    @filter.command("工作陪伴", alias={"工作监控", "work"})
    async def cmd_work_mode(self, event: AstrMessageEvent):
        async for result in self._manual_start_mode(event, "work"):
            yield result

    @filter.command("运动陪伴", alias={"运动监控", "exercise"})
    async def cmd_exercise_mode(self, event: AstrMessageEvent):
        async for result in self._manual_start_mode(event, "exercise"):
            yield result

    @filter.command("关闭陪伴", alias={"关闭监控", "停止监控", "stop"})
    async def cmd_stop_mode(self, event: AstrMessageEvent):
        if not self._current_mode:
            yield event.plain_result("当前没有开启任何陪伴模式")
            return
        mode_name = self._current_mode_name or self._current_mode
        await self._cancel_all_reminders()
        await self._stop_encourage_timer()
        self._current_mode = None
        self._current_mode_name = None
        self._current_mode_config = None
        self._mode_start_time = None
        self._global_warning_level = 0
        self._last_violation_time = 0
        if self._cooldown_task and not self._cooldown_task.done():
            self._cooldown_task.cancel()
        yield event.plain_result(f"{mode_name}模式已关闭")

    @filter.command("查看手机", alias={"截屏", "看看手机", "screenshot"})
    async def request_screenshot(self, event: AstrMessageEvent):
        await self._start_http_server()
        # 自动捕获 session_origin
        try:
            self._session_origin = event.unified_msg_origin
        except:
            pass
        # 直接从服务器取最近一张安卓截屏
        if not os.path.exists(SCREENSHOT_DIR):
            yield event.plain_result("还没有收到过截图")
            return
        files = sorted(os.listdir(SCREENSHOT_DIR), reverse=True)
        image_files = [f for f in files if f.endswith(('.jpg', '.jpeg', '.png'))]
        if not image_files:
            yield event.plain_result("还没有收到过截图")
            return
        latest = os.path.join(SCREENSHOT_DIR, image_files[0])
        yield event.image_result(latest)

    @filter.command("监控状态", alias={"查看监控"})
    async def monitor_status(self, event: AstrMessageEvent):
        await self._start_http_server()
        # 自动捕获 session_origin
        try:
            self._session_origin = event.unified_msg_origin
        except:
            pass
        http_port = self._config.get("http_port", 2313)
        lines = []
        lines.append(f"HTTP服务：端口 {http_port} 运行中")
        lines.append(f"Bark设备：{', '.join(d['name'] for d in self._bark_devices) if self._bark_devices else '未配置'}")
        if self._current_mode:
            lines.append(f"陪伴模式：{self._current_mode_name or self._current_mode}")
            if self._mode_start_time:
                lines.append(f"  开启时间：{self._mode_start_time.strftime('%H:%M:%S')}")
            lines.append(f"  警告等级：{self._global_warning_level}")
            if self._pending_reminders:
                lines.append(f"  待发提醒：{', '.join(self._pending_reminders.keys())}")
        else:
            lines.append("陪伴模式：关闭")
        lines.append(f"固定模式：{', '.join(self._builtin_modes.get(k, {}).get('name', k) for k in self._builtin_modes)}")
        if self._free_modes:
            lines.append(f"自由模式：{', '.join(self._free_modes.keys())}")
        lines.append(f"App使用记录：共 {len(self._app_usage)} 条")
        today = datetime.now().strftime("%Y-%m-%d")
        today_count = len([r for r in self._app_usage if r["time"].startswith(today)])
        lines.append(f"  今日记录：{today_count} 条")
        if os.path.exists(SCREENSHOT_DIR):
            screenshots = [f for f in os.listdir(SCREENSHOT_DIR) if f.endswith(('.jpg', '.jpeg', '.png'))]
            lines.append(f"历史截图：{len(screenshots)} 张")
        lines.append(f"提醒延迟：第二级 {self._config.get('reminder_delay_1', 5)}分钟 / 第三级 {self._config.get('reminder_delay_2', 10)}分钟")
        lines.append(f"冷却时间：{self._config.get('cooldown_minutes', 60)}分钟")
        lines.append(f"鼓励间隔：{self._config.get('encourage_interval', 30)}分钟")
        screenshot_provider = self._config.get("screenshot_analysis_provider", "")
        lines.append(f"截屏分析模型：{screenshot_provider if screenshot_provider else '未配置（使用查岗模型）'}")
        lines.append("")
        lines.append("━━━ 可用指令 ━━━")
        lines.append("/睡眠陪伴 - 开启睡眠监控")
        lines.append("/学习陪伴 - 开启学习监控")
        lines.append("/工作陪伴 - 开启工作监控")
        lines.append("/运动陪伴 - 开启运动监控")
        lines.append("/关闭陪伴 - 关闭当前监控")
        lines.append("/查看手机 - 请求截屏")
        lines.append("/查看使用记录 - 查看今日App记录")
        lines.append("/查看最新截图 - 查看最近一张截图")
        lines.append("/监控状态 - 查看当前状态")
        lines.append("/数据状态 - 查看数据文件大小")
        lines.append("/清理使用记录 - 清空App记录")
        lines.append("/清理截图 - 清空所有截图文件")
        lines.append("/设置提醒延迟 [分钟1] [分钟2]")
        yield event.plain_result("\n".join(lines))

    @filter.command("查看使用记录", alias={"app记录", "使用记录", "她在干嘛"})
    async def show_app_usage(self, event: AstrMessageEvent):
        await self._start_http_server()
        try:
            self._session_origin = event.unified_msg_origin
        except:
            pass
        if not self._app_usage:
            yield event.plain_result("还没有收到过App使用记录")
            return
        today = datetime.now().strftime("%Y-%m-%d")
        today_records = [r for r in self._app_usage if r["time"].startswith(today)]
        if not today_records:
            yield event.plain_result("今天还没有App使用记录")
            return
        lines = [f"今天的App使用记录（共{len(today_records)}条）：\n"]
        for r in today_records[-20:]:
            try:
                dt = datetime.fromisoformat(r["time"])
                time_str = dt.strftime("%H:%M:%S")
            except:
                time_str = r["time"]
            device_tag = f" [{r.get('device', '')}]" if r.get('device') and r.get('device') != 'iPhone' else ""
            lines.append(f"  {time_str}  {r['app_name']}{device_tag}")
        if len(today_records) > 20:
            lines.append(f"\n  ...还有 {len(today_records) - 20} 条更早的记录")
        yield event.plain_result("\n".join(lines))

    @filter.command("查看最新截图", alias={"最新截图", "上次截图"})
    async def show_latest_screenshot(self, event: AstrMessageEvent):
        if not os.path.exists(SCREENSHOT_DIR):
            yield event.plain_result("还没有收到过截图")
            return
        files = sorted(os.listdir(SCREENSHOT_DIR), reverse=True)
        image_files = [f for f in files if f.endswith(('.jpg', '.jpeg', '.png'))]
        if not image_files:
            yield event.plain_result("还没有收到过截图")
            return
        latest = os.path.join(SCREENSHOT_DIR, image_files[0])
        yield event.image_result(latest)

    @filter.command("设置提醒延迟", alias={"修改提醒时间"})
    async def set_reminder_delay(self, event: AstrMessageEvent, level2: int = 5, level3: int = 10):
        self._config["reminder_delay_1"] = level2
        self._config["reminder_delay_2"] = level3
        self._save_config()
        yield event.plain_result(f"提醒延迟已更新：第二级 {level2}分钟 / 第三级 {level3}分钟")

    @filter.command("清理使用记录", alias={"清理数据", "清空记录"})
    async def clear_app_usage(self, event: AstrMessageEvent, days: int = 0):
        if days <= 0:
            count = len(self._app_usage)
            self._app_usage = []
            self._save_app_usage()
            yield event.plain_result(f"已清理全部 {count} 条App使用记录")
        else:
            from datetime import timedelta
            cutoff = datetime.now() - timedelta(days=days)
            cutoff_str = cutoff.isoformat()
            old_count = len(self._app_usage)
            self._app_usage = [r for r in self._app_usage if r["time"] >= cutoff_str]
            removed = old_count - len(self._app_usage)
            self._save_app_usage()
            yield event.plain_result(f"已清理 {removed} 条记录，保留最近 {days} 天共 {len(self._app_usage)} 条")

    @filter.command("数据状态", alias={"数据大小"})
    async def data_status(self, event: AstrMessageEvent):
        lines = []
        if os.path.exists(APP_LOG_FILE):
            size = os.path.getsize(APP_LOG_FILE)
            max_size = self._config.get("max_data_size_mb", 5)
            lines.append(f"App使用记录：{len(self._app_usage)} 条，文件大小 {size / 1024:.1f}KB")
            lines.append(f"容量上限：{max_size}MB")
            if size > max_size * 1024 * 1024:
                lines.append("⚠️ 已超过容量上限，建议清理")
        else:
            lines.append("暂无数据文件")
        if os.path.exists(SCREENSHOT_DIR):
            screenshots = [f for f in os.listdir(SCREENSHOT_DIR) if f.endswith(('.jpg', '.jpeg', '.png'))]
            total_size = sum(os.path.getsize(os.path.join(SCREENSHOT_DIR, f)) for f in screenshots)
            lines.append(f"截图文件：{len(screenshots)} 张，共 {total_size / 1024 / 1024:.1f}MB")
        yield event.plain_result("\n".join(lines))

    @filter.command("清理截图", alias={"清空截图", "清理截屏", "清空截屏"})
    async def clear_screenshots(self, event: AstrMessageEvent):
        if not os.path.exists(SCREENSHOT_DIR):
            yield event.plain_result("暂无截图文件")
            return
        screenshots = [f for f in os.listdir(SCREENSHOT_DIR) if f.endswith(('.jpg', '.jpeg', '.png'))]
        if not screenshots:
            yield event.plain_result("暂无截图文件")
            return
        total_size = sum(os.path.getsize(os.path.join(SCREENSHOT_DIR, f)) for f in screenshots)
        for f in screenshots:
            os.remove(os.path.join(SCREENSHOT_DIR, f))
        yield event.plain_result(f"已清理 {len(screenshots)} 张截图，释放 {total_size / 1024 / 1024:.1f}MB")

    def _auto_cleanup_screenshots(self):
        """截图目录超过2MB时自动清理最早的截图"""
        if not os.path.exists(SCREENSHOT_DIR):
            return
        screenshots = [f for f in os.listdir(SCREENSHOT_DIR) if f.endswith(('.jpg', '.jpeg', '.png'))]
        if not screenshots:
            return
        total_size = sum(os.path.getsize(os.path.join(SCREENSHOT_DIR, f)) for f in screenshots)
        if total_size <= 2 * 1024 * 1024:
            return
        # 按修改时间排序，最早的在前
        screenshots.sort(key=lambda f: os.path.getmtime(os.path.join(SCREENSHOT_DIR, f)))
        removed = 0
        while total_size > 2 * 1024 * 1024 and screenshots:
            oldest = screenshots.pop(0)
            fpath = os.path.join(SCREENSHOT_DIR, oldest)
            fsize = os.path.getsize(fpath)
            os.remove(fpath)
            total_size -= fsize
            removed += 1
        if removed > 0:
            logger.info(f"[ScreenshotGuard] 自动清理了 {removed} 张旧截图，当前截图目录 {total_size / 1024 / 1024:.1f}MB")

    async def terminate(self):
        await self._cancel_all_reminders()
        await self._stop_encourage_timer()
        if self._cooldown_task and not self._cooldown_task.done():
            self._cooldown_task.cancel()
        if self._http_runner:
            await self._http_runner.cleanup()
            logger.info("[ScreenshotGuard] HTTP服务器已关闭")
