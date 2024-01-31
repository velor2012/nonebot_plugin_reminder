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

- `定时提醒`: 获取今天的句子
  - `每日一句[日期]`: 获取指定日期的句子
    > 日期格式为 YYYY-MM-DD , 例如 2020-01-08

- `开启/关闭定时每日一句`: 开启/关闭本群定时发送 **[SUPERUSER]**
  - `开启/关闭定时每日一句[群号]`: 开启/关闭指定群定时发送 **[SUPERUSER]**

- `查看定时每日一句列表`: 列出开启定时发送的群聊 **[SUPERUSER]**

## 配置项

配置方式：直接在 NoneBot 全局配置文件中添加以下配置项即可。

NoneBot 配置相关教程详见 [配置 | NoneBot](https://v2.nonebot.dev/docs/tutorial/configuration)

🟢 默认配置为每日 8:00 发送
### everyday_post_hour
- 类型: int
- 默认: 8
- 说明: 每日定时发送的小时，不需要在数字前加0
>```python
>EVERYDAY_POST_HOUR=8
>```

### everyday_post_minute
- 类型: int
- 默认: 0
- 说明: 每日定时发送的分钟，不需要在数字前加0
>```python
>EVERYDAY_POST_MINUTE=0
>```

### everyday_delay
- 类型: float
- 默认: 0.5
- 说明: 定时发送时各群间发送的延迟秒数，以免腾讯风控导致发送失败
>```python
>EVERYDAY_DELAY=0.5
>```

## 软依赖
- [`nonebot-plugin-apscheduler`](https://github.com/nonebot/plugin-apscheduler): 使用定时发送功能

- [`nonebot-plugin-help`](https://github.com/XZhouQD/nonebot-plugin-help): 在群内查看帮助文档
  - 也可自行解析 `__help_plugin_name__` , `__help_version__` , `__usage__`来接入您自己的帮助插件

## 常见问题

### `Q: 为什么没有语音？`
- A: 如果你使用的是`go-cqhttp`，那么你需要安装`FFmpeg`并重启本插件来使用语音功能，详见[`安装 ffmpeg`](https://docs.go-cqhttp.org/guide/quick_start.html#%E5%AE%89%E8%A3%85-ffmpeg)

### `Q: 为什么定时发送每日一句某些群无法收到？`
- A: 检查日志，频繁发送消息可能导致腾讯风控，可通过设置[`everyday_delay`](https://github.com/MelodyYuuka/nonebot_plugin_everyday_en#everyday_delay)配置项设置发送延迟来缓解

## 开源许可

- 本插件使用 `MIT` 许可证开源