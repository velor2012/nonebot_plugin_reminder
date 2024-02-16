import datetime
import random
import string
from nonebot.plugin import on_regex
from nonebot.params import ArgPlainText
from nonebot.rule import to_me
from nonebot.params import Matcher, RegexGroup
from nonebot.log import logger
from nonebot.permission import SUPERUSER
from nonebot import require, get_driver, get_bot, get_bots
from nonebot.adapters import Message, Event, Bot
from typing import Any, Dict, List, Optional, Tuple
from nonebot.adapters.onebot.v11 import MessageEvent
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
require("nonebot_plugin_saa")
from nonebot_plugin_saa import Text, MessageFactory, Image, \
SaaTarget, PlatformTarget, TargetQQGroup, TargetQQPrivate, MessageSegmentFactory, \
Mention, Reply
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
# ^(?:(?:\@.*))* 用于兼容一些插件，群聊时被@,没有去掉@的那一部分
remainer_matcher = on_regex(r"^(?:(?:\@.*))*定时[\s]*(\d{1,2}:\d{1,2})?$", priority=999, rule=to_me())
fetch_matcher = on_regex(r"^(?:(?:\@.*))*定时请求[\s]*(\d{1,2}:\d{1,2})?$", priority=999,rule=to_me())
list_matcher = on_regex(r"^(?:(?:\@.*))*定时[\s]*列表(\d+)?", priority=999, rule=to_me())
list_apsjob_matcher = on_regex(r"^(?:(?:\@.*))*定时jobs", priority=999,rule=to_me())
clear_matcher = on_regex(r"^(?:(?:\@.*))*清(空|除)定时", priority=999,rule=to_me())
turn_matcher = on_regex(rf"^(?:(?:\@.*))*(查看|开启|关闭|删除|执行)定时[\s]*({plugin_config.reminder_id_prefix + '_'}[a-zA-Z0-9]+)$", priority=999, permission=SUPERUSER,rule=to_me())
update_matcher = on_regex(rf"^(?:(?:\@.*))*(修改|更新)定时[\s]*({plugin_config.reminder_id_prefix + '_'}[a-zA-Z0-9]+)$", priority=999, permission=SUPERUSER,rule=to_me())

lock = asyncio.Lock()

targetTypes: Dict[str, str] = {
    "qqGroup": TargetQQGroup(group_id=123456789).platform_type,
    "qqPrivate": TargetQQPrivate(user_id=100101).platform_type,
}


@remainer_matcher.got("repeat", prompt="选择执行间隔:\n1.每天 回复1 \n2.某天回复具体日期，格式为yyyy-mm-dd,如2023-01-03 \n3.工作日 回复3")
@remainer_matcher.got("word", prompt="请输入提醒语句，默认为 打卡!!!， 回复0即可")
async def remainer_handler(
    matcher: Matcher,
    event: Event,
    target: SaaTarget,
    bot: Bot,
    args: Tuple[Optional[str]] = RegexGroup(),
    word: str = ArgPlainText(),
    repeat: str = ArgPlainText(),
    url: str = None
):
    userId = event.get_user_id()
    arg1 = args[0] if args[0] else f'{plugin_config.reminder_default_hour:02d}:{plugin_config.reminder_default_minute:02d}'
    
    word = word if word != '0' else "打卡!!!"

    if not bot:
        sendReply(f"当前用户:{bot.self_id} 不是bot")
    try:
        res = await addScheduler(bot.self_id, target,  arg1, word, repeat=repeat, url=url)
        logger.opt(colors=True).debug(
            f"addScheduler.res: {res}"
        )
        if res is not None and res != "" and res["code"] != 0:
            msg = Text(res['msg'])
        else:
            msg = Text("设置成功")
    except Exception as e:
        logger.exception(e)
        msg = Text("设置失败")
    
    await sendReply(msg, target)

@fetch_matcher.got("repeat", prompt="选择执行间隔:\n1.每天 回复1 \n2.某天回复具体日期，格式为yyyy-mm-dd,如2023-01-03 \n3.工作日 回复3")
@fetch_matcher.got("word", prompt="请输入提醒语句，默认为 打卡!!!， 回复0即可")
@fetch_matcher.got("url", prompt="请输入需要请求的url，目前支持图片")
async def fetch_handler(
    bot: Bot,
    event: Event,
    matcher: Matcher,
    target: SaaTarget,
    args: Tuple[Optional[str]] = RegexGroup(),
    word: str = ArgPlainText(),
    repeat: str = ArgPlainText(),
    url: str = ArgPlainText()
):
    if url is None or url == "" or not isUrlSupport(url):
        await sendReply("暂不支持该类型的请求", target)
    else:
        await remainer_handler( matcher=matcher, bot=bot, event=event, target=target, args=args, word=word, repeat=repeat, url=url)


