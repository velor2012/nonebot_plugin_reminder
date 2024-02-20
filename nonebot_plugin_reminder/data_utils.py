import asyncio
from typing import Dict, List, Any
import aiofiles
from nonebot.log import logger
import json
from nonebot import require
require("nonebot_plugin_localstore")
import nonebot_plugin_localstore as store
from time import time
from pathlib import Path
lock = asyncio.Lock()
data_file = store.get_data_file("nonebot_plugin_reminder","remain_plugin.json")
def get_datas(filepath: Path = None):
    if filepath is None:
        filepath = data_file
    if filepath.exists():
        with open(filepath, "r", encoding="utf8") as f:
            CONFIG: Dict[str, dict] = json.load(f)
    else:
        CONFIG: Dict[str, dict] = {}
        with open(filepath, "w", encoding="utf8") as f:
            json.dump(CONFIG, f, ensure_ascii=False, indent=4)
    return CONFIG
async def save_datas(CONFIG: Any, filepath: Path = None):
    if filepath is None:
        filepath = data_file
    async with lock:
        async with aiofiles.open(filepath, "w", encoding="utf8") as f:
            await f.write(json.dumps(CONFIG, ensure_ascii=False, indent=4))

def clear_datas(CONFIG: Any):
    CONFIG = {}
    return CONFIG

def item2string(item: Any):
    return f"id: {item['id']} \n\
    报送机器人：{item['bot']} \n\
    目标: {item['target']} \n\
    内容: { item['data'] } \n\
    URL: {item['url']} \n\
    周期：{ '每天' if item['repeat'] == '1' else '工作日' if item['repeat'] == '3' else  item['repeat'] } \n\
    时间: {item['time']} \n\
    状态: {'开启' if item['status'] == 1 else '关闭'} \n\
    -------------------------\n"
    
async def backup(config: Dict[str, Any] = None, maxBkNum:int = 2):
    try:
        data = None
        if config is None:
            data = get_datas()
        else:
            data = config
        bkdir = store.get_data_dir("nonebot_plugin_reminder")
        # 判断bkdir下面有多少backup文件，计算下一个文件名
        backup_files = [i for i in bkdir.iterdir() if i.is_file() and i.name.find("backup_") != -1]
        backup_files.sort() 
        # 如果达到上限，清除最早的一个
        while len(backup_files) >= maxBkNum:
            backup_files[0].unlink()
            backup_files.pop(0)
        logger.opt(colors=True).debug(
            f"<y>backup 清除多余备份</y>"
        )
        # 以时间戳为后缀命名
        date = int(time())
        next_file = Path.joinpath(bkdir, f"backup_{date}.json")
        await save_datas(data, next_file)
        return "备份成功"
    except Exception as e:
        raise e
    
# 从备份中回复定时任务，但只是恢复配置，不会恢复底层的定时任务
# filename不需要带后缀
async def recover(filename: str):
    try:
        data = None
        bkdir = store.get_data_dir("nonebot_plugin_reminder")
        # 执行mv命令
        filename = Path.joinpath(bkdir, filename + ".json")
        if filename.exists():
            with open(filename, "r", encoding="utf8") as f:
                data = json.load(f)
            await save_datas(data)
            return "恢复成功"
        else:
            return "文件不存在"
    except Exception as e:
        raise e
    
async def list_backup(page_size:int = 5, page:int = 1):
    try:
        bkdir = store.get_data_dir("nonebot_plugin_reminder")
        backup_files = [i.name for i in bkdir.iterdir() if i.is_file() and i.name.find("backup_") != -1]
        # 去掉后缀
        backup_files = [i.replace(".json", "") for i in backup_files]
        # 返回特定页数的数据
        backup_files.sort(reverse=True)
        arrs = backup_files[page_size * (page - 1):page_size * page]
        res = "\n".join(arrs)
        return res
    except Exception as e:
        raise e

async def detail_backup(filename: str, page_size:int = 5, page:int = 1):
    try:
        logger.opt(colors=True).debug(
            f"<y>detail_backup 进入获取备份函数</y>"
        )
        bkdir = store.get_data_dir("nonebot_plugin_reminder")
        filename = Path.joinpath(bkdir, filename + ".json")
        logger.opt(colors=True).debug(
            f"<y>detail_backup filename:{filename}</y>"
        )
        data = get_datas(filename)
        logger.opt(colors=True).debug(
            f"<y>detail_backup data:{data}</y>"
        )
        items = list(data.values())
        arrs = items[page_size * (page - 1):page_size * page]
        res = ""
        for item in arrs:
            res += item2string(item)
        return res
    except Exception as e:
        raise e