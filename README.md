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

定时提醒 [date]→ 设置定时提醒，date为时间，格式为HH:MM，如 23:59， 不设置默认为17点
定时提醒 列表 → 列出所有定时提醒
定时提醒 清空 → 清空所有定时提醒
删除/开启/关闭定时提醒 [id] → 删除指定id的定时提醒

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

- `定时提醒 列表`: 列出设置的所有定时任务
- `定时提醒 清空/清除`: 清除的所有定时任务
- `删除/开启/关闭定时提醒 [id]` : 删除/开启/关闭指定id的定时任务

## 配置项

配置方式：直接在 NoneBot 全局配置文件中添加以下配置项即可。

NoneBot 配置相关教程详见 [配置 | NoneBot](https://v2.nonebot.dev/docs/tutorial/configuration)


### everyday_post_hour
- 类型: int
- 默认: 17
>```python
>REMINDER_DEFAULT_HOUR=17
>```

### everyday_post_minute
- 类型: int
- 默认: 0
>```python
>REMINDER_DEFAULT_MINUTE=0
>```

## 依赖
- [`nonebot-plugin-apscheduler`](https://github.com/nonebot/plugin-apscheduler): 使用定时发送功能

## 开源许可

- 本插件使用 `MIT` 许可证开源