@update_matcher.got("type", prompt="请输入需要修改的地方： 1. 时间 2.间隔 3.提醒语句 4.url 5.私聊对象 6.群组")
async def update_handler(
    bot: Bot,
    event: Event,
    target: SaaTarget,
    matcher: Matcher,
    state: T_State,
    args: Tuple[Optional[str], ...] = RegexGroup(),
    type: str = ArgPlainText()
):
    typeMap = {"1": "time", "2": "repeat", "3": "data", "4": "url", "5": "userId", "6": "groupId"}
    if not scheduler:
        await sendReply("未安装软依赖nonebot_plugin_apscheduler，不能使用定时发送功能", target)
    if args[1] is None:
        await sendReply("请输入具体的id", target)
    schId = args[1]
 
    jobItem = findJobFromJSONById(schId)
    if jobItem is None:
        await sendReply("未找到该id的定时提醒", target)
    
    oldValue = ""
    if type in ["5", "6"]:
        toTarget = buildTarget(jobItem["target"])
        logger.opt(colors=True).debug(
            f"修改发送目标 toTarget: {toTarget}"
        )
        oldValue = jobItem["target"]
    else:
        oldValue = jobItem[typeMap[type]] if jobItem and typeMap[type] in jobItem else ""
    
    state["reminder_update_old_value"] = oldValue
    state["reminder_update_type"] = type
    state["reminder_update_jobItem"] = jobItem

@update_matcher.got("newValue", prompt=MessageTemplate("请输入更新后的值，当前为: {reminder_update_old_value}"))
async def update_handler2(
    bot: Bot,
    event: Event,
    target: SaaTarget,
    matcher: Matcher,
    state: T_State,
    newValue: str = ArgPlainText(),
):
    item = state["reminder_update_jobItem"]
    if item is None:
        sendReply("未找到定时提醒", target)
    typeMap = {"1": "time", "2": "repeat", "3": "data", "4": "url", "5": "userId", "6": "groupId"}
    if state["reminder_update_type"] in ["5", "6"]:
        if state["reminder_update_type"] == "5":
            toTarget = TargetQQPrivate(user_id=int(newValue))
        else:
            toTarget = TargetQQGroup(group_id=int(newValue))
        logger.opt(colors=True).debug(
            f"修改发送目标 toTarget: {toTarget}"
        )
        item["target"] = toTarget.dict()
    else:
        item[typeMap[state["reminder_update_type"]]] = newValue
    
    msg = Text("")
    res = await updateScheduler(item)
    if res is not None and res != "":
        if res["code"] != 0:
            msg += res
        else:
            msg += f"设置成功, 最新信息如下\n {item2string(item)}"
    else:
        msg += "设置成功"
    await sendReply(msg, target)

@list_matcher.handle()
async def list_matcher_handle(
    target: SaaTarget,
    args: Tuple[Optional[int], ...] = RegexGroup(),
):
    page = args[0] if len(args) > 0 and args[0] else 1
    pageSize = plugin_config.reminder_page_size
    startIdx = (page - 1) * pageSize
    msg = ""
    logger.opt(colors=True).info(
        f"CONFIG: {CONFIG}"
    )
    msg += f"共计{len(CONFIG)}个定时提醒 \n\
-------------------------\n"
    
    # 分页返回
    items = list(CONFIG.values())
    for idx in range(startIdx, len(items)):
        if idx < (page - 1) * pageSize or idx >= page * pageSize:
            break
        item = items[idx]
        
        msg += item2string(item)

    if(str(msg) == ""):
        msg += "没有定时提醒"
    
    await sendReply(msg, target)

@list_apsjob_matcher.handle()
async def list_apsjob_matcher_handle(
    target: SaaTarget,
):
    msg = None
    if not scheduler:
        msg = Text("未安装软依赖nonebot_plugin_apscheduler，不能使用此功能")
    else:
        msg = Text(get_jobs_info())
    
    await sendReply(msg, target)

@clear_matcher.handle()
async def clear_matcher_handle(
    bot: Bot,
    event: Event,
    matcher: Matcher,
    target: SaaTarget,
):
    global CONFIG
    await clearScheduler()
    CONFIG = clear_datas(CONFIG=CONFIG)
    await save_datas(CONFIG=CONFIG)
    logger.opt(colors=True).info(
        f"保存配置: {CONFIG}"
    )
    CONFIG = get_datas()
    await sendReply("已清空所有定时提醒",target)

