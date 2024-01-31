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
from datetime import date, datetime
import asyncio
import aiofiles
from .config import Config
from functools import partial
from chinese_calendar import is_workday
try:
    import ujson as json
except ImportError:
    import json
from nonebot.plugin import PluginMetadata
from io import StringIO

__version__ = "0.1.1"

__plugin_meta__ = PluginMetadata(
    name="定时提醒",
    description="主要用来提醒大家别忘记什么事情，可以看成定时提醒插件",
    usage='''
    定时提醒 [date]→ 设置定时提醒，date为时间，格式为HH:MM，如 23:59， 不设置默认为17点 \n
    定时提醒 列表 → 列出所有定时提醒 \n
    定时提醒 清空 → 清空所有定时提醒 \n
    定时提醒dev  → 列出底层任务情况 \n
    删除/开启/关闭定时提醒 [id] → 删除指定id的定时提醒
    ''',

    type="application",
    # 发布必填，当前有效类型有：`library`（为其他插件编写提供功能），`application`（向机器人用户提供功能）。

    homepage="https://github.com/velor2012/nonebot_plugin_reminder",
    # 发布必填。

    config=Config,
    # 插件配置项类，如无需配置可不填写。

    supported_adapters={"~onebot.v11"},
    # 支持的适配器集合，其中 `~` 在此处代表前缀 `nonebot.adapters.`，其余适配器亦按此格式填写。
    # 若插件可以保证兼容所有适配器（即仅使用基本适配器功能）可不填写，否则应该列出插件支持的适配器。
)

plugin_config = Config.parse_obj(get_driver().config)

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

everyday_en_matcher = on_regex(r"^定时提醒[\s]*(\d{1,2}:\d{1,2})?$", priority=999)
list_matcher = on_regex(r"^定时提醒[\s]*列表", priority=999)
list_apsjob_matcher = on_regex(r"^定时提醒dev", priority=999)
clear_matcher = on_regex(r"^定时提醒[\s]*清(空|除)", priority=999)
turn_matcher = on_regex(r"^(开启|关闭|删除)定时提醒 ([a-zA-Z0-9]+)$", priority=999, permission=SUPERUSER)

lock = asyncio.Lock()

no_ffmpeg_error = (
    "发送语音失败，可能是风控或未安装FFmpeg，详见 "
    "https://github.com/MelodyYuuka/nonebot_plugin_everyday_en#q-%E4%B8%BA%E4%BB%80%E4%B9%88%E6%B2%A1%E6%9C%89%E8%AF%AD%E9%9F%B3"
)

@everyday_en_matcher.got("repeat", prompt="选择执行间隔:\n1.每天 回复1 \n2.某天回复具体日期，格式为yyyy-mm-dd,如2023-01-03 \n3.工作日 回复3")
@everyday_en_matcher.got("word", prompt="请输入提醒语句，默认为 打卡!!!， 回复0即可")
async def _(
    bot: Bot,
    event: MessageEvent,
    matcher: Matcher,
    args: Tuple[Optional[str]] = RegexGroup(),
    word: Message = ArgPlainText(),
    repeat: Message = ArgPlainText()
):
    logger.opt(colors=True).debug(
        f"plugin_config: {plugin_config}"
    )
    logger.opt(colors=True).debug(
        f"scheduler.print_jobs(): {scheduler.print_jobs()}"
    )
    arg1 = args[0] if args[0] else f'{plugin_config.reminder_default_hour:02d}:{plugin_config.reminder_default_minute:02d}'
    
    word = word if word != '0' else "打卡!!!"
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
        msg += f"id: {item['id']}  时间: {item['time']} 对象：{item['userId']} 内容: { item['data'] } \
              周期：{ '每天' if item['repeat'] == '1' else '工作日' if item['repeat'] == '3' else  item['repeat'] }  状态: {'开启' if item['status'] == 1 else '关闭'} \n"
    
    logger.opt(colors=True).info(
        f"定时列表 <y>{msg}</y> 定时发送提醒"
    )
    await matcher.finish(msg)

@list_apsjob_matcher.handle()
async def list_apsjob_matcher_handle(
    bot: Bot,
    event: MessageEvent,
    matcher: Matcher
):
    # 创建StringIO对象作为重定向的目标
    output = StringIO()
    if not scheduler:
        await matcher.finish("未安装软依赖nonebot_plugin_apscheduler，不能使用此功能")
    scheduler.print_jobs(out=output)

    await matcher.finish(output.getvalue())

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


async def addScheduler(time: str, data: str, userId: int , matcher: Matcher, repeat: str = 1):
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
        job = None
        plans = CONFIG["opened_tasks"]

        # 每天或工作日
        judgeWorkDay = False
        if repeat == '1' or repeat == '3':
            if repeat == '3':
                judgeWorkDay = True
            job = scheduler.add_job(
                post_scheduler, "cron", hour=hour, minute=minute, args=[userId, data, judgeWorkDay]
            )
        
        # 某天
        else:
            # 检查date 格式是否符合 yyyy-mm-dd
            year = 1
            month = 1
            day = 1
            try:
                date_object = datetime.strptime(repeat, '%Y-%m-%d')
                year = date_object.year
                month = date_object.month
                day = date_object.day
            except ValueError:
                await matcher.finish(f"日期格式错误，应为 yyyy-mm-dd，如 2021-01-01")
            
            job = scheduler.add_job(
                post_scheduler, "date", run_date=datetime(int(year), int(month), int(day), int(hour), int(minute), 0), args=[userId, data, judgeWorkDay]
            )

        if job is not None:
            plans.append({"id": job.id, "time": time, "data": data,  "repeat": repeat, "userId": userId, "status": 1})
            async with aiofiles.open(config_path, "w", encoding="utf8") as f:
                await f.write(json.dumps(CONFIG, ensure_ascii=False, indent=4))
            
async def setScheduler(id: str, status: int = 1):
    if scheduler:
        if(status == 0):
            scheduler.pause_job(id)
        else:
            scheduler.reschedule_job(id)
            
async def removeScheduler(id: int):
    if scheduler:
        scheduler.remove_job(id)
        
async def clearScheduler():
    if scheduler:
        scheduler.remove_all_jobs()
        
