import datetime
from nonebot.plugin import on_regex
from nonebot.params import ArgPlainText, Arg
from nonebot.adapters.onebot.v11 import (
    Bot,
    MessageEvent,
    Message,
)
from nonebot.params import Matcher, RegexGroup
from nonebot.log import logger
from nonebot.permission import SUPERUSER
from nonebot import require, get_driver, get_bot
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from datetime import date
import asyncio
import aiofiles
from .config import Config
from functools import partial
from chinese_calendar import is_workday
try:
    import ujson as json
except ImportError:
    import json


__help_plugin_name__ = "定时提醒"
__help_version__ = "1.0"
__usage__ = """
定时提醒 [date]→ 设置定时提醒，date为时间，格式为HH:MM，如 23:59， 不设置默认为17点
定时提醒 列表 → 列出所有定时提醒
定时提醒 清空 → 清空所有定时提醒
删除/开启/关闭定时提醒 [id] → 删除指定id的定时提醒
""".strip()


env_config = Config(**get_driver().config.dict())

config_path = Path("config/remain_plugin.json")
config_path.parent.mkdir(parents=True, exist_ok=True)
if config_path.exists():
    with open(config_path, "r", encoding="utf8") as f:
        CONFIG: Dict[str, List] = json.load(f)
else:
    CONFIG: Dict[str, List] = {"opened_tasks": []}
    with open(config_path, "w", encoding="utf8") as f:
        json.dump(CONFIG, f, ensure_ascii=False, indent=4)

try:
    scheduler = require("nonebot_plugin_apscheduler").scheduler
except Exception:
    scheduler = None

logger.opt(colors=True).info(
    "已检测到软依赖<y>nonebot_plugin_apscheduler</y>, <g>开启定时任务功能</g>"
    if scheduler
    else "未检测到软依赖<y>nonebot_plugin_apscheduler</y>，<r>禁用定时任务功能</r>"
)

everyday_en_matcher = on_regex(r"^定时提醒[\s]*(\d{2}:\d{2})?$", priority=999)
list_matcher = on_regex(r"^定时提醒[\s]*列表", priority=999)
clear_matcher = on_regex(r"^定时提醒[\s]*清空", priority=999)
turn_matcher = on_regex(r"^(开启|关闭|删除)定时提醒 ([0-9]+)$", priority=999, permission=SUPERUSER)

lock = asyncio.Lock()

no_ffmpeg_error = (
    "发送语音失败，可能是风控或未安装FFmpeg，详见 "
    "https://github.com/MelodyYuuka/nonebot_plugin_everyday_en#q-%E4%B8%BA%E4%BB%80%E4%B9%88%E6%B2%A1%E6%9C%89%E8%AF%AD%E9%9F%B3"
)

@everyday_en_matcher.got("repeat", prompt="选择执行间隔:\n1.每天\n2.某天\n3.工作日")
@everyday_en_matcher.got("word", prompt="请输入提醒语句，默认为 打卡!!!")
async def _(
    bot: Bot,
    event: MessageEvent,
    matcher: Matcher,
    args: Tuple[Optional[str]] = RegexGroup(),
    word: Message = ArgPlainText(),
    repeat: Message = ArgPlainText()
):
    arg1 = args[0] if args[0] else f'${env_config.default_hour:02d}:${env_config.default_minute:02d}'
    # 判断schId是int
    try:
        repeat = int(repeat)
    except Exception as e:
        logger.exception(e)
        await matcher.finish("选择正确的执行间隔, 1/2/3")
        
    try:
        await addScheduler(arg1, word, event.user_id, matcher=matcher, repeat=repeat)
    except Exception as e:
        logger.exception(e)
        await matcher.finish("设置失败")
        
    await matcher.finish("设置成功")

@list_matcher.handle()
async def list_matcher_handle(
    bot: Bot,
    event: MessageEvent,
    matcher: Matcher
):
    msg = ""
    logger.opt(colors=True).info(
        f"CONFIG['opened_tasks']: {CONFIG['opened_tasks']}"
    )
    for item in CONFIG["opened_tasks"]:
        msg += f"id: {item['id']}  时间: {item['time']} 对象：{item['userId']} 内容: { item['data'] } 周期：{ '每天' if item['repeat'] == 1
        else '某天' if item['repeat'] == 2 else '工作日' }  状态: {'开启' if item['status'] == 1 else '关闭'}\n"
    
    logger.opt(colors=True).info(
        f"定时列表 <y>{msg}</y> 定时发送提醒"
    )
    await matcher.finish(msg)

@clear_matcher.handle()
async def clear_matcher_handle(
    bot: Bot,
    event: MessageEvent,
    matcher: Matcher
):
    await clearScheduler()
    CONFIG["opened_tasks"] = []
    async with lock:
        async with aiofiles.open(config_path, "w", encoding="utf8") as f:
            await f.write(json.dumps(CONFIG, ensure_ascii=False, indent=4))
    await matcher.finish("已清空所有定时提醒")    

