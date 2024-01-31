from pydantic import BaseSettings


class Config(BaseSettings):
    default_hour: int = 17
    default_minute: int = 0

    class Config:
        extra = "ignore"
        case_sensitive = False