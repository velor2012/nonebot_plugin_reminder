from pydantic import BaseSettings

class Config(BaseSettings):
    reminder_default_hour: int = 17
    reminder_default_minute: int = 0

    class Config:
        extra = "ignore"
        case_sensitive = False