@turn_matcher.handle()
async def _(
    bot: Bot,
    target: SaaTarget,
    event: Event,
    matcher: Matcher,
    args: Tuple[Optional[str], ...] = RegexGroup(),
):
    if not scheduler:
        await sendReply("未安装软依赖nonebot_plugin_apscheduler，不能使用定时发送功能", target)
    mode = args[0]
    schId = args[1] if args[1] else None
    if(not schId):
        await sendReply("请输入具体的id", target)
    
    item = findJobFromJSONById(schId)
    if item is None:
        await sendReply("未找到该id的定时提醒",target)
        
    if mode == "开启":
        if item["status"] == 1:
            await sendReply("该定时提醒已开启，无需重复开启",target)
        else:
            item["status"] = 1
    elif mode == "关闭":
        item["status"] = 0
        setScheduler(schId, 0)
    elif mode == "删除":
        CONFIG.pop(schId, {})
        await removeScheduler(schId)
    elif mode == "查看":
        await sendReply(item2string(item),target)
    elif mode == "执行":
        job = scheduler.get_job(schId)
        if job:
            # 添加一个job并立即执行
            current_time = datetime.now()

            # 加上 10 秒
            new_time = current_time + timedelta(seconds=10)
            job.modify(next_run_time=new_time)
            await sendReply(f"正在执行{schId}的定时提醒",target)
            # new_job = scheduler.run_job(job, 'date', next_run_time=datetime.now())
                   
    await save_datas(CONFIG=CONFIG)

    await sendReply(f"已成功{mode}{schId}的定时提醒",target)

async def post_scheduler(botId: str, target_dict: Dict, msg: str, judgeWorkDay: bool = False, url: str = None, useId: str = None):
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
        msg_img = Image(url)
        logger.opt(colors=True).debug(
            f"获取图片成功"
        )
        msg = MessageFactory([msg, msg_img])
    bot = None
    try:
        bot = get_bot(self_id=botId)
    except:
        logger.opt(colors=True).error(
            f"botId: {botId} 未找到bot"
        )
        return
        
    logger.opt(colors=True).debug(
        f"执行完成任务，发送给<g>target:{target_dict}</g>"
    )
    target = buildTarget(target_dict)
    # 非循环的任务，执行后删除
    if useId is not None and useId != "":
        removeScheduler(id=useId)
    await sendToReply(msg= msg, bot = bot, target=target)


async def addScheduler(botId: str, target: SaaTarget, time: str, data: str, repeat: str = 1, url: str = None, id=None):
    if scheduler:
        logger.opt(colors=True).debug(
            f"<y>target: {target} time:{time}</y>"
        )
        ## 小时-分钟格式的时间提取出来
        hour, minute = time.split(":")
        logger.opt(colors=True).info(
            f"已设定于 <y>{str(hour).rjust(2, '0')}:{str(minute).rjust(2, '0')}</y> 定时发送提醒"
        )
        job = None
        plans = CONFIG

        useId = id if id else generateRandomId()
        target_dict = target.dict()
        # 每天或工作日
        judgeWorkDay = False
        if repeat == '1' or repeat == '3':
            if repeat == '3':
                judgeWorkDay = True
            job = scheduler.add_job(
                post_scheduler, "cron", hour=hour, minute=minute, id=useId, replace_existing=True, args=[botId, target_dict, data, judgeWorkDay, url]
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
                    replace_existing=True,  args=[botId, target_dict, data, judgeWorkDay, url, useId]
            )

        if job is not None:
            plans[job.id] = {"id": job.id, "bot":botId, "time": time, "data": data, \
                "repeat": repeat, "target":target_dict, "url": url, "status": 1}
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
    target = buildTarget(item["target"])
    return await addScheduler(botId, target, item["time"], item["data"], item["repeat"], item["url"], id= id)
    
def buildTarget(target_dict: Dict):
    return PlatformTarget.deserialize(target_dict);
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
        for key in CONFIG:    
            item = CONFIG[key]
            res = await updateScheduler(item)
            if res is not None and res != "":
                continue
            else:
                raise Exception("回复定时任务：设置失败")
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

async def sendReply(msg: MessageSegmentFactory, target: PlatformTarget):
    if(isinstance(msg, str)):
        msg = Text(msg) 
    if target and target.platform_type == targetTypes.get("qqGroup"):
        await msg.send(reply=True, at_sender=True)
    else:
        await msg.send()
async def sendToReply(msg: MessageSegmentFactory, bot: Bot, target: PlatformTarget, useId: str = None, messageId: str = None):
    if(isinstance(msg, str)):
        msg = Text(msg)
    if(useId is not None):
        mention = Mention(user_id=useId)
        msg = MessageFactory([msg, mention])
    if messageId is not None:
        msg = MessageFactory([msg, Reply(message_id=messageId)])
    await msg.send_to(bot=bot, target=target)