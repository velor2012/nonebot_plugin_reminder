from pydantic import BaseModel

class Config(BaseModel):
    reminder_default_hour: int = 17
    reminder_default_minute: int = 0
    reminder_id_len:int = 5
    reminder_id_prefix:str = "reminder"
    reminder_page_size:int = 5

    class Config:
        extra = "ignore"
        case_sensitive = False