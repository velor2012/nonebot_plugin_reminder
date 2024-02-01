import datetime
import random
import string
from nonebot.plugin import on_regex
from nonebot.params import ArgPlainText
from nonebot.adapters.onebot.v11 import (
    Bot,
    MessageEvent,
    Message,
    MessageSegment,
    GroupMessageEvent
)
from nonebot.rule import to_me
from nonebot.params import Matcher, RegexGroup
from nonebot.log import logger
from nonebot.permission import SUPERUSER
from nonebot import require, get_driver, get_bot
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from datetime import date, datetime, timedelta
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
from nonebot.typing import T_State
from nonebot.adapters import MessageTemplate

__version__ = "0.1.1"

__plugin_meta__ = PluginMetadata(
    name="定时提醒",
    description="主要用来提醒大家别忘记什么事情，可以看成定时提醒插件",
    usage='''
    定时 [date]→ 设置定时提醒，date为时间，格式为HH:MM，如 23:59， 不设置默认为17点 \n
    定时列表 → 列出所有定时提醒 \n
    清空定时 → 清空所有定时提醒 \n
    定时jobs  → 列出底层任务情况 \n
    定时请求  → 定时请求数据，目前支持图片 \n
    执行/删除/开启/关闭定时 [id] → 执行/删除/开启/关闭指定id的定时提醒
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

remainer_matcher = on_regex(r"^定时[\s]*(\d{1,2}:\d{1,2})?$", priority=999, rule=to_me())
fetch_matcher = on_regex(r"^定时请求[\s]*(\d{1,2}:\d{1,2})?$", priority=999,rule=to_me())
list_matcher = on_regex(r"^定时[\s]*列表", priority=999,rule=to_me())
list_apsjob_matcher = on_regex(r"^定时jobs", priority=999,rule=to_me())
clear_matcher = on_regex(r"^清(空|除)定时", priority=999,rule=to_me())
turn_matcher = on_regex(rf"^(开启|关闭|删除|执行)定时[\s]*({plugin_config.reminder_id_prefix + '_'}[a-zA-Z0-9]+)$", priority=999, permission=SUPERUSER,rule=to_me())
update_matcher = on_regex(rf"^(修改|更新)定时[\s]*({plugin_config.reminder_id_prefix + '_'}[a-zA-Z0-9]+)$", priority=999, permission=SUPERUSER,rule=to_me())

lock = asyncio.Lock()


@remainer_matcher.got("repeat", prompt="选择执行间隔:\n1.每天 回复1 \n2.某天回复具体日期，格式为yyyy-mm-dd,如2023-01-03 \n3.工作日 回复3")
@remainer_matcher.got("word", prompt="请输入提醒语句，默认为 打卡!!!， 回复0即可")
async def remainer_handler(
    bot: Bot,
    event: MessageEvent,
    matcher: Matcher,
    args: Tuple[Optional[str]] = RegexGroup(),
    word: Message = ArgPlainText(),
    repeat: Message = ArgPlainText(),
    url: str = None
):
    logger.opt(colors=True).debug(
        f"scheduler.print_jobs(): {scheduler.print_jobs()}"
    )
    arg1 = args[0] if args[0] else f'{plugin_config.reminder_default_hour:02d}:{plugin_config.reminder_default_minute:02d}'
    
    word = word if word != '0' else "打卡!!!"
    
    msg = Message("")
    groupId = -1
    if isinstance(event, GroupMessageEvent):
        groupId = event.group_id
    try:
        res = await addScheduler(arg1, word, event.user_id, groupId=groupId, repeat=repeat, url=url)
        logger.opt(colors=True).debug(
            f"addScheduler.res: {res}"
        )
        if res is not None and res != "" and res["code"] != 0:
            msg = Message(res['msg'])
        else:
            msg = Message("设置成功")
    except Exception as e:
        logger.exception(e)
        msg = Message("设置失败")
    
    await sendReply(bot, matcher, event, msg)

@fetch_matcher.got("repeat", prompt="选择执行间隔:\n1.每天 回复1 \n2.某天回复具体日期，格式为yyyy-mm-dd,如2023-01-03 \n3.工作日 回复3")
@fetch_matcher.got("word", prompt="请输入提醒语句，默认为 打卡!!!， 回复0即可")
@fetch_matcher.got("url", prompt="请输入需要请求的url，目前支持图片")
async def fetch_handler(
    bot: Bot,
    event: MessageEvent,
    matcher: Matcher,
    args: Tuple[Optional[str]] = RegexGroup(),
    word: Message = ArgPlainText(),
    repeat: Message = ArgPlainText(),
    url: str = ArgPlainText()
):
    if url is None or url == "" or not isUrlSupport(url):
        await sendReply(bot, matcher, event, "暂不支持该类型的请求")
    else:
        await remainer_handler(bot, event, matcher, args, word, repeat, url)


@update_matcher.got("type", prompt="请输入需要修改的地方： 1. 时间 2.间隔 3.提醒语句 4.url 5.对象 6.群组")
async def update_handler(
    bot: Bot,
    event: MessageEvent,
    matcher: Matcher,
    state: T_State,
    args: Tuple[Optional[str], ...] = RegexGroup(),
    type: Message = ArgPlainText()
):
    typeMap = {"1": "time", "2": "repeat", "3": "data", "4": "url", "5": "userId", "6": "groupId"}
    if not scheduler:
        await sendReply(bot, matcher, event, "未安装软依赖nonebot_plugin_apscheduler，不能使用定时发送功能")
    if args[1] is None:
        await sendReply(bot, matcher, event, "请输入具体的id")
    schId = args[1]
 
    jobItem = findJobFromJSONById(schId)
    if jobItem is None:
        await sendReply(bot, matcher, event, "未找到该id的定时提醒")
            
    oldValue = jobItem[typeMap[type]] if jobItem and typeMap[type] in jobItem else ""
    
    state["reminder_update_old_value"] = oldValue
    state["reminder_update_type"] = type
    state["reminder_update_jobItem"] = jobItem

@update_matcher.got("newValue", prompt=MessageTemplate("请输入更新后的值，当前为: {reminder_update_old_value}"))
async def update_handler2(
    bot: Bot,
    event: MessageEvent,
    matcher: Matcher,
    state: T_State,
    newValue: Message = ArgPlainText(),
):
    item = state["reminder_update_jobItem"]
    if item is None:
        sendReply(bot, matcher, event, "未找到定时提醒")
    typeMap = {"1": "time", "2": "repeat", "3": "data", "4": "url", "5": "userId", "6": "groupId"}
    item[typeMap[state["reminder_update_type"]]] = newValue
    
    msg = Message("")
    res = await updateScheduler(item)
    if res is not None and res != "":
        if res["code"] != 0:
            msg.append(res)
        else:
            msg.append(f"设置成功, id更改为: {res['msg']}")
    else:
        msg.append("设置成功")
    await sendReply(bot, matcher, event, msg)

@list_matcher.handle()
async def list_matcher_handle(
    bot: Bot,
    event: MessageEvent,
    matcher: Matcher
):
    msg = Message("")
    logger.opt(colors=True).info(
        f"CONFIG['opened_tasks']: {CONFIG['opened_tasks']}"
    )
    for item in CONFIG["opened_tasks"]:
        msg.append(f"id: {item['id']} \n\
对象：{item['userId']} \n\
群组: {item['groupId']} \n\
内容: { item['data'] } \n\
URL: {item['url']} \n\
周期：{ '每天' if item['repeat'] == '1' else '工作日' if item['repeat'] == '3' else  item['repeat'] } \n\
时间: {item['time']} \n\
状态: {'开启' if item['status'] == 1 else '关闭'} \n\
-------------------------\n")

    if(msg.extract_plain_text() == ""):
        msg.append("没有定时提醒")
    
    await sendReply(bot, matcher, event, msg)

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
    
    msg = Message(output.getvalue())
    
    await sendReply(bot, matcher, event, msg)

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

    await sendReply(bot, matcher, event, "已清空所有定时提醒")

@turn_matcher.handle()
async def _(
    bot: Bot,
    event: MessageEvent,
    matcher: Matcher,
    args: Tuple[Optional[str], ...] = RegexGroup(),
):
    if not scheduler:
        await sendReply(bot, matcher, event, "未安装软依赖nonebot_plugin_apscheduler，不能使用定时发送功能")
    mode = args[0]
    schId = args[1] if args[1] else None
    if(not schId):
        await sendReply(bot, matcher, event, "请输入具体的id")
    
    item = findJobFromJSONById(schId)
        
    if mode == "开启":
        if item["status"] == 1:
            await sendReply(bot, matcher, event, "该定时提醒已开启，无需重复开启")
        else:
            item["status"] = 1
    elif mode == "关闭":
        item["status"] = 0
        setScheduler(schId, 0)
    elif mode == "删除":
        CONFIG["opened_tasks"].remove(item)
        removeScheduler(schId)
    elif mode == "执行":
        job = scheduler.get_job(schId)
        if job:
            # 添加一个job并立即执行
            current_time = datetime.now()
            # 给da加10秒

            # 加上 10 秒
            new_time = current_time + timedelta(seconds=10)
            job.modify(next_run_time=new_time)
            await sendReply(bot, matcher, event, f"正在执行{schId}的定时提醒")
            # new_job = scheduler.run_job(job, 'date', next_run_time=datetime.now())
                   
    async with lock:
        async with aiofiles.open(config_path, "w", encoding="utf8") as f:
            await f.write(json.dumps(CONFIG, ensure_ascii=False, indent=4))

    await sendReply(bot, matcher, event, f"已成功{mode}{schId}的定时提醒")

async def post_scheduler(user_id: int, groupId: int, msg: str, judgeWorkDay: bool = False, url: str = None):
    logger.opt(colors=True).debug(
        f"执行任务<g>url: {url} msg:{msg}</g>"
    )
    if judgeWorkDay:
        if not is_workday(date.today()):
            logger.opt(colors=True).info(
                f"今天不是工作日，不发送提醒"
            )
            return
    if url is not None and url != "":
        msg_img = MessageSegment.image(url)
        logger.opt(colors=True).debug(
            f"获取图片成功"
        )
        msg = Message(msg) + Message(msg_img)
    
    bot: Bot = get_bot()
    if(groupId > 0):
        msg = Message(msg)
        if user_id > 0:
            msg.append(MessageSegment.at(user_id))
        await bot.send_group_msg(group_id=groupId, message=msg)
        return
    
    logger.opt(colors=True).debug(
        f"执行完成任务，发送给<g>user_id: {user_id} msg:{msg}</g>"
    )
    await bot.send_private_msg(user_id=user_id, message=msg)


async def addScheduler(time: str, data: str, userId: int , repeat: str = 1, url: str = None, groupId:int = 0):
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

        useId = generateRandomId()

        # 每天或工作日
        judgeWorkDay = False
        if repeat == '1' or repeat == '3':
            if repeat == '3':
                judgeWorkDay = True
            job = scheduler.add_job(
                post_scheduler, "cron", hour=hour, minute=minute, id=useId, args=[userId, groupId, data, judgeWorkDay, url]
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
                return {"code": -1, "msg": f"日期格式错误，应为 yyyy-mm-dd，如 2021-01-01"}
            
            job = scheduler.add_job(
                post_scheduler, "date", run_date=datetime(int(year), int(month), int(day), int(hour), int(minute), 0), id=useId, \
                      args=[userId, groupId, data, judgeWorkDay, url]
            )

        if job is not None:
            plans.append({"id": job.id, "time": time, "data": data, \
                "repeat": repeat, "userId": userId, "groupId": groupId, "url": url, "status": 1})
            async with aiofiles.open(config_path, "w", encoding="utf8") as f:
                await f.write(json.dumps(CONFIG, ensure_ascii=False, indent=4))
            return {"code": 0, "msg": job.id}
            
async def setScheduler(id: str, status: int = 1):
    if scheduler and isVaildId(id):
        if(status == 0):
            scheduler.pause_job(id)
        else:
            scheduler.reschedule_job(id)
            
async def removeScheduler(id: str):
    if scheduler and isVaildId(id):
        scheduler.remove_job(id)
        
async def clearScheduler():
    if scheduler:
        jobs = scheduler.get_jobs()
        if not jobs or len(jobs) == 0:
            return False
        for job in jobs:
            if isVaildId(job.id):
                scheduler.remove_job(job.id)

# 先删除后添加新job
async def updateScheduler(item: Any):
    id = item["id"]
    CONFIG["opened_tasks"].remove(item)
    removeScheduler(id)
    return await addScheduler(item["time"], item["data"], int(item["userId"]), item["repeat"], item["url"], int(item["groupId"]))
        
def generateRandomId():
    characters = string.ascii_lowercase + string.digits
    random_id = plugin_config.reminder_id_prefix + '_' + ''.join(random.choices(characters, k=plugin_config.reminder_id_len))
    while checkIdExit(random_id):
        random_id = plugin_config.reminder_id_prefix + '_' + ''.join(random.choices(characters, k=plugin_config.reminder_id_len))
    return random_id

def checkIdExit(needCheckedId: str):
    jobs = scheduler.get_jobs()
    if not jobs or len(jobs) == 0:
        return False
    for job in jobs:
        if job.id.lower() == needCheckedId.lower():
            return True
    return False

def isUrlSupport(url: str):
    # 判断url是否是图片
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp']
    if url.lower().startswith('http') and any(url.lower().endswith(ext) for ext in image_extensions):
        return True
    else:
        return False
    
def processGroupEvent(event: GroupMessageEvent, msg: Message = None):
    userId = event.user_id
    groupId = -1
    if isinstance(event, GroupMessageEvent):
        groupId = event.group_id
    messageId = event.message_id
    if msg is None:
        msg = Message("")
    if not isinstance(msg, Message):
        msg = Message(msg)
    if isinstance(event, GroupMessageEvent):
        msg.append(MessageSegment.reply(messageId))
        msg.append(MessageSegment.at(userId))
    return userId, groupId, messageId, msg

async def sendReply(bot: Bot, matcher: Matcher, event: GroupMessageEvent, msg: Message = None):
    #  处理群组消息
    userId, groupId, messageId, msg = processGroupEvent(event, msg)
    
    if isinstance(event, GroupMessageEvent):
        await bot.send_group_msg(group_id=groupId, message=msg)
        msg = None
        logger.opt(colors=True).info(
            "<g>群组消息</g>"
        )
    await matcher.finish(msg) 

def findJobFromJSONById(id: str):
    for item in CONFIG["opened_tasks"]:
        if item["id"] == id:
            return item
    return None

def isVaildId(id: str):
    if id is None or id == "":
        return False
    return id.lower().startswith(plugin_config.reminder_id_prefix.lower())