from pydantic import BaseModel

class Config(BaseModel):
    # 默认提醒时间的小时数
    reminder_default_hour: int = 17
    # 默认提醒时间的分钟数
    reminder_default_minute: int = 0
    # 底层任务id长度
    reminder_id_len:int = 5
    # 底层任务id的前缀
    reminder_id_prefix:str = "reminder"
    # 列出任务时，每次列出的条目数
    reminder_page_size:int = 5
    # 最多有几个备份
    reminder_bk_size:int = 2
    
    class Config:
        extra = "ignore"
        case_sensitive = False