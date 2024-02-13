<div align="center">
  <a href="https://v2.nonebot.dev/store"><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/nbp_logo.png" width="180" height="180" alt="NoneBotPluginLogo"></a>
  <br>
  <p><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/NoneBotPlugin.svg" width="240" alt="NoneBotPluginText"></p>
</div>

<div align="center">

# nonebot-plugin-reminder

_✨ NoneBot 插件简单描述 ✨_


<a href="./LICENSE">
    <img src="https://img.shields.io/github/license/velor2012/nonebot-plugin-reminder.svg" alt="license">
</a>
<a href="https://pypi.python.org/pypi/nonebot-plugin-reminder">
    <img src="https://img.shields.io/pypi/v/nonebot-plugin-reminder.svg" alt="pypi">
</a>
<img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="python">

</div>

这是一个 nonebot2 插件库, 主要用来提醒大家别忘记什么事情，可以看成定时提醒插件。


## 指令

定时 [date]→ 设置定时提醒，date为时间，格式为HH:MM，如 23:59， 不设置默认为17点
定时请求[date]→ 设置定时请求某个URL，返回其内容，**目前只能请求图片**，date为时间，格式为HH:MM，如 23:59， 不设置默认为17点
定时列表 → 列出所有定时提醒
清空|清除定时 → 清空所有定时提醒
开启|关闭|查看|删除|执行定时提醒 [id] → 开启|关闭|查看|删除|执行指定id的定时提醒
修改|更新定时 [id] → 修改指定id的定时提醒

- `定时提醒`: 在默认时间定时提醒
  - `定时提醒 [时间]`: 在指定时间定时提醒
    > 时间格式为 HH:MM , 例如 17:00

  之后 Bot 会询问提醒的时间间隔

  >  1.每天 回复1 
  >
  >  2.某天回复具体日期，格式为yyyy-mm-dd,如2023-01-03 
  >
  >  3.工作日 回复3
  
  回复数字即可

  再之后 Bot 会询问需要提醒的内容
  默认为 `打卡！！`, 回复0即使默认内容

- `定时请求`：与上面用法类似
- `定时列表 [page]`: 列出设置的所有定时任务
- `清空/清除定时 `: 清除的所有定时任务
- `查看/删除/开启/关闭/执行定时 [id]` : 查看/删除/开启/关闭指定id的定时任务
- `定时请求`: 定时请求数据，目前支持图片
- `定时jobs [page]`: 列出底层任务情况(debug使用)

## 配置项

配置方式：直接在 NoneBot 全局配置文件中添加以下配置项即可。

NoneBot 配置相关教程详见 [配置 | NoneBot](https://v2.nonebot.dev/docs/tutorial/configuration)

> ~~如果需要持久化定时任务(即nonebot2重启后任务还在)，需要配置 `nonebot-plugin-apscheduler` 插件。~~
>
> ~~在`.env`中加上
> `apscheduler_config={ "apscheduler.timezone": "Asia/Shanghai", "apscheduler.jobstores.default":{"type":"sqlalchemy","url":"sqlite:///jobs.sqlite"} }`~~
> 
> ~~进入到nonebot的安装目录，执行`source .venv/bin/activate`，进入虚拟环境~~
>
> ~~执行`pip install sqlalchemy`安装sqlalchemy。(不知道为什么`nonebot-plugin-apscheduler` 插件没有包含这个库)~~
> ~~重启nonebot2，即可持久化定时任务。~~

现在不需要配置`nonebot-plugin-apscheduler`插件的持久化了，插件已经实现了。

### reminder_default_hour
- 类型: int
- 默认: 17
>```python
>REMINDER_DEFAULT_HOUR=17
>```

### reminder_default_minute
- 类型: int
- 默认: 0
>```python
>REMINDER_DEFAULT_MINUTE=0
>```

### reminder_id_len
- 类型: int
- 说明：底层任务id长度
- 默认: 5
>```python
>REMINDER_ID_LEN=5
>```

### reminder_id_prefix
- 类型: str
- 说明：底层任务id的前缀
- 默认: 0
>```python
>REMINDER_ID_PREFIX=reminder
>```

### reminder_page_size
- 类型: str
- 说明：列出任务时，每次列出的条目数
- 默认: 0
>```python
>REMINDER_PAGE_SIZE=5
>```

## 依赖
- [`nonebot-plugin-apscheduler`](https://github.com/nonebot/plugin-apscheduler): 使用定时发送功能
- [`nonebot-plugin-localstore`](https://github.com/nonebot/plugin-localstore): 使用存储功能
- [`nonebot-plugin-send-anything-anywhere`](https://github.com/MountainDash/nonebot-plugin-send-anything-anywhere): 使用跨平台发送消息功能
## 致谢

代码基于 [nonebot-plugin-everyday-en](https://github.com/MelodyYuuka/nonebot_plugin_everyday_en)，感谢原作者的开源精神！

## 其他
修改定时的时候，私聊对象和群组只能二选一。

## 开源许可

- 本插件使用 `MIT` 许可证开源