@turn_matcher.handle()
async def _(
    bot: Bot,
    event: MessageEvent,
    matcher: Matcher,
    args: Tuple[Optional[str], ...] = RegexGroup(),
):
    if not scheduler:
        await matcher.finish("未安装软依赖nonebot_plugin_apscheduler，不能使用定时发送功能")
    mode = args[0]
    schId = args[1] if args[1] else None
    if(not schId):
        await matcher.finish("请输入具体的id")
       
    # 判断schId是int
    try:
        schId = int(schId)
    except Exception as e:
        logger.exception(e)
        await matcher.finish("请输入正确的id")
         
    if mode == "开启":
        # 遍历CONFIG["opened_tasks"]中每个对象的id
        for item in CONFIG["opened_tasks"]:
            find = False
            if item["id"] == schId:
                find = True
                if item["status"] == 1:
                    await matcher.finish("该定时提醒已开启，无需重复开启")
                else:
                    item["status"] = 1
                    setScheduler(schId, 1)
            if not find:
                await matcher.finish("没有找到对应id的题型, 请检查输入是否正确")
    elif mode == "关闭":
        for item in CONFIG["opened_tasks"]:
            if item["id"] == schId:
                item["status"] = 0
                setScheduler(schId, 0)
    elif mode == "删除":
        for item in CONFIG["opened_tasks"]:
            if item["id"] == schId:
                CONFIG["opened_tasks"].remove(item)
                removeScheduler(schId)
                
    async with lock:
        async with aiofiles.open(config_path, "w", encoding="utf8") as f:
            await f.write(json.dumps(CONFIG, ensure_ascii=False, indent=4))
    await matcher.finish(f"已成功{mode}{schId}的定时提醒")

async def post_scheduler(user_id: int, msg: str, judgeWorkDay: bool = False):
    if judgeWorkDay:
        if not is_workday(date.today()):
            logger.opt(colors=True).info(
                f"今天不是工作日，不发送提醒"
            )
            return
    bot: Bot = get_bot()
    await bot.send_private_msg(user_id=user_id, message=msg)

## 绑定post_scheduler 和参数 a,


async def addScheduler(time: str, data: str, userId: int , matcher: Matcher, repeat: int = 1, dateStr: str = None):
    # # 重置
    # scheduler.remove_all_jobs()
    # CONFIG: Dict[str, List] = {"opened_tasks": []}
    # async with aiofiles.open(config_path, "w", encoding="utf8") as f:
    #     await f.write(json.dumps(CONFIG, ensure_ascii=False, indent=4))
    if scheduler:
        ## 小时-分钟格式的时间提取出来
        hour, minute = time.split(":")
        logger.opt(colors=True).info(
            f"已设定于 <y>{str(hour).rjust(2, '0')}:{str(minute).rjust(2, '0')}</y> 定时发送提醒"
        )
        
        warp_func = partial(post_scheduler, user_id=userId, msg=data)
        curLen: Optional[int] = CONFIG["opened_tasks"].__len__()
        
        # 每天或工作日
        if repeat == 1 or repeat == 3:
            if repeat == 3:
                warp_func = partial(post_scheduler, user_id=userId, msg=data, judgeWorkDay=True)
            scheduler.add_job(
                warp_func, "cron", hour=hour, minute=minute, id="{curLen}"
            )
        
        # 某天
        elif repeat == 2:
            # 检查date 格式是否符合 yyyy-mm-dd
            year = 1
            month = 1
            day = 1
            try:
                date_object = datetime.strptime(dateStr, '%Y-%m-%d')
                year = date_object.year
                month = date_object.month
                day = date_object.day
            except ValueError:
                await matcher.finish(f"日期格式错误，应为 yyyy-mm-dd，如 2021-01-01")

            scheduler.add_job(
                warp_func, "date", run_date=date(year, month, day), hour=hour, minute=minute, id="{curLen}"
            )


        CONFIG["opened_tasks"].append({"id": curLen + 1, "time": time, "data": data,  "repeat": repeat, "userId": userId, "status": 1})
        async with aiofiles.open(config_path, "w", encoding="utf8") as f:
            await f.write(json.dumps(CONFIG, ensure_ascii=False, indent=4))
            
async def setScheduler(id: str, status: int = 1):
    if scheduler:
        if(status == 0):
            scheduler.pause_job(id)
        else:
            scheduler.reschedule_job(id)
            
async def removeScheduler(id: str):
    if scheduler:
        scheduler.remove_job(id)
        
async def clearScheduler():
    if scheduler:
        scheduler.remove_all_jobs()
        
