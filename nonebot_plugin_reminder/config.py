from pydantic import BaseSettings

class Config(BaseSettings):
    reminder_default_hour: int = 17
    reminder_default_minute: int = 0
    reminder_id_len:int = 5
    reminder_id_prefix:str = "reminder"

    class Config:
        extra = "ignore"
        case_sensitive = False