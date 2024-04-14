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
from nonebot import require, get_driver, get_bot, get_bots
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
from .data_utils import get_datas, save_datas, clear_datas, item2string
__version__ = "0.1.1"

__plugin_meta__ = PluginMetadata(
    name="定时提醒",
    description="主要用来提醒大家别忘记什么事情，可以看成定时提醒插件",
    usage='''
    定时 [date]→ 设置定时提醒，date为时间，格式为HH:MM，如 23:59， 不设置默认为17点 \n
    定时列表 [page] → 列出设置的定时提醒\n
    清空定时 → 清空所有定时提醒 \n
    定时jobs [page]  → 列出底层任务情况 \n
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
driver = get_driver()
plugin_config = Config.parse_obj(driver.config)
CONFIG = get_datas()


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
list_matcher = on_regex(r"^定时列表[\s]*(\d+)?", priority=999,rule=to_me())
list_apsjob_matcher = on_regex(r"^定时jobs", priority=999,rule=to_me())
clear_matcher = on_regex(r"^清(空|除)定时", priority=999,rule=to_me())
turn_matcher = on_regex(rf"^(查看|开启|关闭|删除|执行)定时[\s]*({plugin_config.reminder_id_prefix + '_'}[a-zA-Z0-9]+)$", priority=999, permission=SUPERUSER,rule=to_me())
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
        res = await addScheduler(bot.self_id, arg1, word, event.user_id, groupId=groupId, repeat=repeat, url=url)
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
    matcher: Matcher,
    args: Tuple[Optional[int], ...] = RegexGroup(),
):
    page = args[0] if len(args) > 0 and args[0] else 1
    pageSize = plugin_config.reminder_page_size
    startIdx = (page - 1) * pageSize
    msg = Message("")
    logger.opt(colors=True).info(
        f"CONFIG: {CONFIG}"
    )
    msg.append(f"共计{len(CONFIG)}个定时提醒 \n\
-------------------------\n")
    
    # 分页返回
    items = list(CONFIG.values())
    for idx in range(startIdx, len(items)):
        if idx < (page - 1) * pageSize or idx >= page * pageSize:
            break
        item = items[idx]
        
        msg.append(item2string(item))

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
    # scheduler.print_jobs(out=output)
    # msg = Message(output.getvalue())
    msg = Message(get_jobs_info())
    
    await sendReply(bot, matcher, event, msg)

@clear_matcher.handle()
async def clear_matcher_handle(
    bot: Bot,
    event: MessageEvent,
    matcher: Matcher
):
    await clearScheduler()
    clear_datas(CONFIG=CONFIG)
    await save_datas(CONFIG=CONFIG)

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
    if item is None:
        await sendReply(bot, matcher, event, "未找到该id的定时提醒")
        
    if mode == "开启":
        if item["status"] == 1:
            await sendReply(bot, matcher, event, "该定时提醒已开启，无需重复开启")
        else:
            item["status"] = 1
    elif mode == "关闭":
        item["status"] = 0
        setScheduler(schId, 0)
    elif mode == "删除":
        CONFIG.pop(schId, {})
        await removeScheduler(schId)
    elif mode == "查看":
        await sendReply(bot, matcher, event, item2string(item))
    elif mode == "执行":
        job = scheduler.get_job(schId)
        if job:
            # 添加一个job并立即执行
            current_time = datetime.now()

            # 加上 10 秒
            new_time = current_time + timedelta(seconds=10)
            job.modify(next_run_time=new_time)
            await sendReply(bot, matcher, event, f"正在执行{schId}的定时提醒")
            # new_job = scheduler.run_job(job, 'date', next_run_time=datetime.now())
                   
    await save_datas(CONFIG=CONFIG)

    await sendReply(bot, matcher, event, f"已成功{mode}{schId}的定时提醒")

async def post_scheduler(botId: str, userId: int, groupId: int, msg: str, judgeWorkDay: bool = False, url: str = None, useId: str = None):
    logger.opt(colors=True).debug(
        f"执行任务<g>url: {url} msg:{msg}</g>"
    )
    if judgeWorkDay:
        if not is_workday(date.today()):
            logger.opt(colors=True).info(
                f"今天不是工作日，不发送提醒"
            )
            return

    msg = Message(msg)
    msg_img = None
    if url is not None and url != "" and isUrlSupport(url):
        msg_img = MessageSegment.image(url)
        logger.opt(colors=True).debug(
            f"获取图片成功"
        )
        msg = msg + Message(msg_img)
    
    bot = get_bot(self_id=botId)
    if(groupId > 0):
        # at定时者
        # if userId > 0:
        #     msg.append(MessageSegment.at(userId))
        await bot.send_group_msg(group_id=groupId, message=msg)
        return
    
    logger.opt(colors=True).debug(
        f"执行完成任务，发送给<g>userId: {userId} msg:{msg}</g>"
    )
    # 非循环的任务，执行后删除
    if useId is not None and useId != "":
        removeScheduler(id=userId)
        logger.opt(colors=True).debug(
            f"<y>执行完成任务{useId}，清除记录</y>"
        )
        CONFIG.pop(useId, {})
        await save_datas(CONFIG=CONFIG)
        
    await bot.send_private_msg(user_id=userId, message=msg)

async def addScheduler(botId: str, time: str, data: str, userId: int , repeat: str = 1, url: str = None, groupId:int = 0, id=None, fn=None, fnParamsArrs=None):
    if scheduler:
        ## 小时-分钟格式的时间提取出来
        hour, minute = time.split(":")
        if time.index(":") == -1:
            hour, minute = time.split("：")
            return {"code": -1, "msg": f"时间格式错误，应为 HH:MM"}
        
        logger.opt(colors=True).info(
            f"已设定于 <y>{str(hour).rjust(2, '0')}:{str(minute).rjust(2, '0')}</y> 定时发送提醒"
        )
        job = None
        plans = CONFIG

        useId = id if id else generateRandomId()

        # 每天或工作日
        judgeWorkDay = False
        if repeat == '1' or repeat == '3':
            if repeat == '3':
                judgeWorkDay = True
            if fn is not None:
                job = scheduler.add_job(
                    fn, "cron", hour=hour, minute=minute, id=useId, replace_existing=True, args=fnParamsArrs
                )
                # 不能保存job信息，因为请求天气的函数中matcher不支持序列化
            else:
                job = scheduler.add_job(
                    post_scheduler, "cron", hour=hour, minute=minute, id=useId, replace_existing=True, args=[botId, userId, groupId, data, judgeWorkDay, url]
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
            
            if fn is not None:
                job = scheduler.add_job(
                    fn, "date", run_date=datetime(int(year), int(month), int(day), int(hour), int(minute), 0), id=useId, replace_existing=True, args=fnParamsArrs
                )
            else:
                # 非循环任务
                job = scheduler.add_job(
                    post_scheduler, "date", run_date=datetime(int(year), int(month), int(day), int(hour), int(minute), 0), id=useId, \
                        replace_existing=True,  args=[botId, userId, groupId, data, judgeWorkDay, url, useId]
                )

        if job is not None:
            plans[job.id] = {"id": job.id, "bot":botId, "time": time, "data": data, \
                "repeat": repeat, "userId": userId, "groupId": groupId, "url": url, "status": 1, "type": "normal"}
            await save_datas(CONFIG=CONFIG)
            return {"code": 0, "msg": job.id}
            
async def setScheduler(id: str, status: int = 1):
    if scheduler and isVaildId(id):
        if(status == 0):
            scheduler.pause_job(id)
        else:
            scheduler.reschedule_job(id)
            
async def removeScheduler(id: str):
    logger.opt(colors=True).info(
        f"<g>删除定时{id}</g>"
    )
    if scheduler and isVaildId(id):
        try:
            scheduler.remove_job(id)
        except Exception as e:
            logger.opt(colors=True).debug(
                f"删除定时任务出错，error: {e}"
            )        
async def clearScheduler():
    if scheduler:
        jobs = scheduler.get_jobs()
        if not jobs or len(jobs) == 0:
            return False
        for job in jobs:
            if isVaildId(job.id):
                scheduler.remove_job(job.id)

async def updateScheduler(item: Any):
    id = item["id"]
    botId = item["bot"]
    if botId is None or botId == "":
        return {"code": -1, "msg": f"找不到bot"}
    return await addScheduler(botId, item["time"], item["data"], int(item["userId"]), item["repeat"], item["url"], int(item["groupId"]), id= id)
        
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

async def sendReply(bot: Bot, matcher: Matcher, event: GroupMessageEvent, msg: Message = None, finish = True):
    #  处理群组消息
    userId, groupId, messageId, msg = processGroupEvent(event, msg)
    
    if isinstance(event, GroupMessageEvent):
        await bot.send_group_msg(group_id=groupId, message=msg)
        msg = None
        logger.opt(colors=True).info(
            "<g>群组消息</g>"
        )
    if finish:
        await matcher.finish(msg) 

def findJobFromJSONById(id: str):
    if id in CONFIG:
        return CONFIG[id]
    return None

def isVaildId(id: str):
    if id is None or id == "":
        return False
    return id.lower().startswith(plugin_config.reminder_id_prefix.lower())


@driver.on_startup
async def recoverFromJson():
    if CONFIG is None or len(CONFIG) < 1:
        return
    jobs = scheduler.get_jobs()
    # 判断是否已经存在计划任务，存在则说明已经初始化过了
    for job in jobs:
        if isVaildId(job.id):
            logger.opt(colors=True).info(
                f"已经初始化过了，不需要再次初始化，退出初始化任务"
            )
            return
    
    logger.opt(colors=True).info(
        f"初始化定时任务，尝试从json中恢复定时任务"
    )
    try:
        notNormalIds = []
        for key in CONFIG:    
            item = CONFIG[key]
            if('type' in item):
                if item['type'] != 'normal':
                    notNormalIds.append(item["id"])
                    continue
                
            res = await updateScheduler(item)
            if res is not None and res != "":
                continue
            else:
                raise Exception("回复定时任务：设置失败")
        for id in notNormalIds:
            CONFIG.pop(id, {})
            await save_datas(CONFIG=CONFIG)
            
        logger.opt(colors=True).info(
            f"<y>初始化定时任务完成</y>"
        )
        scheduler.print_jobs()
    except Exception as e:
        logger.error(f"尝试从json中恢复定时任务失败，error: {e}")
        raise e

def get_jobs_info(page: int = 1):
    if scheduler:
        jobs = scheduler.get_jobs()
        pageSize = plugin_config.reminder_page_size
        startIdx = (page - 1) * pageSize
        msg = f"共计{len(jobs)}个定时任务\n"
        for idx in range(startIdx, len(jobs)):
            job = jobs[idx]
            if idx < (page - 1) * pageSize or idx >= page * pageSize:
                break
            if isVaildId(job.id):
                msg += "(本插件任务)"
            else:
                msg += "(非本插件任务)"
            msg += f"jobId: {job.id} \n\
trigger:{job.trigger} \n\
下次运行时间: {job.next_run_time}\n"
        return msg