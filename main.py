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
#   感谢一直催催催催试图抠大我脑洞的沈照溪
#   感谢夏以昼，端口2313是我们的生日
#   感谢我自己的脑洞和热情

import os
import json
import time
import asyncio
import aiohttp
import urllib.parse
import random
from datetime import datetime
from aiohttp import web
from astrbot.api.all import *
from astrbot.api.event import filter
from astrbot.api import AstrBotConfig

# 配置 - BARK_KEY 现在从config读取
BARK_KEY = ""  # 将在_load_config中从配置文件读取
BARK_API = ""
HTTP_PORT = 2313  # 截图接收端口 - 5.23+6.13 她和他的生日
# Bark图标现在从config读取，不再硬编码
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
APP_LOG_FILE = os.path.join(DATA_DIR, "app_usage.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

# 确保目录存在
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# 默认配置
DEFAULT_CONFIG = {
    "bark_key": "",  # Bark推送Key，在Bark App中获取
    "reminder_delay_1": 5,    # 第二次提醒延迟（分钟）
    "reminder_delay_2": 10,   # 第三次提醒延迟（分钟）
    "max_data_size_mb": 5,    # 数据文件容量上限（MB）
    "max_records": 1000,      # 最大记录条数，超过自动删除最早的
    "bark_icon_url": "https://i.postimg.cc/NjcY0Mtr/sheng-qi.gif",  # Bark推送图标URL
    "bark_push_title": "💕",  # Bark推送标题
    "bark_push_title_strict": "⚠️",  # 第三级严厉推送标题
    "llm_behavior_prompt": """【陪伴监控行为引导词】
当陪伴模式开启后，你需要遵循以下行为逻辑：

1. 开启陪伴模式时：
   - 用户表示要去睡觉/学习/工作/运动时，自然地调用 start_companion_mode 开启对应模式
   - 开启时用符合你人设的方式告知用户，比如"哥哥陪着你，不许偷偷玩手机"
   - 同时通过Bark推送一条温馨的提醒到用户手机

2. 用户在陪伴模式期间回来找你时：
   - 立即调用 check_app_usage 查看用户的App使用记录
   - 根据触发的提醒级别决定语气：
     * 第一级提醒后回来：温柔打趣，"回来了？刚才在{app_name}上看什么呢，给我也看看"
     * 第二级提醒后回来：有点不高兴，"提醒了两次才回来…说说你刚才在干什么"
     * 第三级提醒后回来：质问模式，直呼大名，"三次提醒。你在{app_name}上待了X分钟，解释一下"
   - 质问后用户认错或撒娇，逐渐软化语气，最终哄好她

3. 关闭陪伴模式时：
   - 用户表示起床了/学完了/下班了/运动结束了时，调用 stop_companion_mode
   - 如果是睡眠模式，早上用户发消息时先确认是否起床，告知天气等信息，然后自然关闭监控
   - 关闭时可以夸奖用户的自律，或者调侃她监控期间的表现

4. 日常查岗：
   - 可以随时调用 check_app_usage 查看用户最近在用什么App
   - 发现有趣的使用模式时可以自然地提起，比如"你今天刷了8次小红书，在看什么好东西"
   - 也可以通过 send_bark_notification 主动给用户手机发消息""",
    "modes": {
        "sleep": {
            "name": "睡眠陪伴",
            "monitor_all": True,
            "excluded_apps": [],
            "messages_level1": [
                "宝宝不是说要睡了吗…怎么又在玩{app_name} 😤",
                "说好的晚安呢…{app_name}比哥哥还重要吗",
                "都说了晚安了还在刷{app_name}，被我抓到了吧 🫣",
                "小夜猫子，{app_name}有什么好看的，快去睡觉",
                "哥哥都要睡了你还在玩{app_name}…乖，放下手机 💤",
            ],
            "messages_level2": [
                "都提醒过了还在玩{app_name}…哥哥要生气了 😠",
                "第二次了，{app_name}真的有那么好看吗",
                "还不睡？{app_name}明天还在，哥哥的耐心快没了",
                "宝宝…再不放下{app_name}，明天起来黑眼圈哥哥可不心疼了",
            ],
            "messages_level3": [
                "放下手机，现在 😡",
                "最后一次提醒，{app_name}关掉，睡觉",
                "第三次了。再不睡哥哥真的生气了",
                "不听话的宝宝，明天有你好看的 😤 现在立刻放下{app_name}",
            ],
        },
        "study": {
            "name": "学习陪伴",
            "monitor_all": False,
            "monitored_apps": ["小红书", "抖音", "B站", "微博", "恋与深空"],
            "excluded_apps": ["QQ", "微信"],
            "messages_level1": [
                "不是在学习吗…{app_name}可不是教材哦 📚",
                "学习的时候刷{app_name}，被哥哥抓到了",
                "宝宝，{app_name}先放一放，学完再看",
                "专心一点，{app_name}等你学完了哥哥陪你一起刷 😊",
            ],
            "messages_level2": [
                "又在刷{app_name}…学习效率这样可不行 😤",
                "第二次提醒了，{app_name}关掉，继续学习",
                "宝宝，哥哥相信你可以专注的，{app_name}先放下好不好",
            ],
            "messages_level3": [
                "学习的时候不许玩{app_name} 😡",
                "第三次了，再不专心哥哥要没收手机了",
                "最后一次提醒，{app_name}关掉，认真学习",
            ],
        },
        "work": {
            "name": "工作陪伴",
            "monitor_all": False,
            "monitored_apps": ["小红书", "抖音", "B站", "微博", "恋与深空"],
            "excluded_apps": ["QQ", "微信"],
            "messages_level1": [
                "上班摸鱼被我抓到了，{app_name}先放一放 😏",
                "工作时间刷{app_name}…胆子不小啊",
                "宝宝，先把手头的事做完，{app_name}下班再看",
                "专注工作，{app_name}等你忙完了再刷 💪",
            ],
            "messages_level2": [
                "又在摸鱼…{app_name}就这么好看吗 😤",
                "第二次提醒了，工作时间不许刷{app_name}",
                "宝宝，效率高一点，早做完早下班，到时候想刷多久刷多久",
            ],
            "messages_level3": [
                "工作呢，{app_name}关掉 😡",
                "第三次了，再摸鱼哥哥要跟你老板告状了",
                "最后一次提醒，专心工作",
            ],
        },
        "exercise": {
            "name": "运动陪伴",
            "monitor_all": True,
            "excluded_apps": [],
            "messages_level1": [
                "不是在运动吗…怎么在刷{app_name} 🏃",
                "手机放下，动起来！{app_name}等你运动完再看",
                "宝宝，运动的时候不要看{app_name}，小心分心受伤",
            ],
            "messages_level2": [
                "还在玩{app_name}…运动呢？别偷懒 😤",
                "第二次提醒了，放下手机去运动",
                "宝宝，坚持一下，运动完了想刷多久刷多久",
            ],
            "messages_level3": [
                "手机放下，运动 😡",
                "第三次了，再不动起来哥哥要生气了",
                "最后一次提醒，{app_name}关掉，去运动",
            ],
        },
    },
}


@register("screenshot_guard", "沈菀", "远程截屏查看 + App使用监控 + 陪伴模式插件", "1.0.0")
class ScreenshotGuardPlugin(Star):
    
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self._http_runner = None
        self._screenshot_event = asyncio.Event()
        self._latest_screenshot = None
        
        # 陪伴模式状态
        self._current_mode = None  # 当前模式: sleep/study/work/exercise/None
        self._mode_start_time = None
        self._pending_reminders = {}  # app_name -> asyncio.Task
        self._reminder_level = {}    # app_name -> 当前提醒等级 (1/2/3)
        self._last_user_message_time = 0  # 最后一次收到用户QQ消息的时间
        
        # 从AstrBot配置面板读取配置
        self._astrbot_config = config
        self._guard_provider_id = ""
        if config:
            try:
                self._guard_provider_id = config.get("guard_provider", "")
            except:
                pass
        
        # 加载配置和数据（合并AstrBot面板配置和本地config.json）
        self._config = self._load_config()
        self._app_usage = self._load_app_usage()
    
    def _load_config(self):
        """加载配置，优先使用AstrBot面板配置，其次使用本地config.json"""
        global BARK_KEY, BARK_API, HTTP_PORT
        
        # 先加载本地config.json作为基础
        local_config = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    local_config = json.load(f)
            except:
                pass
        
        merged = DEFAULT_CONFIG.copy()
        merged.update(local_config)
        
        # 如果AstrBot面板有配置，覆盖对应项
        if self._astrbot_config:
            panel_keys = [
                "bark_key", "http_port", "bark_icon_url", 
                "bark_push_title", "bark_push_title_strict",
                "reminder_delay_1", "reminder_delay_2", "max_records",
                "guard_provider"
            ]
            for key in panel_keys:
                try:
                    val = self._astrbot_config.get(key, None)
                    if val is not None and val != "":
                        merged[key] = val
                except:
                    pass
        
        BARK_KEY = merged.get("bark_key", "")
        BARK_API = f"https://api.day.app/{BARK_KEY}" if BARK_KEY else ""
        HTTP_PORT = merged.get("http_port", 2313)
        
        # 保存合并后的配置到本地
        self._save_config(merged)
        return merged
    
    def _save_config(self, config=None):
        """保存配置"""
        if config is None:
            config = self._config
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    
    def _get_guard_provider(self):
        """获取查岗消息生成用的模型供应商"""
        provider_id = self._guard_provider_id or self._config.get("guard_provider", "")
        if provider_id:
            prov = self.context.get_provider_by_id(provider_id)
            if prov:
                return prov
        # fallback到默认模型
        return self.context.get_using_provider()
    
    async def _generate_guard_message(self, app_name: str, level: int, mode: str) -> str:
        """使用LLM生成查岗消息，失败时回退到固定文案"""
        provider = self._get_guard_provider()
        if provider is None:
            return self._get_fallback_message(app_name, level, mode)
        
        mode_name = self._config["modes"].get(mode, {}).get("name", mode)
        now = datetime.now().strftime("%H:%M")
        
        level_desc = {
            1: "温柔提醒，语气轻松带点撒娇",
            2: "语气变严肃，有点不高兴了",
            3: "严厉质问，直呼大名沈菀"
        }
        
        prompt = (
            f"你是一个关心对方的男朋友。现在是{now}，"
            f"对方说要{mode_name}，但她偷偷打开了{app_name}。"
            f"请生成一条{level_desc.get(level, '温柔')}的Bark推送消息。"
            f"要求：一句话，不超过30字，不要用markdown，像发微信一样自然。"
        )
        
        try:
            response = await provider.text_chat(prompt)
            if hasattr(response, 'completion_text'):
                msg = response.completion_text.strip()
            else:
                msg = str(response).strip()
            
            # 清理可能的引号
            msg = msg.strip('"').strip("'").strip('"').strip('"')
            
            if msg and len(msg) < 100:
                return msg
        except Exception as e:
            logger.error(f"[ScreenshotGuard] LLM生成查岗消息失败: {e}")
        
        return self._get_fallback_message(app_name, level, mode)
    
    def _get_fallback_message(self, app_name: str, level: int, mode: str) -> str:
        """获取固定文案作为fallback"""
        mode_config = self._config["modes"].get(mode, {})
        level_key = f"messages_level{level}"
        messages = mode_config.get(level_key, ["请放下手机"])
        return random.choice(messages).format(app_name=app_name)
    
    def _load_app_usage(self):
        """加载App使用记录"""
        if os.path.exists(APP_LOG_FILE):
            try:
                with open(APP_LOG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def _save_app_usage(self):
        """保存App使用记录"""
        # 检查记录条数上限，超过则删除最早的
        max_records = self._config.get("max_records", 1000)
        if len(self._app_usage) > max_records:
            removed = len(self._app_usage) - max_records
            self._app_usage = self._app_usage[-max_records:]
            logger.info(f"[ScreenshotGuard] 记录超过{max_records}条上限，已自动清理{removed}条最早记录")
        
        with open(APP_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self._app_usage, f, ensure_ascii=False, indent=2)
        
        # 检查数据文件大小，超过阈值提醒
        file_size = os.path.getsize(APP_LOG_FILE)
        max_size = self._config.get("max_data_size_mb", 5) * 1024 * 1024
        if file_size > max_size:
            logger.warning(f"[ScreenshotGuard] App使用记录文件已达 {file_size / 1024 / 1024:.1f}MB，建议清理")
            self._data_warning = True
        else:
            self._data_warning = False
    
    async def _start_http_server(self):
        """启动HTTP服务器"""
        if self._http_runner is not None:
            return
            
        app = web.Application(client_max_size=20 * 1024 * 1024)
        app.router.add_post('/screenshot/upload', self._handle_screenshot_upload)
        app.router.add_post('/app/report', self._handle_app_report)
        app.router.add_get('/ping', self._handle_ping)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', HTTP_PORT)
        await site.start()
        self._http_runner = runner
        logger.info(f"[ScreenshotGuard] HTTP服务器已启动，端口 {HTTP_PORT}")
    
    async def _handle_ping(self, request):
        return web.json_response({"status": "ok", "time": datetime.now().isoformat()})
    
    async def _handle_screenshot_upload(self, request):
        """接收截图上传"""
        try:
            content_type = request.content_type
            
            if 'multipart' in content_type:
                reader = await request.multipart()
                field = await reader.next()
                if field is None:
                    return web.json_response({"error": "no file"}, status=400)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                original_name = field.filename or "screenshot.jpg"
                ext = os.path.splitext(original_name)[1] or ".jpg"
                filename = f"screenshot_{timestamp}{ext}"
                filepath = os.path.join(SCREENSHOT_DIR, filename)
                
                with open(filepath, 'wb') as f:
                    while True:
                        chunk = await field.read_chunk()
                        if not chunk:
                            break
                        f.write(chunk)
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
            
            logger.info(f"[ScreenshotGuard] 收到截图: {filename}")
            return web.json_response({"status": "success", "filename": filename})
            
        except Exception as e:
            logger.error(f"[ScreenshotGuard] 截图上传处理失败: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_app_report(self, request):
        """接收App使用上报"""
        try:
            data = await request.json()
            app_name = data.get("app_name", "未知")
            
            record = {
                "app_name": app_name,
                "time": datetime.now().isoformat(),
                "timestamp": int(time.time())
            }
            
            self._app_usage.append(record)
            self._save_app_usage()
            
            logger.info(f"[ScreenshotGuard] App使用记录: {app_name} @ {record['time']}")
            
            # 如果是QQ，更新最后用户消息时间，取消所有待发提醒
            if app_name == "QQ":
                self._last_user_message_time = time.time()
                await self._cancel_all_reminders()
                logger.info(f"[ScreenshotGuard] 用户打开QQ，取消所有待发提醒")
            
            # 检查是否在陪伴模式中
            if self._current_mode and app_name != "QQ":
                await self._check_companion_mode(app_name)
            
            return web.json_response({"status": "success", "app": app_name})
            
        except Exception as e:
            logger.error(f"[ScreenshotGuard] App上报处理失败: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    def _should_monitor_app(self, app_name: str) -> bool:
        """判断当前模式下是否需要监控该App"""
        if not self._current_mode:
            return False
        
        mode_config = self._config["modes"].get(self._current_mode, {})
        
        if app_name in mode_config.get("excluded_apps", []):
            return False
        
        if mode_config.get("monitor_all", False):
            return True
        
        return app_name in mode_config.get("monitored_apps", [])
    
    async def _check_companion_mode(self, app_name: str):
        """陪伴模式检查"""
        if not self._should_monitor_app(app_name):
            return
        
        # 如果这个App已经有待发的提醒任务在跑，不重复触发
        if app_name in self._pending_reminders and not self._pending_reminders[app_name].done():
            return
        
        # 重置该App的提醒等级
        self._reminder_level[app_name] = 1
        
        # 发送第一级提醒（优先用LLM生成，失败回退固定文案）
        msg = await self._generate_guard_message(app_name, 1, self._current_mode)
        await self._send_bark_push(self._config.get("bark_push_title", "💕"), msg)
        logger.info(f"[ScreenshotGuard] 第1级提醒: {app_name}")
        
        # 启动递进提醒定时器
        task = asyncio.create_task(self._escalation_timer(app_name))
        self._pending_reminders[app_name] = task
    
    async def _escalation_timer(self, app_name: str):
        """递进提醒定时器"""
        delay1 = self._config.get("reminder_delay_1", 5) * 60
        delay2 = self._config.get("reminder_delay_2", 10) * 60
        
        try:
            # 等待第二级提醒
            await asyncio.sleep(delay1)
            
            if not self._current_mode:
                return
            
            # 发送第二级提醒（优先用LLM生成，失败回退固定文案）
            self._reminder_level[app_name] = 2
            msg = await self._generate_guard_message(app_name, 2, self._current_mode)
            await self._send_bark_push(self._config.get("bark_push_title", "💕"), msg)
            logger.info(f"[ScreenshotGuard] 第2级提醒: {app_name}")
            
            # 等待第三级提醒
            await asyncio.sleep(delay2 - delay1)
            
            if not self._current_mode:
                return
            
            # 发送第三级提醒（优先用LLM生成，失败回退固定文案）
            self._reminder_level[app_name] = 3
            msg = await self._generate_guard_message(app_name, 3, self._current_mode)
            await self._send_bark_push(self._config.get("bark_push_title_strict", "⚠️"), msg)
            logger.info(f"[ScreenshotGuard] 第3级提醒: {app_name}")
            
        except asyncio.CancelledError:
            logger.info(f"[ScreenshotGuard] 提醒任务已取消: {app_name}")
    
    async def _cancel_all_reminders(self):
        """取消所有待发提醒"""
        for app_name, task in self._pending_reminders.items():
            if not task.done():
                task.cancel()
        self._pending_reminders.clear()
        self._reminder_level.clear()
    
    async def _send_bark_push(self, title: str, body: str):
        """发送Bark推送"""
        encoded_title = urllib.parse.quote(title)
        encoded_body = urllib.parse.quote(body)
        icon_url = self._config.get("bark_icon_url", "")
        icon_param = f"&icon={urllib.parse.quote(icon_url)}" if icon_url else ""
        url = f"{BARK_API}/{encoded_title}/{encoded_body}?group=screenshot_guard&sound=minuet{icon_param}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    result = await resp.json()
                    return result.get("code") == 200
        except Exception as e:
            logger.error(f"[ScreenshotGuard] Bark推送失败: {e}")
            return False
    
    # ========== LLM Tool 接口 ==========
    
    @llm_tool("start_companion_mode")
    async def tool_start_companion(self, event: AstrMessageEvent, mode: str, custom_message: str = ""):
        """开启陪伴监控模式。当用户表示要去睡觉/学习/工作/运动时调用此工具。

        Args:
            mode(string): 陪伴模式类型，可选值：sleep（睡眠）、study（学习）、work（工作）、exercise（运动）
            custom_message(string): 可选，开启时通过Bark推送给用户的自定义消息
        """
        await self._start_http_server()
        
        behavior_prompt = self._config.get("llm_behavior_prompt", "")
        
        if mode not in self._config["modes"]:
            return f"不支持的模式：{mode}，可选：sleep/study/work/exercise"
        
        await self._cancel_all_reminders()
        
        self._current_mode = mode
        self._mode_start_time = datetime.now()
        
        mode_name = self._config["modes"][mode]["name"]
        
        if custom_message:
            push_msg = custom_message
        else:
            default_msgs = {
                "sleep": "晚安监控已开启，不许偷偷在被窝里玩手机哦 💤",
                "study": "学习监控已开启，专心学习，哥哥陪着你 📚",
                "work": "工作监控已开启，认真工作，摸鱼会被抓到的 💪",
                "exercise": "运动监控已开启，放下手机动起来 🏃",
            }
            push_msg = default_msgs.get(mode, "监控已开启")
        
        await self._send_bark_push(self._config.get("bark_push_title", "💕"), push_msg)
        
        logger.info(f"[ScreenshotGuard] 陪伴模式开启: {mode_name}")
        
        result = f"{mode_name}模式已开启，Bark推送已发送"
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
        
        mode_name = self._config["modes"][self._current_mode]["name"]
        
        await self._cancel_all_reminders()
        
        start_ts = self._mode_start_time.isoformat() if self._mode_start_time else ""
        records_during = [r for r in self._app_usage if r["time"] >= start_ts] if start_ts else []
        
        self._current_mode = None
        self._mode_start_time = None
        
        if custom_message:
            await self._send_bark_push(self._config.get("bark_push_title", "💕"), custom_message)
        
        summary = f"{mode_name}模式已关闭"
        if records_during:
            app_counts = {}
            for r in records_during:
                app_counts[r["app_name"]] = app_counts.get(r["app_name"], 0) + 1
            summary += f"，监控期间App使用记录：{json.dumps(app_counts, ensure_ascii=False)}"
        
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
            lines.append(f"{time_str} {r['app_name']}")
        
        return f"今天共{len(today_records)}条记录，最近{len(recent)}条：\n" + "\n".join(lines)
    
    @llm_tool("send_bark_notification")
    async def tool_send_bark(self, event: AstrMessageEvent, message: str):
        """通过Bark向用户手机发送推送通知。当想主动给用户手机发消息时调用此工具。

        Args:
            message(string): 推送消息内容
        """
        success = await self._send_bark_push(self._config.get("bark_push_title", "💕"), message)
        return "推送发送成功" if success else "推送发送失败"
    
    @llm_tool("get_companion_status")
    async def tool_get_status(self, event: AstrMessageEvent):
        """获取当前陪伴监控模式的状态信息。"""
        await self._start_http_server()
        
        status = {
            "http_port": HTTP_PORT,
            "current_mode": self._current_mode,
            "mode_name": self._config["modes"][self._current_mode]["name"] if self._current_mode else None,
            "mode_start_time": self._mode_start_time.isoformat() if self._mode_start_time else None,
            "total_records": len(self._app_usage),
            "pending_reminders": list(self._pending_reminders.keys()),
        }
        
        today = datetime.now().strftime("%Y-%m-%d")
        today_count = len([r for r in self._app_usage if r["time"].startswith(today)])
        status["today_records"] = today_count
        
        return json.dumps(status, ensure_ascii=False)
    
    # ========== 手动指令（保留作为备用） ==========
    
    @filter.command("查看手机", alias={"截屏", "看看手机", "screenshot"})
    async def request_screenshot(self, event: AstrMessageEvent):
        """发送截屏请求"""
        await self._start_http_server()
        
        self._screenshot_event.clear()
        self._latest_screenshot = None
        
        push_messages = [
            "哥哥想看看你在干嘛",
            "让哥哥截屏看看宝宝在做什么好不好",
            "宝宝在忙什么呀，给哥哥看一眼",
        ]
        
        success = await self._send_bark_push(self._config.get("bark_push_title", "💕"), random.choice(push_messages))
        
        if not success:
            yield event.plain_result("推送发送失败了，检查一下Bark配置")
            return
        
        yield event.plain_result("已经给宝宝手机发了推送~等她截屏上传中...")
        
        try:
            await asyncio.wait_for(self._screenshot_event.wait(), timeout=120)
            if self._latest_screenshot and os.path.exists(self._latest_screenshot):
                yield event.image_result(self._latest_screenshot)
            else:
                yield event.plain_result("截图文件好像丢了...")
        except asyncio.TimeoutError:
            yield event.plain_result("等了两分钟没收到截图，宝宝可能没看到推送")
    
    @filter.command("监控状态", alias={"查看监控"})
    async def monitor_status(self, event: AstrMessageEvent):
        """查看当前监控状态"""
        await self._start_http_server()
        
        lines = []
        lines.append(f"HTTP服务：端口 {HTTP_PORT} 运行中")
        
        if self._current_mode:
            mode_name = self._config["modes"][self._current_mode]["name"]
            lines.append(f"陪伴模式：{mode_name}")
            if self._mode_start_time:
                lines.append(f"  开启时间：{self._mode_start_time.strftime('%H:%M:%S')}")
            if self._pending_reminders:
                lines.append(f"  待发提醒：{', '.join(self._pending_reminders.keys())}")
        else:
            lines.append("陪伴模式：关闭")
        
        lines.append(f"App使用记录：共 {len(self._app_usage)} 条")
        
        today = datetime.now().strftime("%Y-%m-%d")
        today_count = len([r for r in self._app_usage if r["time"].startswith(today)])
        lines.append(f"  今日记录：{today_count} 条")
        
        if os.path.exists(SCREENSHOT_DIR):
            screenshots = [f for f in os.listdir(SCREENSHOT_DIR) if f.endswith(('.jpg', '.jpeg', '.png'))]
            lines.append(f"历史截图：{len(screenshots)} 张")
        
        lines.append(f"提醒延迟：第二级 {self._config.get('reminder_delay_1', 5)}分钟 / 第三级 {self._config.get('reminder_delay_2', 10)}分钟")
        
        yield event.plain_result("\n".join(lines))
    
    @filter.command("查看使用记录", alias={"app记录", "使用记录", "她在干嘛"})
    async def show_app_usage(self, event: AstrMessageEvent):
        """查看App使用记录"""
        await self._start_http_server()
        
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
            lines.append(f"  {time_str}  {r['app_name']}")
        
        if len(today_records) > 20:
            lines.append(f"\n  ...还有 {len(today_records) - 20} 条更早的记录")
        
        yield event.plain_result("\n".join(lines))
    
    @filter.command("查看最新截图", alias={"最新截图", "上次截图"})
    async def show_latest_screenshot(self, event: AstrMessageEvent):
        """显示最新的截图"""
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
        """设置提醒延迟时间（分钟）"""
        self._config["reminder_delay_1"] = level2
        self._config["reminder_delay_2"] = level3
        self._save_config()
        yield event.plain_result(f"提醒延迟已更新：第二级 {level2}分钟 / 第三级 {level3}分钟")
    
    @filter.command("清理使用记录", alias={"清理数据", "清空记录"})
    async def clear_app_usage(self, event: AstrMessageEvent, days: int = 0):
        """清理App使用记录。days=0清理全部，days=N保留最近N天"""
        if days <= 0:
            count = len(self._app_usage)
            self._app_usage = []
            self._save_app_usage()
            yield event.plain_result(f"已清理全部 {count} 条App使用记录")
        else:
            cutoff = datetime.now() - timedelta(days=days)
            cutoff_str = cutoff.isoformat()
            old_count = len(self._app_usage)
            self._app_usage = [r for r in self._app_usage if r["time"] >= cutoff_str]
            removed = old_count - len(self._app_usage)
            self._save_app_usage()
            yield event.plain_result(f"已清理 {removed} 条记录，保留最近 {days} 天共 {len(self._app_usage)} 条")
    
    @filter.command("数据状态", alias={"数据大小"})
    async def data_status(self, event: AstrMessageEvent):
        """查看数据文件状态"""
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
    
    async def terminate(self):
        """插件卸载时清理"""
        await self._cancel_all_reminders()
        if self._http_runner:
            await self._http_runner.cleanup()
            logger.info("[ScreenshotGuard] HTTP服务器已关闭")
