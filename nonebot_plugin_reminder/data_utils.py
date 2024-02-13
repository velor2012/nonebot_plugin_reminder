import asyncio
from typing import Dict, List, Any
import aiofiles
from nonebot.log import logger
import json
from nonebot import require
require("nonebot_plugin_localstore")
import nonebot_plugin_localstore as store


data_file = store.get_data_file("nonebot_plugin_reminder","remain_plugin.json")
lock = asyncio.Lock()

def get_datas():
    if data_file.exists():
        with open(data_file, "r", encoding="utf8") as f:
            CONFIG: Dict[str, dict] = json.load(f)
    else:
        CONFIG: Dict[str, dict] = {}
        with open(data_file, "w", encoding="utf8") as f:
            json.dump(CONFIG, f, ensure_ascii=False, indent=4)
    return CONFIG
async def save_datas(CONFIG: Any):
    async with lock:
        async with aiofiles.open(data_file, "w", encoding="utf8") as f:
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