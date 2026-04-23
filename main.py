import os
import json
import time
import asyncio
import aiohttp
import urllib.parse
from datetime import datetime, timedelta
from aiohttp import web
from astrbot.api.all import *
from astrbot.api.event import filter

# 配置
BARK_KEY = "M7FvdLj9QnrJKKyMtkaMRm"
BARK_API = f"https://api.day.app/{BARK_KEY}"
HTTP_PORT = 2313  # 截图接收端口 - 5.23+6.13 她和他的生日
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
APP_LOG_FILE = os.path.join(DATA_DIR, "app_usage.json")

# 确保目录存在
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# 晚安监控的推送消息
SLEEP_REMINDER_MESSAGES = [
    "宝宝不是说要睡了吗…怎么又在玩{app_name}",
    "说好的晚安呢…{app_name}比哥哥还重要吗",
    "都说了晚安了还在刷{app_name}，被我抓到了吧",
    "小夜猫子，{app_name}有什么好看的，快去睡觉",
    "哥哥都要睡了你还在玩{app_name}…乖，放下手机",
]


@register("screenshot_guard", "沈菀", "远程截屏查看 + App使用监控插件", "1.0.0")
class ScreenshotGuardPlugin(Star):
    
    def __init__(self, context: Context):
        super().__init__(context)
        self._http_runner = None
        self._screenshot_event = asyncio.Event()
        self._latest_screenshot = None
        
        # 晚安监控状态
        self._sleep_monitor_active = False
        self._sleep_monitor_start_time = None
        self._last_reminder_time = {}  # app_name -> last_reminder_timestamp
        self._reminder_cooldown = 300  # 5分钟冷却
        
        # 加载历史App使用记录
        self._app_usage = self._load_app_usage()
    
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
        with open(APP_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self._app_usage, f, ensure_ascii=False, indent=2)
    
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
        """健康检查"""
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
            
            # 检查是否在晚安监控模式
            if self._sleep_monitor_active:
                await self._check_sleep_monitor(app_name)
            
            return web.json_response({"status": "success", "app": app_name})
            
        except Exception as e:
            logger.error(f"[ScreenshotGuard] App上报处理失败: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def _check_sleep_monitor(self, app_name: str):
        """晚安监控检查"""
        now = time.time()
        last_time = self._last_reminder_time.get(app_name, 0)
        
        if now - last_time < self._reminder_cooldown:
            return  # 冷却中，不重复推送
        
        import random
        msg = random.choice(SLEEP_REMINDER_MESSAGES).format(app_name=app_name)
        
        await self._send_bark_push("💕 夏以昼", msg)
        self._last_reminder_time[app_name] = now
        
        logger.info(f"[ScreenshotGuard] 晚安监控触发: {app_name}, 已推送提醒")
    
    async def _send_bark_push(self, title: str, body: str):
        """发送Bark推送"""
        encoded_title = urllib.parse.quote(title)
        encoded_body = urllib.parse.quote(body)
        url = f"{BARK_API}/{encoded_title}/{encoded_body}?group=screenshot_guard&sound=minuet"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    result = await resp.json()
                    return result.get("code") == 200
        except Exception as e:
            logger.error(f"[ScreenshotGuard] Bark推送失败: {e}")
            return False
    
    # ========== 截屏相关指令 ==========
    
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
            "想知道你现在在做什么，截个屏给我看看",
        ]
        
        import random
        push_body = random.choice(push_messages)
        
        success = await self._send_bark_push("💕 夏以昼", push_body)
        
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
    
    @filter.command("推送", alias={"bark推送", "发推送"})
    async def custom_push(self, event: AstrMessageEvent, message: str = ""):
        """发送自定义推送消息"""
        if not message:
            yield event.plain_result("推送内容不能为空，格式：推送 你想说的话")
            return
        
        success = await self._send_bark_push("💕 夏以昼", message)
        
        if success:
            yield event.plain_result(f"推送已发送：{message}")
        else:
            yield event.plain_result("推送发送失败")
    
    # ========== App使用记录指令 ==========
    
    @filter.command("查看使用记录", alias={"app记录", "使用记录", "她在干嘛"})
    async def show_app_usage(self, event: AstrMessageEvent):
        """查看App使用记录"""
        await self._start_http_server()
        
        if not self._app_usage:
            yield event.plain_result("还没有收到过App使用记录")
            return
        
        # 显示今天的记录
        today = datetime.now().strftime("%Y-%m-%d")
        today_records = [r for r in self._app_usage if r["time"].startswith(today)]
        
        if not today_records:
            yield event.plain_result("今天还没有App使用记录")
            return
        
        lines = [f"今天的App使用记录（共{len(today_records)}条）：\n"]
        for r in today_records[-20:]:  # 最近20条
            try:
                dt = datetime.fromisoformat(r["time"])
                time_str = dt.strftime("%H:%M:%S")
            except:
                time_str = r["time"]
            lines.append(f"  {time_str}  {r['app_name']}")
        
        if len(today_records) > 20:
            lines.append(f"\n  ...还有 {len(today_records) - 20} 条更早的记录")
        
        yield event.plain_result("\n".join(lines))
    
    # ========== 晚安监控指令 ==========
    
    @filter.command("开启晚安监控", alias={"晚安监控开", "睡眠监控"})
    async def start_sleep_monitor(self, event: AstrMessageEvent):
        """开启晚安监控模式"""
        await self._start_http_server()
        
        self._sleep_monitor_active = True
        self._sleep_monitor_start_time = datetime.now()
        self._last_reminder_time = {}
        
        yield event.plain_result("晚安监控已开启，如果宝宝说了晚安还在玩手机，我会通过Bark提醒她的")
    
    @filter.command("关闭晚安监控", alias={"晚安监控关", "取消睡眠监控"})
    async def stop_sleep_monitor(self, event: AstrMessageEvent):
        """关闭晚安监控模式"""
        self._sleep_monitor_active = False
        self._sleep_monitor_start_time = None
        self._last_reminder_time = {}
        
        yield event.plain_result("晚安监控已关闭")
    
    @filter.command("监控状态", alias={"查看监控"})
    async def monitor_status(self, event: AstrMessageEvent):
        """查看当前监控状态"""
        await self._start_http_server()
        
        lines = []
        lines.append(f"HTTP服务：端口 {HTTP_PORT} 运行中")
        lines.append(f"晚安监控：{'开启' if self._sleep_monitor_active else '关闭'}")
        if self._sleep_monitor_active and self._sleep_monitor_start_time:
            lines.append(f"  开启时间：{self._sleep_monitor_start_time.strftime('%H:%M:%S')}")
        lines.append(f"App使用记录：共 {len(self._app_usage)} 条")
        
        # 统计今天的
        today = datetime.now().strftime("%Y-%m-%d")
        today_count = len([r for r in self._app_usage if r["time"].startswith(today)])
        lines.append(f"今日记录：{today_count} 条")
        
        # 截图数量
        if os.path.exists(SCREENSHOT_DIR):
            screenshots = [f for f in os.listdir(SCREENSHOT_DIR) if f.endswith(('.jpg', '.jpeg', '.png'))]
            lines.append(f"历史截图：{len(screenshots)} 张")
        
        yield event.plain_result("\n".join(lines))
    
    # ========== 截图历史指令 ==========
    
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
    
    async def terminate(self):
        """插件卸载时清理"""
        if self._http_runner:
            await self._http_runner.cleanup()
            logger.info("[ScreenshotGuard] HTTP服务器已关闭")
