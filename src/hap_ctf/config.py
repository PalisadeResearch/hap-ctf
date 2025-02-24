from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    process_timeout: int = 60
